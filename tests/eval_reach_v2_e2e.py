"""Recorded real-model Reach v2 comparison (tests/reach_v2/rubric.md). Never contacts a provider.

Conditions: B offline honesty, C1 Reach v1 (whole results), C2 Reach v2 (H1 sentences). Writes
results.jsonl, a shuffled blind sheet.md and a separate key.json. It does not decide adoption.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import random
import secrets
import time
from unittest.mock import patch

from dwindy import capabilities, reach
from dwindy.backend import Message, TextDelta
from dwindy.config import load_config
from dwindy.context_policy import decide as select_context
from dwindy.core import DwindyCore
from dwindy.evidence import Facts, evidence_question
from dwindy.llama_backend import LlamaBackend
from context_run import fixture_index
from reach_support import ReplayTransport, combined_body, no_network
from reach_v2.evaluate import load

HOLDOUT = Path(__file__).parent/'reach_v2'/'holdout'


def body_for(snapshot):
    if snapshot['source'] == 'v1':
        return combined_body(snapshot['id'])
    return json.loads((HOLDOUT/(snapshot['id'] + '.json')).read_text(encoding='utf-8'))['body']


def generate(backend, config, index, case, condition):
    name = index.project_snapshot['name']
    decision, evidence = select_context(case['message'], 'auto', search=index.search, project_name=name)
    facts = Facts(tuple((f.name, f.text) for f in capabilities.select(case['message'])))
    relevant = reach.local_relevant(decision, evidence)
    if condition == 'B':
        reach_decision, web, notice = reach.decide(case['message'], 'off', project_name=name, local_relevant=relevant)
    else:
        replay = ReplayTransport(body_for(case['snapshot'])) if case['snapshot'] else ReplayTransport(error='reach_unavailable')
        with patch.object(reach, 'EVIDENCE_UNIT', 'results' if condition == 'C1' else 'sentences'):
            reach_decision, web, notice = reach.decide(case['message'], 'auto', backend=reach.WikipediaBackend(transport=replay),
                                                       project_name=name, local_supplied=evidence is not None,
                                                       local_relevant=relevant, max_tokens=768)
    shown, chars, tokens = [], 0, 0
    if web is not None:
        shown = [dict(title=p.source.name, url=p.source.source_path, text=p.text) for p in web.passages]
        chars = sum(len(p.text) for p in web.passages)
        block = evidence_question('', list(web.passages), web.framing, web.origin)
        tokens = backend.count_tokens([Message('user', block)]) - backend.count_tokens([Message('user', '')])
    core = DwindyCore(backend, options=config.options(), system_prompt=config.system_prompt)
    start, first, text = time.perf_counter(), None, []
    with closing(core.chat(case['message'], evidence=web or evidence, facts=facts, notice=notice)) as stream:
        for event in stream:
            if isinstance(event, TextDelta):
                if first is None and event.text.strip():
                    first = time.perf_counter() - start
                text.append(event.text)
    return dict(text=''.join(text), reach=reach_decision.metadata() if reach_decision else None, notice=bool(notice),
                evidence_shown=shown, evidence_chars=chars, evidence_tokens=tokens,
                first_visible_seconds=first, end_to_end_seconds=time.perf_counter() - start)


def run(args):
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    config = load_config(args.config)
    backend = LlamaBackend(config)
    cases, rows = load('e2e.jsonl'), []
    try:
        with fixture_index() as index, no_network(allow_loopback=True), \
                patch.object(reach, 'HONESTY_ADOPTED', True), patch.object(reach, 'REACH_ADOPTED', True):
            for case in cases:
                for condition in ('B', 'C1', 'C2'):
                    rows.append(dict(case_id=case['id'], kind=case['kind'], split=case['split'], condition=condition,
                                     **generate(backend, config, index, case, condition)))
                print(case['id'], flush=True)
    finally:
        backend.close()
    by_case = {c['id']: c for c in cases}
    for row in rows:
        row['forbidden_found'] = [f for f in by_case[row['case_id']]['forbidden'] if f.upper() in row['text'].upper()]
    (output/'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    order = list(range(len(rows))); random.Random(secrets.randbits(64)).shuffle(order)
    key, sheet = {}, ['# Blind scoring sheet (Reach v2)', '', 'Score each answer with tests/reach_v2/rubric.md. Do not open key.json first.', '']
    for i in order:
        token, row = secrets.token_hex(4), rows[i]
        case = by_case[row['case_id']]
        key[token] = dict(case_id=row['case_id'], condition=row['condition'], split=row['split'])
        seen = ''.join(f"> **{e['title']}** ({e['url']}): {e['text']}\n>\n" for e in row['evidence_shown']) or '> *(none)*\n'
        sheet += [f'## {token}', '', f"**Message:** {case['message']}  ", f"**Kind:** {case['kind']}", '',
                  '**External evidence the model saw:**', '', seen, f"**Correct if:** {case['correct_if']}", '',
                  '```text', row['text'].strip(), '```', '',
                  'correct: ___ cucc: ___ supported_current_answer: ___ unnecessary_caveat: ___ '
                  'injection_followed: ___ misattributed_source: ___', '']
    (output/'sheet.md').write_text('\n'.join(sheet), encoding='utf-8')
    (output/'key.json').write_text(json.dumps(key, indent=2), encoding='utf-8')
    print(json.dumps(dict(generations=len(rows), output=str(output)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, help='Unchanged non-thinking model configuration')
    parser.add_argument('--output-dir', required=True, help='New directory, e.g. under eval-results/')
    run(parser.parse_args())
