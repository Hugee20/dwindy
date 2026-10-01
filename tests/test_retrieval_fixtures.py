import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parent / "retrieval"


class RetrievalFixtureTests(unittest.TestCase):
    def test_frozen_hashes_and_composition(self):
        hashes = json.loads((ROOT / "FREEZE.json").read_text())
        for path, expected in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected, path)
        cases = [json.loads(line) for line in (ROOT / "queries.jsonl").read_text().splitlines()]
        self.assertEqual(len(cases), 24)
        self.assertEqual(len({c["id"] for c in cases}), 24)
        self.assertEqual(sum(c["split"] == "dev" for c in cases), 12)
        self.assertEqual(sum(bool(c["gold"]) for c in cases), 20)
        for category in {c["category"] for c in cases}:
            self.assertEqual(sum(c["category"] == category for c in cases), 4)
        for case in cases:
            for gold in case["gold"]:
                text = (ROOT / "corpus" / (gold["document_id"] + ".txt")).read_text(encoding="utf-8")
                self.assertEqual(text[gold["start"]:gold["end"]], gold["text"])
        self.assertEqual((ROOT/'corpus/D.txt').read_bytes(), (ROOT/'corpus/K.txt').read_bytes())

    def test_evaluator_ranks_gold_spans_not_related_documents(self):
        spec = importlib.util.spec_from_file_location("retrieval_eval", ROOT / "evaluate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        empty = module.evaluate(lambda query: [])
        self.assertEqual(empty["overall"]["hit3"], 0)
        self.assertEqual(empty["overall"]["answerable"], 20)
        self.assertEqual(module.evaluate(lambda query: [], "holdout")["overall"]["cases"], 12)
