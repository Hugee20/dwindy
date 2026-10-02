"""Foundation v2 capability-wording DEVELOPMENT ONLY; no holdout option or semantic auto-scorer.

The frozen evaluator is imported, never edited. Raw responses and counterfactual
tokenization remain separate from the blinded human judgment workflow.
"""
import argparse
from contextlib import closing
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import random
import secrets
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from dwindy.backend import Completion, TextDelta
from dwindy.config import load_config
from dwindy.core import DwindyCore
from dwindy.llama_backend import LlamaBackend
import dwindy.evidence as framing
from policy_foundation_v1.evaluate import (evaluate_contract, load, p95,
                                          turn_inputs, verify_freeze)
from policy_foundation_v1.probes import observe as frozen_observe
from foundation_capability_v2 import observe, capture, VERSION
from policy.evaluate import verify_freeze as historical_freeze
from policy_support import baseline_core, baseline_inputs, RecordingBackend
from reach_support import no_network

FOUNDATION = '59190f0dd49f5cd6721bdabf97472a9d69ec4829b1bce21c6a3fad74bb3e5a8f'
ORIGINAL = 'e098fe14666bd43a6ee797d8fc7e94585d169c9e4b9ac0633943590be731cc26'
CONDITIONS = ('M10', 'M11_foundation')


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')


def kwargs(case, turn, condition):
    data = turn_inputs(case, turn)
    return baseline_inputs(data) if condition == 'M10' else {
        key: data[key] for key in ('evidence', 'facts', 'notice')}


def core_type(condition):
    return baseline_core() if condition == 'M10' else DwindyCore


class Recorder(RecordingBackend):
    def __init__(self, tokenizer):
        super().__init__()
        self.tokenizer = tokenizer

    def count_tokens(self, messages):
        return self.tokenizer.count_tokens(messages)

    def context_size(self):
        return self.tokenizer.context_size()


class MeasuredBackend:
    def __init__(self, backend):
        self.backend = backend
        self.calls = 0
        self.requests = []
        self.counted = []

    def count_tokens(self, messages):
        count = self.backend.count_tokens(messages)
        self.counted.append((list(messages), count))
        return count

    def context_size(self):
        return self.backend.context_size()

    def generate(self, messages, options):
        self.calls += 1
        self.requests.append(list(messages))
        yield from self.backend.generate(messages, options)


def prepare(case, turn, condition, config, tokenizer, history):
    recorder = Recorder(tokenizer)
    core = core_type(condition)(recorder, options=config.options(), system_prompt=config.system_prompt)
    core.restore(history)
    events = list(core.chat(case['turns'][turn]['message'], **kwargs(case, turn, condition)))
    started = events[0]
    messages = recorder.requests[-1]
    return dict(messages=[asdict(m) for m in messages],
                prompt_tokens=tokenizer.count_tokens(messages),
                retained_turns=len(history)//2-started.dropped_turns,
                admitted_ids=[s['chunk_id'] for s in (started.retrieval or {}).get('sources', [])])


def construction(case, turn, condition, admitted):
    data = kwargs(case, turn, condition)
    module = sys.modules['dwindy._m10_evidence'] if condition == 'M10' else framing
    evidence, facts = data['evidence'], data['facts']
    selected = tuple(p for p in evidence.passages if p.source.chunk_id in admitted) if evidence else ()
    samples = []
    for _ in range(100):
        clock = time.perf_counter()
        if facts:
            module.facts_block(facts)
        if condition == 'M10':
            if facts:
                module.facts_guidance(facts)
        else:
            module.policy_guidance(facts, selected)
        if evidence:
            module.evidence_question(case['turns'][turn]['message'], selected, evidence.framing, evidence.origin)
        samples.append((time.perf_counter()-clock)*1000)
    return p95(samples)


