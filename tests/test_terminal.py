import io
from pathlib import Path
import unittest
from unittest.mock import patch

from dwindy.__main__ import bounded_messages, main, terminal
from dwindy.backend import BackendError, Completion, Message, TextDelta
from dwindy.config import Config


class FakeBackend:
    def __init__(self, limit=100, failure=None):
        self.limit = limit
        self.failure = failure
        self.requests = []
        self.closed_streams = 0

    def context_size(self):
        return self.limit

    def close(self):
        pass

    def count_tokens(self, messages):
        return sum(len(m.content) + 1 for m in messages)

    def generate(self, messages, options):
        self.requests.append(list(messages))
        try:
            yield TextDelta("ok")
            if self.failure and len(self.requests) == 1:
                raise self.failure
            yield Completion("stop", self.count_tokens(messages), 1)
        finally:
            self.closed_streams += 1


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(Path("unused.gguf"), max_tokens=5)

    def run_chat(self, backend, inputs):
        iterator = iter(inputs)
        output = io.StringIO()
        def read(_):
            try:
                return next(iterator)
            except StopIteration:
                raise EOFError
        terminal(backend, self.cfg, read=read, output=output)
        return output.getvalue()

    def test_history_and_reset(self):
        backend = FakeBackend()
        self.run_chat(backend, ["one", "two", "/reset", "three", "/exit"])
        self.assertEqual([m.content for m in backend.requests[1]], ["one", "ok", "two"])
        self.assertEqual([m.content for m in backend.requests[2]], ["three"])
        self.assertEqual(backend.closed_streams, 3)

    def test_failed_and_interrupted_turn_not_retained(self):
        for failure in (BackendError("failed"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                backend = FakeBackend(failure=failure)
                self.run_chat(backend, ["one", "two", "/exit"])
                self.assertEqual([m.content for m in backend.requests[1]], ["two"])
                self.assertEqual(backend.closed_streams, 2)

    def test_drop_whole_turn_keep_system(self):
        cfg = Config(Path("unused"), max_tokens=5, system_prompt="sys")
        history = [Message("user", "old"), Message("assistant", "answer"),
                   Message("user", "new"), Message("assistant", "ok")]
        messages = bounded_messages(FakeBackend(limit=20), history, "hi", cfg)
        self.assertEqual([m.content for m in messages], ["sys", "new", "ok", "hi"])
        self.assertEqual(len(history), 4)  # Selection is transactional.

    def test_oversize_does_not_generate(self):
        backend = FakeBackend(limit=8)
        output = self.run_chat(backend, ["too long", "a", "/exit"])
        self.assertIn("cannot fit", output)
        self.assertEqual(len(backend.requests), 1)

    def test_exact_budget_fits(self):
        self.assertEqual(len(bounded_messages(FakeBackend(limit=8), [], "hi", self.cfg)), 1)

    def test_blank_input_and_eof(self):
        backend = FakeBackend()
        self.assertIn("Goodbye", self.run_chat(backend, ["  "]))
        self.assertFalse(backend.requests)

    def test_configuration_failure_is_clean(self):
        with patch("sys.stderr", new_callable=io.StringIO) as error:
            self.assertEqual(main([]), 1)
        self.assertIn("Supply a local GGUF", error.getvalue())

    def test_terminal_does_not_open_files_or_network_connections(self):
        backend = FakeBackend()
        with patch("builtins.open", side_effect=AssertionError("file access")), \
             patch("pathlib.Path.open", side_effect=AssertionError("file access")), \
             patch("socket.socket", side_effect=AssertionError("network access")):
            self.run_chat(backend, ["hello", "/reset", "/exit"])
        self.assertEqual(len(backend.requests), 1)

    def test_missing_completion_does_not_commit_turn(self):
        backend = FakeBackend()
        original = backend.generate
        def generate(messages, options):
            if not backend.requests:
                backend.requests.append(list(messages))
                yield TextDelta("partial")
            else:
                yield from original(messages, options)
        backend.generate = generate
        output = self.run_chat(backend, ["one", "two", "/exit"])
        self.assertIn("without a completion", output)
        self.assertEqual([m.content for m in backend.requests[1]], ["two"])

    def test_empty_completion_does_not_commit_turn(self):
        backend = FakeBackend()
        original = backend.generate
        def generate(messages, options):
            if not backend.requests:
                backend.requests.append(list(messages))
                yield Completion("stop", 1, 0)
            else:
                yield from original(messages, options)
        backend.generate = generate
        self.assertIn("no visible answer", self.run_chat(backend, ["one", "two", "/exit"]))
        self.assertEqual([m.content for m in backend.requests[1]], ["two"])
