"""Frozen model-independent M8 context-selection evaluator.

decide_fn(case) -> mapping with:
  outcome      'direct' | 'context' | 'honest_empty' | 'unavailable'
  attempted    bool, whether local retrieval was called
  source_paths list of supplied passage source paths (empty unless outcome is 'context')
  reason       ContextDecision reason code
run_fn(failure_case) -> mapping containing at least every key of the case's expected mapping.
It never calls a model and makes no claim about answer correctness.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
OUTCOMES = frozenset({'direct', 'context', 'honest_empty', 'unavailable'})
# Labels name desired behavior; 'guided' means the M6 insufficient-material path is used,
# with or without passages, so the model is told what the local material lacks.
ALLOWED = {'direct': {'direct'}, 'context': {'context'}, 'guided': {'context', 'honest_empty'}}
EVIDENCE_PATH = frozenset({'context', 'honest_empty'})
PROJECT = ('explicit_project', 'implicit_project', 'location', 'rationale')
STRICT_NON_PROJECT = ('casual', 'creative', 'transformation', 'conversation_history')
GENERAL_NON_PROJECT = ('general_knowledge', 'current_information')
REPORTED_ONLY = ('multilingual',)

GATES = dict(accuracy_min=.85, missed_context_max=1, strict_false_supply_max=0,
             general_false_supply_max=2, honest_path_min=3, policy_errors_max=0)
CUE_TABLE_CAP = 60


def load(name):
    return [json.loads(line) for line in (ROOT/name).read_text(encoding='utf-8').splitlines()]


def evaluate(decide_fn, split=None):
    rows = []
    for case in load('cases.jsonl'):
        if split and case['split'] != split:
            continue
        observed = dict(decide_fn(case))
        if observed['outcome'] not in OUTCOMES:
            raise ValueError('Unknown outcome: ' + str(observed['outcome']))
        allowed = set().union(*(ALLOWED[label] for label in [case['expected'], *case['acceptable']]))
        paths = list(observed.get('source_paths', ()))
        rows.append(dict(id=case['id'], category=case['category'], split=case['split'],
            expected=case['expected'], outcome=observed['outcome'], attempted=bool(observed['attempted']),
            reason=observed['reason'], source_paths=paths, correct=observed['outcome'] in allowed,
            gold_supplied=bool(set(case['gold']) & set(paths)) if case['gold'] else None))

    def count(rows, categories, test):
        return sum(test(r) for r in rows if r['category'] in categories)

    def summarize(group):
        english = [r for r in group if r['category'] not in REPORTED_ONLY]
        should = [r for r in english if r['expected'] != 'direct']
        attempted = [r for r in english if r['attempted']]
        gold = [r for r in english if r['expected'] == 'context' and r['outcome'] == 'context']
        return dict(cases=len(group), english_cases=len(english),
            accuracy=sum(r['correct'] for r in english)/len(english) if english else None,
            missed_context=count(group, PROJECT, lambda r: r['outcome'] != 'context'),
            strict_false_supply=count(group, STRICT_NON_PROJECT, lambda r: r['outcome'] in EVIDENCE_PATH),
            general_false_supply=count(group, GENERAL_NON_PROJECT, lambda r: r['outcome'] in EVIDENCE_PATH),
            overlap_false_supply=count(group, ('accidental_overlap',), lambda r: r['outcome'] in EVIDENCE_PATH),
            honest_path=count(group, ('project_unavailable',), lambda r: r['outcome'] in EVIDENCE_PATH),
            attempt_recall=sum(r['attempted'] for r in should)/len(should) if should else None,
            attempt_precision=sum(r['expected'] != 'direct' for r in attempted)/len(attempted) if attempted else None,
            gold_coverage=sum(r['gold_supplied'] for r in gold)/len(gold) if gold else None,
            policy_errors=sum(r['reason'] == 'policy_error' for r in group),
            multilingual_correct=count(group, REPORTED_ONLY, lambda r: r['correct']))

    return dict(overall=summarize(rows),
        splits={key: summarize([r for r in rows if r['split'] == key]) for key in sorted({r['split'] for r in rows})},
        categories={key: summarize([r for r in rows if r['category'] == key]) for key in sorted({r['category'] for r in rows})},
        failures=[r for r in rows if not r['correct']], cases=rows)


def evaluate_failures(run_fn, fallback_adopted=True):
    rows = []
    for case in load('failures.jsonl'):
        expected = case['expected'] if fallback_adopted else case.get('expected_if_fallback_rejected', case['expected'])
        observed = dict(run_fn(case))
        mismatched = {key: (value, observed.get(key)) for key, value in expected.items() if observed.get(key) != value}
        rows.append(dict(id=case['id'], correct=not mismatched, mismatched=mismatched))
    return dict(correct=sum(r['correct'] for r in rows), cases=len(rows), rows=rows)


def gates(result, failure_result):
    """Apply the frozen gates to the full (both-split) result; holdout is scored once."""
    overall = result['overall']
    return dict(accuracy=overall['accuracy'] >= GATES['accuracy_min'],
        missed_context=overall['missed_context'] <= GATES['missed_context_max'],
        strict_false_supply=overall['strict_false_supply'] <= GATES['strict_false_supply_max'],
        general_false_supply=overall['general_false_supply'] <= GATES['general_false_supply_max'],
        honest_path=overall['honest_path'] >= GATES['honest_path_min'],
        policy_errors=overall['policy_errors'] <= GATES['policy_errors_max'],
        failures=failure_result['correct'] == failure_result['cases'])
