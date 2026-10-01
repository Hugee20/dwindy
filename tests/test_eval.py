from collections import Counter
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dwindy.backend import BackendError
from dwindy.config import Config
from test_terminal import FakeBackend

ROOT = Path(__file__).parent / "eval"
spec = importlib.util.spec_from_file_location("baseline", ROOT / "run.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class EvaluationTests(unittest.TestCase):
    def test_dataset_balance_and_unique_cases(self):
        cases = baseline.load_cases(ROOT / "core_v0.jsonl")
        self.assertEqual(len(cases), 30)
        self.assertEqual(Counter(c["category"] for c in cases),
                         {category: 5 for category in baseline.CATEGORIES})

    def test_evaluation_records_without_invented_quality_score(self):
        case = baseline.load_cases(ROOT / "core_v0.jsonl")[0]
        result = baseline.evaluate_case(FakeBackend(limit=1000), case,
                                        Config(Path("unused"), max_tokens=5))
        self.assertEqual(result["response"], "ok")
        self.assertIsNone(result["human_score"])
        self.assertIsNone(result["error"])
        self.assertGreaterEqual(result["first_text_seconds"], 0)

    def test_failure_is_not_scored_as_success(self):
        case = baseline.load_cases(ROOT / "core_v0.jsonl")[0]
        result = baseline.evaluate_case(FakeBackend(limit=1000, failure=BackendError("failed")),
                                        case, Config(Path("unused"), max_tokens=5))
        self.assertEqual(result["error"], "failed")
        self.assertIsNone(result["visible_text_tokens_per_second"])

    def test_oversized_eval_is_not_silently_truncated(self):
        case = baseline.load_cases(ROOT / "core_v0.jsonl")[0]
        backend = FakeBackend(limit=5)
        result = baseline.evaluate_case(backend, case, Config(Path("unused"), max_tokens=2))
        self.assertIn("no truncation", result["error"])
        self.assertFalse(backend.requests)

    def test_complete_runner_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "fixture.gguf"
            model.write_bytes(b"not a real model")
            output = root / "results.jsonl"
            arguments = ["--model", str(model), "--output", str(output)]
            backend = FakeBackend(limit=4096)
            with patch("dwindy.llama_backend.LlamaBackend", return_value=backend), \
                 patch.object(baseline.importlib.metadata, "version", return_value="test"), \
                 patch.object(baseline.MemorySampler, "start"), \
                 patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(baseline.main(arguments), 0)
            original = output.read_bytes()
            rows = [json.loads(line) for line in original.decode().splitlines()]
            self.assertEqual(len(rows), 32)
            self.assertEqual(rows[-1]["cases"], 30)
            self.assertNotIn(str(root), original.decode())
            self.assertTrue(all(len(request) == 1 for request in backend.requests))
            with patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(baseline.main(arguments), 1)
            self.assertEqual(output.read_bytes(), original)
