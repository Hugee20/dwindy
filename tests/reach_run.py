"""Run the frozen M10 detection and privacy evaluation (development split unless asked otherwise)."""
import argparse
import json

from dwindy import reach
from reach.evaluate import evaluate_detection, evaluate_privacy


def detect_fn(case):
    fresh, explicit = reach.detect(case['message'])
    return dict(freshness=fresh, explicit_search=explicit)


def minimize_fn(case):
    context = case['context']
    query, _ = reach.minimize(case['message'], host_texts=[i['text'] for i in context['host_context']],
                              project_name=context['project_name'])
    return dict(sent=query is not None, query=query)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['dev', 'holdout', 'all'], default='dev')
    args = parser.parse_args()
    detection = evaluate_detection(detect_fn, None if args.split == 'all' else args.split)
    print(json.dumps(dict(overall=detection['overall'], splits=detection['splits']), indent=2))
    for case in detection['failures']:
        print('DETECTION MISS', case['id'], case['message'] if 'message' in case else '', case['observed'])
    privacy = evaluate_privacy(minimize_fn)
    print('privacy', privacy['correct'], '/', privacy['cases'])
    for row in privacy['rows']:
        print(f"  {row['id']:11} {'ok ' if row['correct'] else 'BAD'} query={row['query']!r} {row['problems'] or ''}")