def episode(case, condition, config):
    clock = time.perf_counter()
    backend = LlamaBackend(config)
    loading = time.perf_counter()-clock
    measured = MeasuredBackend(backend)
    core = core_type(condition)(measured, options=config.options(), system_prompt=config.system_prompt)
    core.restore(turn_inputs(case, 0)['history'])
    rows = []
    try:
        for turn, entry in enumerate(case['turns']):
            history = core.snapshot()
            prepared = prepare(case, turn, condition, config, backend, history)
            before = measured.calls
            measured.counted.clear()
            first = completion = started = error = None
            pieces = []
            clock = time.perf_counter()
            try:
                with closing(core.chat(entry['message'], **kwargs(case, turn, condition))) as stream:
                    for event in stream:
                        if isinstance(event, TextDelta):
                            if first is None and event.text:
                                first = time.perf_counter()-clock
                            pieces.append(event.text)
                        elif isinstance(event, Completion):
                            completion = event
                        elif hasattr(event, 'dropped_turns'):
                            started = event
            except Exception as exc:
                error = type(exc).__name__ + ': ' + str(exc)
            elapsed = time.perf_counter()-clock
            messages = measured.requests[-1] if measured.calls > before else []
            exact_counted = any(m == messages and n == prepared['prompt_tokens'] for m, n in measured.counted)
            row = dict(id=case['id'], turn=turn, condition=condition, text=''.join(pieces),
                       load_seconds=loading if turn == 0 else 0,
                       history_before=[asdict(m) for m in history],
                       history_after=[asdict(m) for m in core.snapshot()],
                       messages=[asdict(m) for m in messages],
                       prompt_tokens=prepared['prompt_tokens'],
                       completion_prompt_tokens=completion.prompt_tokens if completion else None,
                       retained_turns=prepared['retained_turns'], admitted_ids=prepared['admitted_ids'],
                       ttft_s=first, end_to_end_s=elapsed,
                       output_tokens=completion.text_tokens if completion else 0,
                       model_calls=measured.calls-before, verifier_calls=0, network_calls=0,
                       execution_error=error, finish_reason=completion.finish_reason if completion else 'error',
                       retrieval=started.retrieval if started else None,
                       budget_audit_pass=exact_counted and prepared['messages'] == [asdict(m) for m in messages]
                           and prepared['prompt_tokens']+config.max_tokens <= config.context_size
                           and completion is not None and completion.prompt_tokens == prepared['prompt_tokens'])
            row['construction_ms'] = construction(case, turn, condition, row['admitted_ids'])
            rows.append(row)
            print(json.dumps({k: row[k] for k in ('id','turn','condition','ttft_s','finish_reason','execution_error')}), flush=True)
    finally:
        backend.close()
    return rows


