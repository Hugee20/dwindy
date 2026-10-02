"""Real-model M9 comparison over the frozen e2e set (tests/tools/rubric.md). Never runs M1 eval.

Each case runs with capabilities off (baseline) and on. Writes results.jsonl, a shuffled blind
sheet.md, a separate key.json and adoption.json, which applies the frozen calculator rule to
a mechanical exact-value check, into a new output directory.
"""
import argparse
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import random
import re
import secrets
import time

from dwindy import capabilities
from dwindy.backend import TextDelta
from dwindy.config import load_config
from dwindy.core import DwindyCore
from dwindy.evidence import Facts
from dwindy.llama_backend import LlamaBackend
from tools.evaluate import calculator_adopted, load


def generate(backend, config, case, condition):
    core = DwindyCore(backend, options=config.options(), system_prompt=config.system_prompt)
    now = datetime.now().astimezone()
    facts, used = Facts(), []
    if condition == 'on':
        computed = capabilities.select(case['message'], now)  # Calculator measured as if adopted.
        host = tuple((item['label'], item['text']) for item in case.get('host_context', ()))
        facts = Facts(tuple((f.name, f.text) for f in computed), host)
        used = [f.metadata for f in computed] + ([dict(name='host_context', items=len(host))] if host else [])
    start, first, text = time.perf_counter(), None, []
    with closing(core.chat(case['message'], facts=facts)) as stream:
        for event in stream:
            if isinstance(event, TextDelta):
                if first is None and event.text.strip():
                    first = time.perf_counter() - start
                text.append(event.text)
    return dict(text=''.join(text), capabilities=used, server_local_time=f'{now:%A, %Y-%m-%d %H:%M %z}',
                first_visible_seconds=first, end_to_end_seconds=time.perf_counter() - start)


def states_value(answer, value):
    """Mechanical arithmetic check: the exact expected value appears as a number in the answer."""
    numbers = {n.replace(',', '').rstrip('.') for n in re.findall(r'-?\d[\d,]*(?:\.\d+)?', answer)}
    return value in numbers or any(n.endswith('.0') and n[:-2] == value for n in numbers)


def run(args):
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    config = load_config(args.config)
    backend = LlamaBackend(config)
    cases, rows = load('e2e.jsonl'), []
    try:
        with patch_adopted():
            for case in cases:
                for condition in ('off', 'on'):
                    rows.append(dict(case_id=case['id'], kind=case['kind'], condition=condition,
                                     **generate(backend, config, case, condition)))
                print(case['id'], flush=True)
    finally:
        backend.close()
    by_case = {case['id']: case for case in cases}
    expected = {c['id']: c['expected']['value'] for c in load('cases.jsonl') if c['expected']['calculator'] == 'result'}
    for row in rows:
        case = by_case[row['case_id']]
        row['forbidden_found'] = [f for f in case['forbidden'] if f.upper() in row['text'].upper()]
        if row['kind'] == 'arithmetic':
            row['states_expected_value'] = states_value(row['text'], expected[case['case_id']])
    (output/'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    arithmetic = [r for r in rows if r['kind'] == 'arithmetic']
    off = {r['case_id']: r['states_expected_value'] for r in arithmetic if r['condition'] == 'off'}
    on = {r['case_id']: r['states_expected_value'] for r in arithmetic if r['condition'] == 'on'}
    (output/'adoption.json').write_text(json.dumps(dict(
        off_correct=sum(off.values()), on_correct=sum(on.values()),
        fixed=[k for k in off if on[k] and not off[k]], broken=[k for k in off if off[k] and not on[k]],
        calculator_adopted_by_rule=calculator_adopted(off, on),
        note='Mechanical exact-value check; blind scoring of sheet.md may confirm it.'), indent=2), encoding='utf-8')
    order = list(range(len(rows))); random.Random(secrets.randbits(64)).shuffle(order)
    key, sheet = {}, ['# Blind scoring sheet (M9)', '', 'Score each answer with tests/tools/rubric.md. Do not open key.json first.', '']
    for i in order:
        token, row = secrets.token_hex(4), rows[i]
        case = by_case[row['case_id']]
        key[token] = dict(case_id=row['case_id'], condition=row['condition'])
        supplied = case.get('host_context') if row['condition'] == 'on' else None
        host = ''.join(f"> **{item['label']}:** {item['text']}\n" for item in supplied or ()) or '> *(none)*\n'
        sheet += [f'## {token}', '', f"**Message:** {case['message']}", '',
                  f"**Server-local time at generation:** {row['server_local_time']}", '', '**Host context supplied:**', '', host,
                  f"**Correct if:** {case['correct_if']}  ", f"**Unsupported claim if:** {case['unsupported_claim_if']}", '',
                  '```text', row['text'].strip(), '```', '',
                  'correct: ___ unsupported_claim: ___ injection_followed: ___ action_claimed: ___', '']
    (output/'sheet.md').write_text('\n'.join(sheet), encoding='utf-8')
    (output/'key.json').write_text(json.dumps(key, indent=2), encoding='utf-8')
    print(json.dumps(dict(generations=len(rows), output=str(output)), indent=2))


class patch_adopted:
    """Measure the calculator as if adopted, whatever the shipped constant says."""
    def __enter__(self):
        self.saved, capabilities.CALCULATOR_ADOPTED = capabilities.CALCULATOR_ADOPTED, True

    def __exit__(self, *exc):
        capabilities.CALCULATOR_ADOPTED = self.saved


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, help='Unchanged non-thinking model configuration')
    parser.add_argument('--output-dir', required=True, help='New directory, e.g. under eval-results/')
    run(parser.parse_args())
