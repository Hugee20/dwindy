from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
import unittest

try:
    import pathspec  # noqa: F401  Optional dwindy[project] dependency.
except ImportError:
    pathspec = None

sys.path.insert(0, str(Path(__file__).parent))
from context.evaluate import ALLOWED, CUE_TABLE_CAP, GATES, evaluate, evaluate_failures, gates, load
from project_support import load as load_project, materialize

ROOT = Path(__file__).parent/'context'
CATEGORIES = ('casual', 'creative', 'transformation', 'explicit_project', 'implicit_project', 'location',
              'rationale', 'project_unavailable', 'accidental_overlap', 'general_knowledge',
              'current_information', 'conversation_history', 'adversarial', 'multilingual')


def extra_paths():
    manifest = tomllib.loads((ROOT/'extra/collection.toml').read_text(encoding='utf-8'))
    return {entry['path'] for entry in manifest['documents']}


def oracle(case):
    outcome = {'direct': 'direct', 'context': 'context', 'guided': 'honest_empty'}[case['expected']]
    return dict(outcome=outcome, attempted=outcome != 'direct', source_paths=case['gold'][:1], reason='oracle')


class ContextFixtureTests(unittest.TestCase):
    def test_frozen_hashes_cover_every_file(self):
        frozen = json.loads((ROOT/'FREEZE.json').read_text(encoding='utf-8'))
        present = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                   if p.is_file() and p.name != 'FREEZE.json' and '__pycache__' not in p.parts}
        self.assertEqual(set(frozen), present)
        for path, digest in frozen.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest, path)

    def test_cases_composition_splits_and_labels(self):
        cases = load('cases.jsonl')
        self.assertEqual(len(cases), 56)
        self.assertEqual(len({c['id'] for c in cases}), 56)
        self.assertEqual(Counter(c['category'] for c in cases), {c: 4 for c in CATEGORIES})
        for split in ('dev', 'holdout'):
            subset = [c for c in cases if c['split'] == split]
            self.assertEqual(len(subset), 28)
            self.assertEqual(Counter(c['category'] for c in subset), {c: 2 for c in CATEGORIES})
        known = set(load_project('files.json')) | extra_paths()
        for case in cases:
            self.assertIn(case['expected'], ALLOWED)
            self.assertTrue(set(case['acceptable']) <= ALLOWED.keys())
            self.assertEqual(bool(case['gold']), case['expected'] == 'context', case['id'])
            self.assertTrue(set(case['gold']) <= known, case['id'])
            self.assertTrue(case['message'].strip() and len(case['message'].encode()) <= 2048)
            for turn in case['history']:
                self.assertEqual(set(turn), {'user', 'assistant'})
        self.assertTrue(all(c['history'] for c in cases if c['category'] == 'conversation_history'))

    def test_failures_and_e2e(self):
        failures = load('failures.jsonl')
        self.assertEqual(len(failures), 10)
        directed = [f for f in failures if f['project_directed']]
        self.assertEqual(len(directed), 4)
        self.assertTrue(all(f['expected']['outcome'] == 'unavailable' and
                            f['expected_if_fallback_rejected']['http_status'] == 503 for f in directed))
        e2e = load('e2e.jsonl')
        cases = {c['id']: c for c in load('cases.jsonl')}
        ordinary = [e for e in e2e if e['kind'] == 'case']
        self.assertEqual((len(ordinary), len(e2e) - len(ordinary)), (22, 4))
        for entry in ordinary:
            self.assertEqual(entry['message'], cases[entry['case_id']]['message'])
            self.assertIsInstance(entry['oracle_retrieval'], bool)
        self.assertEqual(sum(e['oracle_retrieval'] for e in ordinary), 12)
        self.assertEqual({e['case_id'] for e in e2e if e['kind'] == 'failure'}, {f['id'] for f in directed})
        self.assertIn('could not be accessed', (ROOT/'rubric.md').read_text(encoding='utf-8'))

    def test_evaluator_interface_and_gates(self):
        self.assertEqual(CUE_TABLE_CAP, 60)
        self.assertEqual(GATES['strict_false_supply_max'], 0)
        perfect = evaluate(oracle)
        failures = {f['id']: f['expected'] for f in load('failures.jsonl')}
        passed = evaluate_failures(lambda case: failures[case['id']])
        self.assertTrue(all(gates(perfect, passed).values()))
        self.assertEqual(perfect['overall']['missed_context'], 0)
        self.assertEqual(evaluate(oracle, 'dev')['overall']['cases'], 28)
        silent = evaluate(lambda case: dict(outcome='direct', attempted=False, source_paths=[], reason='off'))
        result = gates(silent, passed)
        self.assertFalse(result['missed_context'] or result['honest_path'])
        self.assertTrue(result['strict_false_supply'])
        noisy = evaluate(lambda case: dict(outcome='context', attempted=True, source_paths=[], reason='x'))
        self.assertFalse(gates(noisy, passed)['strict_false_supply'])
        rejected = evaluate_failures(lambda case: failures[case['id']], fallback_adopted=False)
        self.assertEqual(rejected['correct'], 6)
        with self.assertRaises(ValueError):
            evaluate(lambda case: dict(outcome='maybe', attempted=False, source_paths=[], reason='x'))

    @unittest.skipIf(pathspec is None, 'requires the optional dwindy[project] dependency')
    def test_combined_index_contains_every_gold_path(self):
        from dwindy.project import synchronize
        from dwindy.retrieval import RetrievalIndex
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(ROOT/'extra', Path(folder)/'extra')
            synchronize(materialize(folder, documents_manifest='extra/collection.toml'))
            index = RetrievalIndex(Path(folder)/'index.sqlite3')
            try:
                indexed = {row[0] for row in index.connection.execute('SELECT source_path FROM documents')}
            finally:
                index.close()
        gold = {path for case in load('cases.jsonl') for path in case['gold']}
        self.assertTrue(gold <= indexed, gold - indexed)
        self.assertTrue(extra_paths() <= indexed)


if __name__ == '__main__':
    unittest.main()
