import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parent / 'project'


class ProjectFixtureTests(unittest.TestCase):
    def test_frozen_hashes(self):
        frozen = json.loads((ROOT/'FREEZE.json').read_text(encoding='utf-8'))
        for path, digest in frozen.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)

    def test_queries_spans_split_and_discovery(self):
        files=json.loads((ROOT/'files.json').read_text(encoding='utf-8'))
        cases=[json.loads(line) for line in (ROOT/'queries.jsonl').read_text().splitlines()]
        self.assertEqual(len(cases),32)
        self.assertEqual(len({c['id'] for c in cases}),32)
        for split in ('dev','holdout'):
            subset=[c for c in cases if c['split']==split]
            self.assertEqual(len(subset),16)
            self.assertEqual(sum(c['answerable'] for c in subset),11)
        for case in cases:
            for gold in case['gold']:
                self.assertTrue(0 <= gold['start'] < gold['end'] <= len(files[gold['source_path']]))
        expected=json.loads((ROOT/'discovery.json').read_text())
        self.assertFalse(set(expected['selected']) & set(expected['excluded']))
        self.assertTrue(set(expected['selected']) <= files.keys())