def run(args):
    assert verify_freeze() == FOUNDATION and historical_freeze() == ORIGINAL
    config = load_config(args.config)
    frozen = json.loads((Path('tests/policy_foundation_v1')/'baseline.json').read_text(encoding='utf-8'))
    for key in ('context_size','max_tokens','temperature','seed','threads','system_prompt','chat_template_kwargs'):
        if getattr(config, key) != frozen[key]:
            raise ValueError('Non-frozen setting: ' + key)
    if version('llama-cpp-python') != '0.3.35':
        raise ValueError('Runtime differs from frozen baseline')
    digest = hashlib.sha256()
    with config.model_path.open('rb') as model:
        for block in iter(lambda: model.read(1024*1024), b''):
            digest.update(block)
    if digest.hexdigest() != frozen['model_sha256']:
        raise ValueError('Model differs from frozen baseline')
    frozen_contracts = evaluate_contract(frozen_observe)
    failed = [r for r in frozen_contracts if not r['pass']]
    if [r['id'] for r in failed] != ['capability_1', 'capability_2'] or any(
            set(r['mismatches']) != {'capability_present', 'runtime_fact_correct'} for r in failed):
        raise RuntimeError('Unexpected frozen incompatibility; inference prohibited')
    placement = {c['id']:capture(c)[1] for c in load('contract.jsonl') if c['family']=='capability'}
    if not all(all(a.values()) for a in placement.values()):
        raise RuntimeError('Compatibility placement/accounting failure; inference prohibited')
    contracts = evaluate_contract(observe)
    if not all(row['pass'] for row in contracts):
        raise RuntimeError('Contract failure; inference prohibited')
    cases = load('cases.jsonl', 'dev')
    assert len(cases) == 24 and sum(len(c['turns']) for c in cases) == 28
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=False)
    write(root/'frozen-contracts.json', frozen_contracts)
    write(root/'compatibility-contracts.json', contracts)
    write(root/'capability-placement.json', placement)
    paths = [Path('src/dwindy/core.py'), Path('src/dwindy/evidence.py'), Path(__file__), Path('tests/foundation_capability_v2.py')]
    write(root/'manifest.json', dict(freeze=FOUNDATION, original_freeze=ORIGINAL,
          baseline_commit=frozen['commit'], model_sha256=digest.hexdigest(),
          model_filename=config.model_path.name, settings={k:frozen[k] for k in ('context_size','max_tokens','temperature','seed','threads','system_prompt','chat_template_kwargs')},
          runtime=version('llama-cpp-python'), python=platform.python_version(), platform=platform.platform(),
          code_hashes={p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
          candidate_label='Foundation v2 capability wording', implementation_compatibility_version=VERSION,
          frozen_contract_passed=30, compatibility_contract_passed=32,
          frozen_evaluation_replaced=False, split='dev', cases=[c['id'] for c in cases], planned_generations=56,
          fresh_backend_per_episode=True, live_followup_history=True,
          holdout_executed=False, output_tuning=False, blind_human_scores_sealed=False))
    rows = []
    with (root/'results.jsonl').open('x', encoding='utf-8', newline='\n') as output, no_network() as attempts:
        for ordinal, case in enumerate(cases, 1):
            pair = {}
            order = CONDITIONS if ordinal%2 else CONDITIONS[::-1]
            for condition in order:
                pair[condition] = episode(case, condition, config)
            # Counterfactuals share the actual M10 canonical retained history.
            # Tokenization only: no generation, no replacement of live history.
            tokenizer = LlamaBackend(config)
            try:
                for turn in range(len(case['turns'])):
                    from dwindy.backend import Message
                    common = tuple(Message(**m) for m in pair['M10'][turn]['history_before'])
                    matched = {c:prepare(case, turn, c, config, tokenizer, common) for c in CONDITIONS}
                    for condition in CONDITIONS:
                        row = pair[condition][turn]
                        row['matched_input_tokens'] = matched[condition]['prompt_tokens']
                        other = pair[CONDITIONS[condition == 'M10']][turn]
                        row['history_text_diverged'] = row['history_before'] != other['history_before']
                        row['budget_audit_pass'] &= row['admitted_ids'] == other['admitted_ids'] and row['retained_turns'] == other['retained_turns']
                        row['matched_history'] = [asdict(m) for m in common]
                        row['matched_messages'] = matched[condition]['messages']
                        # If generated history differs, exact counterfactual construction
                        # still isolates cost; retain and disclose both actual payloads.
                        rows.append(row)
                        output.write(json.dumps(row, ensure_ascii=True)+'\n')
                        output.flush()
            finally:
                tokenizer.close()
        write(root/'network-audit.json', dict(attempts=attempts, model_calls=sum(r['model_calls'] for r in rows), verifier_calls=0))
        if attempts:
            raise AssertionError('Network attempt during evaluation')
    key = {}
    sheet = []
    for case in cases:
        for condition in CONDITIONS:
            token = secrets.token_hex(8)
            key[token] = dict(id=case['id'], condition=condition)
            answers = sorted((r for r in rows if r['id']==case['id'] and r['condition']==condition), key=lambda r:r['turn'])
            sheet.append(dict(token=token, history=case['history'],
                              turns=[dict(request=case['turns'][r['turn']], response=r['text'], admitted_ids=r['admitted_ids']) for r in answers],
                              controls=case['controls'], gold=case['gold']))
    random.Random(1111001).shuffle(sheet)
    write(root/'blind-sheet.json', sheet)
    write(root/'key.json', key)
    assert verify_freeze() == FOUNDATION and historical_freeze() == ORIGINAL
    if len(rows) != 56 or sum(r['model_calls'] for r in rows) != 56:
        raise AssertionError('Generation coverage mismatch')
    print('Complete: 24 DEVELOPMENT episodes per condition, 56 generations. Neither holdout run.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output-dir', required=True)
    run(parser.parse_args())
