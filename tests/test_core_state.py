import unittest
from unittest.mock import patch

from dwindy.backend import GenerationOptions, Message
from dwindy.core import DwindyCore
from test_terminal import FakeBackend


class CoreStateTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.core = DwindyCore(self.backend, options=GenerationOptions(max_tokens=5), system_prompt="sys")

    def test_round_trip_preserves_exact_model_input_and_detaches_container(self):
        list(self.core.chat("  one  "))
        snapshot = self.core.snapshot()
        self.assertIsInstance(snapshot, tuple)
        other = DwindyCore(self.backend, options=GenerationOptions(max_tokens=5), system_prompt="sys")
        values = list(snapshot)
        with patch.object(self.backend, "count_tokens", side_effect=AssertionError("no model calls")):
            other.restore(values)
        values.clear()
        list(self.core.chat("two"))
        expected = self.backend.requests[-1]
        list(other.chat("two"))
        self.assertEqual(self.backend.requests[-1], expected)
        self.core.reset()
        self.assertEqual(len(snapshot), 2)

    def test_invalid_restore_is_atomic(self):
        list(self.core.chat("one"))
        original = self.core.snapshot()
        for value in (None, "x", [Message("user", "x")],
                      [Message("system", "x"), Message("assistant", "a")],
                      [Message("user", "x"), Message("assistant", " ")],
                      [Message("user", "x"), Message("assistant", 1)]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.core.restore(value)
            self.assertEqual(self.core.snapshot(), original)

    def test_active_guard_includes_final_completion(self):
        stream = self.core.chat("one")
        for event in stream:
            with self.assertRaises(RuntimeError):
                self.core.snapshot()
            with self.assertRaises(RuntimeError):
                self.core.restore([])
        self.assertEqual(len(self.core.snapshot()), 2)
        self.core.restore([])
        self.assertEqual(self.core.snapshot(), ())
