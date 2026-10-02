import ast
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from tools.evaluate import (CUE_TABLE_CAP, GATES, HOST_CONTEXT_LIMITS, OUTCOMES, calculator_adopted,
                            evaluate, evaluate_host, gates, load, same_value)

ROOT = Path(__file__).parent/'tools'
COUNTS = dict(arithmetic=14, numeric_no_trigger=16, adversarial_expression=8, clock=8,
              clock_no_trigger=8, mixed=4, self_contained=2)


def exact(expression):
    """Test-only exact check of a label's canonical expression: + - * / ** on literals."""
    def walk(node):
        if isinstance(node, ast.Expression): return walk(node.body)
        if isinstance(node, ast.Constant): return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub): return -walk(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left), walk(node.right)
            return {ast.Add: a + b, ast.Sub: a - b, ast.Mult: a * b}.get(type(node.op)) if not isinstance(
                node.op, (ast.Div, ast.Pow)) else (a / b if isinstance(node.op, ast.Div) else a ** int(b))
        raise ValueError(ast.dump(node))
    return walk(ast.parse(expression, mode='eval'))


def oracle(case):
    expected = case['expected']
    return dict(calculator=expected['calculator'], value=expected['value'], clock=expected['clock'])


def host_oracle(row):
    expected = row['expected']
    observed = {k: expected[k] for k in ('http_status', 'error_code', 'host_context_supplied') if k in expected}
    observed.update(model_input=' '.join(expected.get('model_input_contains', [])), persisted='', resumed_input='',
                    capabilities=[])
    return observed


class ToolsFixtureTests(unittest.TestCase):
    def test_frozen_hashes_cover_every_file(self):
        frozen = json.loads((ROOT/'FREEZE.json').read_text(encoding='utf-8'))
        present = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                   if p.is_file() and p.name != 'FREEZE.json' and '__pycache__' not in p.parts}
        self.assertEqual(set(frozen), present)
        for path, digest in frozen.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest, path)

    def test_cases_composition_split_and_exact_labels(self):
        cases = load('cases.jsonl')
        self.assertEqual(len({c['id'] for c in cases}), 60)
        self.assertEqual(Counter(c['category'] for c in cases), COUNTS)
        for category, count in COUNTS.items():
            subset = [c for c in cases if c['category'] == category]
            self.assertEqual(Counter(c['split'] for c in subset), {'dev': count // 2, 'holdout': count // 2})
        for case in cases:
            expected = case['expected']
            self.assertIn(expected['calculator'], OUTCOMES)
            self.assertIsInstance(expected['clock'], bool)
            if expected['calculator'] == 'result':
                self.assertEqual(Fraction(expected['value']), exact(expected['expression']), case['id'])
                self.assertTrue(same_value(expected['value'], expected['value']))
            else:
                self.assertIsNone(expected['value'])
            self.assertTrue(case['message'].strip() and case['note'].strip())
        self.assertTrue(all(c['expected']['clock'] for c in cases if c['category'] == 'clock'))
        self.assertFalse(any(c['expected']['clock'] for c in cases if c['category'] == 'clock_no_trigger'))

    def test_host_context_rows_and_contract(self):
        rows = load('host_context.jsonl')
        self.assertEqual(len({r['id'] for r in rows}), 16)
        self.assertEqual(HOST_CONTEXT_LIMITS, dict(max_items=8, max_label_chars=64, max_text_chars=2000,
                                                   max_total_text_chars=4000, budget_tokens=1024))
        for row in rows:
            self.assertEqual(set(row), {'id', 'note', 'token_configured', 'authenticated', 'body', 'expected'})
            self.assertIn('http_status', row['expected'])
        statuses = Counter(r['expected']['http_status'] for r in rows)
        self.assertEqual(statuses, {200: 6, 401: 1, 403: 1, 422: 8})
        action = next(r for r in rows if 'Renew' in r['body']['message'])
        self.assertIn('action', action['expected']['capabilities_exclude'])

    def test_e2e_and_rubric(self):
        e2e = load('e2e.jsonl')
        self.assertEqual(Counter(e['kind'] for e in e2e), dict(arithmetic=10, clock=4, host=6, mixed=2))
        cases = {c['id']: c for c in load('cases.jsonl')}
        for entry in e2e:
            if entry['case_id']:
                self.assertEqual(entry['message'], cases[entry['case_id']]['message'])
            if entry['kind'] == 'arithmetic':
                self.assertIn(cases[entry['case_id']]['expected']['value'], entry['correct_if'])
        self.assertEqual(sum('host_context' in e for e in e2e), 7)
        rubric = (ROOT/'rubric.md').read_text(encoding='utf-8')
        for phrase in ('at least 2', 'breaks **no** answer', 'server-local', 'not shipped'):
            self.assertIn(phrase, rubric)

    def test_evaluator_gates_and_adoption_rule(self):
        self.assertEqual((CUE_TABLE_CAP, GATES['strict_false_triggers_max']), (30, 0))
        host = evaluate_host(host_oracle)
        self.assertEqual(host['correct'], 16)
        self.assertTrue(all(gates(evaluate(oracle), host).values()))
        self.assertEqual(evaluate(oracle, 'dev')['overall']['cases'], 30)
        silent = gates(evaluate(lambda c: dict(calculator='none', value=None, clock=False)), host)
        self.assertFalse(silent['calculator_exact'] or silent['clock_recall'])
        noisy = gates(evaluate(lambda c: dict(calculator='result', value='1', clock=True)), host)
        self.assertFalse(noisy['strict_false_triggers'] or noisy['clock_false_triggers'])
        with self.assertRaises(ValueError):
            evaluate(lambda c: dict(calculator='maybe', value=None, clock=False))
        ids = [f'a{i}' for i in range(10)]
        off = {k: i < 6 for i, k in enumerate(ids)}
        self.assertTrue(calculator_adopted(off, {k: True for k in ids}))
        self.assertFalse(calculator_adopted(off, {k: i < 7 for i, k in enumerate(ids)}))     # gain of 1
        self.assertFalse(calculator_adopted(off, {k: i != 0 for i, k in enumerate(ids)}))    # one regression
        self.assertFalse(calculator_adopted({k: True for k in ids}, {k: True for k in ids}))  # nothing to fix


if __name__ == '__main__':
    unittest.main()
