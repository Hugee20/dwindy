"""Frozen model-independent evaluator. search(query) returns ranked mappings."""
import json
from pathlib import Path

ROOT = Path(__file__).parent


def evaluate(search, split=None):
    results = []
    for line in (ROOT / 'queries.jsonl').read_text(encoding='utf-8').splitlines():
        case = json.loads(line)
        if split and case['split'] != split:
            continue
        matches = list(search(case['query']))[:3]
        rank = next((i for i, match in enumerate(matches, 1) if any(
            match['source_path'] == gold['source_path'] and
            match['start'] <= gold['start'] and match['end'] >= gold['end']
            for gold in case['gold'])), None)
        results.append(dict(id=case['id'], category=case['category'], split=case['split'],
            answerable=case['answerable'], rank=rank, returned=len(matches),
            paths=[m['source_path'] for m in matches],
            duplicates=len(matches)-len({m['text'] for m in matches})))

    def summarize(rows):
        positives = [r for r in rows if r['answerable']]
        total = len(positives)
        return dict(cases=len(rows), answerable=total,
            hit1=sum(r['rank'] == 1 for r in positives)/total if total else None,
            hit3=sum(r['rank'] is not None for r in positives)/total if total else None,
            mrr3=sum(1/r['rank'] if r['rank'] else 0 for r in positives)/total if total else None,
            negative_nonempty=sum(not r['answerable'] and r['returned'] > 0 for r in rows),
            duplicate_slots=sum(r['duplicates'] for r in rows))
    return dict(overall=summarize(results),
        categories={key:summarize([r for r in results if r['category']==key]) for key in sorted({r['category'] for r in results})},
        splits={key:summarize([r for r in results if r['split']==key]) for key in sorted({r['split'] for r in results})},
        cases=results)
