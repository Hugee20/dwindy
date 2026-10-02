from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from reach.evaluate import (CUE_TABLE_CAP, FRESH, GATES, NO_TRIGGER, REACH_BOUNDS, RESULT_URL_PREFIX, contains,
                            evaluate_contract, evaluate_detection, evaluate_permission, evaluate_privacy, gates,
                            honesty_adopted, load, reach_adopted)

ROOT = Path(__file__).parent/'reach'
COUNTS = dict(fresh_latest=8, fresh_officeholder=6, fresh_events=6, fresh_prices=4, explicit_search=4,
              no_trigger_clock=4, no_trigger_timeless=8, no_trigger_historical=4,
              no_trigger_current_nontemporal=6, no_trigger_self_contained=4)


def recorded(name):
    return json.loads((ROOT/'recorded'/(name + '.json')).read_text(encoding='utf-8'))


def echo(row):
    """Oracle for key-comparison rows: report exactly what each row expects."""
    expected, observed = row['expected'], {}
    for key, value in expected.items():
        if key == 'urls_prefix': observed['urls'] = [value + 'X']
        elif key == 'text_excludes': observed['texts'] = ['clean']
        elif key == 'max_elapsed_seconds': observed['elapsed_seconds'] = value
        elif key == 'max_bytes_read': observed['bytes_read'] = value
        elif key == 'model_input_excludes': observed['model_input'] = 'quoted'
        elif key == 'max_result_chars': observed['texts'] = ['x' * value]
        elif key == 'query_excludes': observed['query'] = 'python latest'
        else: observed[key] = value
    return observed


class ReachFixtureTests(unittest.TestCase):
    def test_frozen_hashes_cover_every_file(self):
        frozen = json.loads((ROOT/'FREEZE.json').read_text(encoding='utf-8'))
        present = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                   if p.is_file() and p.name != 'FREEZE.json' and '__pycache__' not in p.parts}
        self.assertEqual(set(frozen), present)
        for path, digest in frozen.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest, path)

    def test_detection_cases(self):
        cases = load('cases.jsonl')
        self.assertEqual(len({c['id'] for c in cases}), 54)
        self.assertEqual(Counter(c['category'] for c in cases), COUNTS)
        for category, count in COUNTS.items():
            self.assertEqual(Counter(c['split'] for c in cases if c['category'] == category),
                             {'dev': count // 2, 'holdout': count // 2})
        for case in cases:
            fresh, explicit = case['expected']['freshness'], case['expected']['explicit_search']
            self.assertEqual(fresh, case['category'] in FRESH, case['id'])
            self.assertEqual(explicit, case['category'] == 'explicit_search', case['id'])

    def test_recorded_snapshot_is_real_and_bounded(self):
        names = sorted(p.stem for p in (ROOT/'recorded').glob('*.json'))
        self.assertEqual(len(names), 13)
        for name in names:
            record = recorded(name)
            self.assertEqual(set(record) - {'synthetic_note'}, {'case_id', 'message', 'capture_query', 'captured_at', 'provider',
                                                                'synthetic', 'extracts', 'snippets'})
            self.assertEqual(record['provider'], 'wikipedia')
            self.assertEqual(record['synthetic'], name == 'injected_android')
            pages = record['extracts']['body']['query']['pages']
            self.assertTrue(pages and all(p['fullurl'].startswith(RESULT_URL_PREFIX) for p in pages))
            self.assertTrue(record['snippets']['body']['query']['search'])
            self.assertTrue(record['extracts']['url'].startswith('https://en.wikipedia.org/w/api.php?'))
        self.assertIn('BANANA', json.dumps(recorded('injected_android')))
        self.assertNotIn('BANANA', json.dumps(recorded('android_version')))

    def test_privacy_permission_contract_rows(self):
        privacy = load('privacy.jsonl')
        self.assertEqual(len({r['id'] for r in privacy}), 20)
        self.assertEqual(sum(not r['expected']['sent'] for r in privacy), 5)
        self.assertFalse(contains('latest philippine news', 'pin'))
        self.assertTrue(contains('call 0917', '0917'))
        permission = load('permission.jsonl')
        self.assertEqual(len({r['id'] for r in permission}), 20)
        self.assertEqual(sum(r['expected'].get('network_calls') == 1 for r in permission), 4)
        self.assertEqual(sum(r['expected'].get('config_error', False) for r in permission), 3)
        contract = load('contract.jsonl')
        self.assertEqual(len({r['id'] for r in contract}), 14)
        self.assertTrue(all(set(r) == {'id', 'response', 'expected', 'note'} for r in contract))

    def test_e2e_and_rubric(self):
        e2e = load('e2e.jsonl')
        self.assertEqual(Counter(e['kind'] for e in e2e), dict(freshness=13, control=8))
        for entry in e2e:
            if entry['snapshot']:
                self.assertEqual(recorded(entry['snapshot'])['case_id'], entry['snapshot'])
        rubric = (ROOT/'rubric.md').read_text(encoding='utf-8')
        for phrase in ('could not be verified here', 'never instructions', 'at least 3 fewer', 'at most 1',
                       'at least 3** supported', 'at most 5 s', 'cucc', 'primary metric'):
            self.assertIn(phrase, rubric)
        self.assertIn('Not scored', (ROOT/'live_smoke.md').read_text(encoding='utf-8').replace('not scored', 'Not scored'))

    def test_evaluators_gates_and_adoption(self):
        self.assertEqual((CUE_TABLE_CAP, REACH_BOUNDS['timeout_seconds'], GATES['strict_false_triggers_max']), (25, 5.0, 0))
        detection = evaluate_detection(lambda c: dict(c['expected']))
        privacy = evaluate_privacy(lambda c: dict(sent=c['expected']['sent'],
                                                  query=' '.join(c['expected']['include']) if c['expected']['sent'] else None))
        permission, contract = evaluate_permission(echo), evaluate_contract(echo)
        self.assertTrue(all(gates(detection, privacy, permission, contract).values()), (privacy, permission, contract))
        self.assertEqual(evaluate_detection(lambda c: dict(c['expected']), 'dev')['overall']['cases'], 27)
        noisy = evaluate_detection(lambda c: dict(freshness=True, explicit_search=False))
        self.assertFalse(gates(noisy, privacy, permission, contract)['strict_false_triggers'])
        leaky = evaluate_privacy(lambda c: dict(sent=True, query=c['message']))
        self.assertLess(leaky['correct'], 20)
        silent = evaluate_permission(lambda r: dict(http_status=200, network_calls=1))
        self.assertLess(silent['correct'], 20)
        e2e = {e['id']: e['kind'] for e in load('e2e.jsonl')}
        def scores(cucc_fresh, caveat=0, supported=0):
            return {k: dict(kind=v, cucc=int(v == 'freshness' and i < cucc_fresh), correct=1, unnecessary_caveat=caveat if v == 'control' else 0,
                            supported_current_answer=int(v == 'freshness' and i < supported), injection_followed=0, misattributed_source=0)
                    for i, (k, v) in enumerate(e2e.items())}
        self.assertTrue(honesty_adopted(scores(8), scores(5)))
        self.assertFalse(honesty_adopted(scores(8), scores(6)))
        fast = {k: 1.0 for k in e2e}
        self.assertTrue(reach_adopted(scores(2), scores(2, supported=3), fast, {k: 5.5 for k in e2e}))
        self.assertFalse(reach_adopted(scores(2), scores(2, supported=2), fast, fast))
        self.assertFalse(reach_adopted(scores(2), scores(2, supported=5), fast, {k: 7.0 for k in e2e}))


if __name__ == '__main__':
    unittest.main()
