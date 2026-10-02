"""Development runner mechanics with a fake model; no scored model outputs."""
from pathlib import Path
import unittest
from unittest.mock import patch

from dwindy.config import Config
from eval_policy_foundation_dev import episode, prepare, Recorder
from policy_foundation_v1.evaluate import load
from policy_support import RecordingBackend


class FoundationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(Path('unused.gguf'), context_size=20000, max_tokens=5)
        self.case = next(c for c in load('cases.jsonl', 'dev') if c['id']=='continuity_1')

    def test_followup_uses_actual_first_answer_without_new_backend(self):
        backend = RecordingBackend(text='ACTUAL_FIRST_ANSWER')
        with patch('eval_policy_foundation_dev.LlamaBackend', return_value=backend) as factory:
            rows = episode(self.case, 'M11_foundation', self.config)
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(len(backend.requests), 2)
        self.assertEqual(rows[1]['history_before'][1]['content'], 'ACTUAL_FIRST_ANSWER')
        self.assertEqual(rows[1]['messages'][1]['content'], 'ACTUAL_FIRST_ANSWER')
        self.assertEqual([r['model_calls'] for r in rows], [1, 1])
        self.assertTrue(all(r['budget_audit_pass'] for r in rows))

    def test_failed_turn_is_not_retried_or_seeded_as_success(self):
        backend = RecordingBackend(failure=RuntimeError('generation failed'))
        with patch('eval_policy_foundation_dev.LlamaBackend', return_value=backend):
            rows = episode(self.case, 'M11_foundation', self.config)
        self.assertEqual(len(backend.requests), 2)
        self.assertTrue(all(r['execution_error'] for r in rows))
        self.assertEqual(rows[1]['history_before'], [])
        self.assertEqual([r['model_calls'] for r in rows], [1, 1])

    def test_counterfactual_tokenization_never_generates_on_real_backend(self):
        backend = RecordingBackend()
        data = prepare(self.case, 0, 'M11_foundation', self.config, backend, ())
        self.assertEqual(backend.requests, [])
        self.assertEqual(data['messages'], [{'role':'user', 'content':self.case['turns'][0]['message']}])

    def test_pinned_m10_and_native_ordinary_inputs_match(self):
        backend = RecordingBackend()
        old = prepare(self.case, 0, 'M10', self.config, backend, ())
        new = prepare(self.case, 0, 'M11_foundation', self.config, backend, ())
        self.assertEqual(old, new)
