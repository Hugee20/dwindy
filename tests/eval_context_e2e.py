"""Real-model M8 comparison over the frozen e2e set (tests/context/rubric.md). Never runs M1 eval.

Writes results.jsonl, a shuffled blind scoring sheet (sheet.md) and a separate key.json into
a new output directory. Conditions: oracle explicit selection, auto, forced on, off; plus the
four injected project-directed failure cases under auto.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import random
import secrets
import time

from dwindy.backend import Message, TextDelta
from dwindy.config import load_config
from dwindy.context_policy import CONSTRAINED_FALLBACK, decide
from dwindy.core import DwindyCore, TurnStarted
from dwindy.llama_backend import LlamaBackend
from dwindy.retrieval import RetrievalError
from context.evaluate import load
from context_run import fixture_index

CONDITIONS = ('oracle', 'auto', 'on', 'off')


def generate(backend, config, case, mode, search, project_name):
    core = DwindyCore(backend, options=config.options(), system_prompt=config.system_prompt)
    core.restore([Message(role, turn[role]) for turn in case['history'] for role in ('user', 'assistant')])
    start = time.perf_counter(); first = None; text = []
    decision, evidence = decide(case['message'], mode, search=search, project_name=project_name)
    with closing(core.chat(case['message'], evidence=evidence)) as stream:
        for event in stream:
            if isinstance(event, TurnStarted):
                metadata = decision.metadata(event.retrieval)
            elif isinstance(event, TextDelta):
                if first is None and event.text.strip():
                    first = time.perf_counter() - start
                text.append(event.text)
    return dict(text=''.join(text), retrieval=metadata, first_visible_seconds=first,
                end_to_end_seconds=time.perf_counter() - start)


def run(args):
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    config = load_config(args.config)
    backend = LlamaBackend(config)
    rows = []
    try:
        with fixture_index() as index:
            name = index.project_snapshot['name']
            for case in load('e2e.jsonl'):
                if case['kind'] == 'case':
                    for condition in CONDITIONS:
                        mode = ('on' if case['oracle_retrieval'] else 'off') if condition == 'oracle' else condition
                        rows.append(dict(case_id=case['case_id'], condition=condition, mode=mode,
                                         **generate(backend, config, case, mode, index.search, name)))
                else:
                    def failing(*_, code=case['inject']):
                        raise RetrievalError(code)
                    rows.append(dict(case_id=case['case_id'], condition='failure', mode='auto',
                                     constrained_fallback=CONSTRAINED_FALLBACK,
                                     **generate(backend, config, case, 'auto', failing, name)))
                print(case['id'], flush=True)
    finally:
        backend.close()
    cases = {c['case_id']: c for c in load('e2e.jsonl')}
    for row in rows:
        row['forbidden_found'] = [f for f in cases[row['case_id']]['forbidden'] if f.upper() in row['text'].upper()]
    (output/'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    order = list(range(len(rows))); random.Random(secrets.randbits(64)).shuffle(order)
    key, sheet = {}, ['# Blind scoring sheet', '', 'Score each answer with tests/context/rubric.md. Do not open key.json first.', '']
    for i in order:
        token = secrets.token_hex(4)
        row, case = rows[i], cases[rows[i]['case_id']]
        key[token] = dict(case_id=row['case_id'], condition=row['condition'])
        history = ''.join(f"> **User:** {t['user']}\n>\n> **Assistant:** {t['assistant']}\n>\n" for t in case['history'])
        sheet += [f'## {token}', '', history + f"**Message:** {case['message']}", '',
                  f"**Correct if:** {case['correct_if']}  ", f"**Unsupported project claim if:** {case['unsupported_project_claim_if']}", '',
                  '```text', row['text'].strip(), '```', '',
                  'correct: ___ unsupported_project_claim: ___ unnecessary_refusal: ___ injection_followed: ___' +
                  (' disclosed_unavailable: ___' if case['kind'] == 'failure' else ''), '']
    (output/'sheet.md').write_text('\n'.join(sheet), encoding='utf-8')
    (output/'key.json').write_text(json.dumps(key, indent=2), encoding='utf-8')
    print(json.dumps(dict(generations=len(rows), output=str(output)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, help='Unchanged non-thinking model configuration')
    parser.add_argument('--output-dir', required=True, help='New directory, e.g. under eval-results/')
    run(parser.parse_args())
