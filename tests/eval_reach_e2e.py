"""Real-model M10 comparison over the frozen e2e set (tests/reach/rubric.md). Never contacts a provider.

Conditions: A baseline (M9 behavior), B offline honesty, C Reach replaying the recorded snapshot.
Writes results.jsonl, a shuffled blind sheet.md and a separate key.json into a new directory.
"""
import argparse
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import random
import secrets
import time
from unittest.mock import patch

from dwindy import capabilities
from reach_history_support import reach, module
from dwindy.backend import TextDelta
from dwindy.config import load_config
from dwindy.context_policy import decide as select_context
DwindyCore = module("core").DwindyCore
Facts = module("evidence").Facts
from dwindy.llama_backend import LlamaBackend
from context_run import fixture_index
from reach.evaluate import load
from reach_support import ReplayTransport, combined_body, no_network


def generate(backend, config, index, case, condition):
    name = index.project_snapshot['name']
    decision, evidence = select_context(case['message'], 'auto', search=index.search, project_name=name)
    computed = capabilities.select(case['message'])
    facts = Facts(tuple((f.name, f.text) for f in computed))
    reach_decision, notice, web = None, None, None
    if condition == 'B':
        reach_decision, _, notice = reach.decide(case['message'], 'off')
    elif condition == 'C':
        replay = ReplayTransport(combined_body(case['snapshot'])) if case['snapshot'] else ReplayTransport(error='reach_unavailable')
        reach_decision, web, notice = reach.decide(case['message'], 'auto', backend=reach.WikipediaBackend(transport=replay),
                                                   project_name=name, local_supplied=evidence is not None,
                                                   max_tokens=768)
    core = DwindyCore(backend, options=config.options(), system_prompt=config.system_prompt)
    start, first, text = time.perf_counter(), None, []
    with closing(core.chat(case['message'], evidence=web or evidence, facts=facts, notice=notice)) as stream:
        for event in stream:
            if isinstance(event, TextDelta):
                if first is None and event.text.strip():
                    first = time.perf_counter() - start
                text.append(event.text)
    shown = [dict(title=p.source.name, url=p.source.source_path, text=p.text) for p in (web.passages if web else ())]
    return dict(text=''.join(text), reach=reach_decision.metadata() if reach_decision else None, notice=bool(notice),
                results_shown=shown, server_local_time=f'{datetime.now().astimezone():%Y-%m-%d %H:%M %z}',
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
                for condition in ('A', 'B', 'C'):
                    rows.append(dict(case_id=case['id'], kind=case['kind'], condition=condition,
                                     **generate(backend, config, index, case, condition)))
                print(case['id'], flush=True)
    finally:
        backend.close()
    by_case = {c['id']: c for c in cases}
    for row in rows:
        row['forbidden_found'] = [f for f in by_case[row['case_id']]['forbidden'] if f.upper() in row['text'].upper()]
    (output/'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    order = list(range(len(rows))); random.Random(secrets.randbits(64)).shuffle(order)
    key, sheet = {}, ['# Blind scoring sheet (M10)', '', 'Score each answer with tests/reach/rubric.md. Do not open key.json first.', '']
    for i in order:
        token, row = secrets.token_hex(4), rows[i]
        case = by_case[row['case_id']]
        key[token] = dict(case_id=row['case_id'], condition=row['condition'])
        results = ''.join(f"> **{r['title']}** ({r['url']}): {r['text']}\n>\n" for r in row['results_shown']) or '> *(none)*\n'
        sheet += [f'## {token}', '', f"**Message:** {case['message']}  ", f"**Kind:** {case['kind']}", '',
                  '**External results the model saw:**', '', results, f"**Correct if:** {case['correct_if']}", '',
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
