"""Run the frozen M9 capability evaluation (development split unless asked otherwise)."""
import argparse
import json

from dwindy.capabilities import detect
from tools.evaluate import evaluate


def detect_fn(case):
    calculation, clock = detect(case['message'])
    return dict(calculator=calculation.outcome, value=calculation.value, clock=clock)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['dev', 'holdout', 'all'], default='dev')
    args = parser.parse_args()
    result = evaluate(detect_fn, None if args.split == 'all' else args.split)
    print(json.dumps({k: result[k] for k in ('overall', 'splits')}, indent=2))
    for case in result['cases']:
        flag = '' if case['calculator_correct'] and case['clock_correct'] else '  <-- MISS'
        print(f"{case['id']:28} calc={case['observed']['calculator']:9} value={case['observed']['value']!s:14} "
              f"clock={case['observed']['clock']!s:5} expected={case['expected']['calculator']}/{case['expected']['clock']}{flag}")
