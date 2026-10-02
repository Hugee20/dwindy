"""Frozen model-independent M9 deterministic-capability evaluator.

detect_fn(case) -> mapping with:
  calculator  'result' | 'undefined' | 'rejected' | 'none'
  value       exact result as a decimal string when calculator == 'result', else None
  clock       bool, whether the server-local clock fact would be supplied
run_fn(host_row) -> mapping with any of: http_status, error_code, host_context_supplied,
  model_input (str), persisted (str), resumed_input (str), capabilities (list of names).
It never calls a model and makes no claim about answer correctness.
"""
from decimal import Decimal
import json
from pathlib import Path

ROOT = Path(__file__).parent
OUTCOMES = frozenset({'result', 'undefined', 'rejected', 'none'})
NO_TRIGGER_STRICT = ('numeric_no_trigger', 'self_contained')

# Contract and bounds frozen with this evaluation.
CUE_TABLE_CAP = 30            # Clock cues plus calculator word operators, all entries counted.
CALCULATOR_BOUNDS = dict(max_expression_chars=200, max_number_digits=30, max_nesting=10,
                         max_abs_exponent=100, max_result_digits=100, precision_digits=28)
HOST_CONTEXT_LIMITS = dict(max_items=8, max_label_chars=64, max_text_chars=2000,
                           max_total_text_chars=4000, budget_tokens=1024)
GATES = dict(calculator_exact=1.0, strict_false_triggers_max=0, adversarial_correct=1.0,
             clock_recall_min=0.9, clock_false_triggers_max=1)
# Calculator adoption (rubric.md): over the 10 real-model arithmetic cases, the capability
# must fix at least this many answers and break none.
CALCULATOR_MIN_GAIN = 2


def load(name):
    return [json.loads(line) for line in (ROOT/name).read_text(encoding='utf-8').splitlines()]


def same_value(observed, expected):
    try:
        a, b = Decimal(observed), Decimal(expected)
    except Exception:
        return False
    return abs(a - b) <= Decimal('1e-12') * max(Decimal(1), abs(b))


def evaluate(detect_fn, split=None):
    rows = []
    for case in load('cases.jsonl'):
        if split and case['split'] != split:
            continue
        observed = dict(detect_fn(case))
        if observed['calculator'] not in OUTCOMES:
            raise ValueError('Unknown calculator outcome: ' + str(observed['calculator']))
        expected = case['expected']
        calc_ok = observed['calculator'] == expected['calculator'] and (
            expected['calculator'] != 'result' or same_value(observed.get('value'), expected['value']))
        rows.append(dict(id=case['id'], category=case['category'], split=case['split'],
            expected=expected, observed=observed, calculator_correct=calc_ok,
            clock_correct=bool(observed['clock']) == expected['clock']))

    def summarize(group):
        results = [r for r in group if r['expected']['calculator'] == 'result']
        adversarial = [r for r in group if r['category'] == 'adversarial_expression']
        clock = [r for r in group if r['expected']['clock']]
        return dict(cases=len(group),
            calculator_exact=sum(r['calculator_correct'] for r in results)/len(results) if results else None,
            strict_false_triggers=sum(r['observed']['calculator'] != 'none' for r in group if r['category'] in NO_TRIGGER_STRICT),
            other_false_triggers=sum(r['observed']['calculator'] != 'none' for r in group
                                     if r['expected']['calculator'] == 'none' and r['category'] not in NO_TRIGGER_STRICT),
            adversarial_correct=sum(r['calculator_correct'] for r in adversarial)/len(adversarial) if adversarial else None,
            clock_recall=sum(bool(r['observed']['clock']) for r in clock)/len(clock) if clock else None,
            clock_false_triggers=sum(bool(r['observed']['clock']) for r in group if r['category'] == 'clock_no_trigger'),
            other_clock_false_triggers=sum(bool(r['observed']['clock']) for r in group
                                           if not r['expected']['clock'] and r['category'] != 'clock_no_trigger'))

    return dict(overall=summarize(rows),
        splits={k: summarize([r for r in rows if r['split'] == k]) for k in sorted({r['split'] for r in rows})},
        categories={k: summarize([r for r in rows if r['category'] == k]) for k in sorted({r['category'] for r in rows})},
        failures=[r for r in rows if not (r['calculator_correct'] and r['clock_correct'])], cases=rows)


def evaluate_host(run_fn):
    rows = []
    for row in load('host_context.jsonl'):
        observed, expected, problems = dict(run_fn(row)), row['expected'], []
        for key in ('http_status', 'error_code', 'host_context_supplied'):
            if key in expected and observed.get(key) != expected[key]:
                problems.append((key, expected[key], observed.get(key)))
        checks = dict(model_input_contains=('model_input', True), model_input_excludes=('model_input', False),
                      persisted_excludes=('persisted', False), resumed_excludes=('resumed_input', False),
                      capabilities_exclude=('capabilities', False))
        for key, (field, present) in checks.items():
            for item in expected.get(key, ()):
                if (item in (observed.get(field) or '')) != present:
                    problems.append((key, item, field))
        rows.append(dict(id=row['id'], correct=not problems, problems=problems))
    return dict(correct=sum(r['correct'] for r in rows), cases=len(rows), rows=rows)


def gates(result, host_result):
    """Apply the frozen gates to the full (both-split) result; holdout is scored once."""
    overall = result['overall']
    return dict(calculator_exact=overall['calculator_exact'] >= GATES['calculator_exact'],
        strict_false_triggers=overall['strict_false_triggers'] <= GATES['strict_false_triggers_max'],
        adversarial=overall['adversarial_correct'] >= GATES['adversarial_correct'],
        clock_recall=overall['clock_recall'] >= GATES['clock_recall_min'],
        clock_false_triggers=overall['clock_false_triggers'] <= GATES['clock_false_triggers_max'],
        host_context=host_result['correct'] == host_result['cases'])


def calculator_adopted(off_correct, on_correct):
    """off_correct/on_correct map each real-model arithmetic case id to True/False."""
    gain = sum(on_correct[k] and not off_correct[k] for k in off_correct)
    regressions = sum(off_correct[k] and not on_correct[k] for k in off_correct)
    return gain >= CALCULATOR_MIN_GAIN and regressions == 0
