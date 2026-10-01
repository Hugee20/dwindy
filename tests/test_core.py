import io
import unittest
from unittest.mock import patch

from dwindy.backend import BackendError, Completion, GenerationOptions, Message, TextDelta
from dwindy.core import DwindyCore, TurnStarted, _bounded_messages
from test_terminal import FakeBackend


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.options = GenerationOptions(max_tokens=5)
        self.core = DwindyCore(self.backend, options=self.options)

    def test_drop_whole_turn_keep_system(self):
        history = [Message("user", "old"), Message("assistant", "answer"),
                   Message("user", "new"), Message("assistant", "ok")]
        messages = _bounded_messages(FakeBackend(limit=20), history, "hi", self.options, "sys")
        self.assertEqual([m.content for m in messages], ["sys", "new", "ok", "hi"])
        self.assertEqual(len(history), 4)

    def test_exact_budget_fits(self):
        self.assertEqual(len(_bounded_messages(FakeBackend(limit=8), [], "hi", self.options, "")), 1)

    def test_multiturn_and_reset_with_borrowed_backend(self):
        with patch.object(self.backend, "close") as close:
            self.assertEqual(list(self.core.chat("one"))[0], TurnStarted(0))
            list(self.core.chat("two"))
            self.assertEqual([m.content for m in self.backend.requests[-1]], ["one", "ok", "two"])
            self.core.reset()
            list(self.core.chat("three"))
            self.assertEqual([m.content for m in self.backend.requests[-1]], ["three"])
            close.assert_not_called()

    def test_separate_conversations_can_borrow_backend_sequentially(self):
        other = DwindyCore(self.backend, options=self.options)
        list(self.core.chat("private"))
        list(other.chat("separate"))
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["separate"])
        list(self.core.chat("again"))
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["private", "ok", "again"])

    def test_successful_trimming_commits_only_retained_turns(self):
        self.backend.limit = 20
        list(self.core.chat("one"))
        list(self.core.chat("two"))
        events = list(self.core.chat("three"))
        self.assertEqual(events[0], TurnStarted(1))
        self.backend.limit = 100
        list(self.core.chat("four"))
        self.assertEqual([m.content for m in self.backend.requests[-1]],
                         ["two", "ok", "three", "ok", "four"])

    def test_failure_after_proposed_trimming_rolls_back(self):
        list(self.core.chat("one"))
        list(self.core.chat("two"))
        self.backend.limit = 12
        def fail(messages, options):
            yield TextDelta("partial")
            raise BackendError("failure")
        with patch.object(self.backend, "generate", side_effect=fail):
            stream = self.core.chat("bad")
            self.assertEqual(next(stream), TurnStarted(2))
            with self.assertRaises(BackendError):
                list(stream)
        self.backend.limit = 100
        list(self.core.chat("next"))
        self.assertEqual([m.content for m in self.backend.requests[-1]],
                         ["one", "ok", "two", "ok", "next"])

    def test_early_close_closes_backend_and_discards_pending_turn(self):
        list(self.core.chat("one"))
        stream = self.core.chat("cancel")
        next(stream)
        self.assertEqual(next(stream), TextDelta("ok"))
        stream.close()
        self.assertEqual(self.backend.closed_streams, 2)
        list(self.core.chat("next"))
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["one", "ok", "next"])

    def test_cancellation_after_proposed_trimming_preserves_history(self):
        list(self.core.chat("one"))
        list(self.core.chat("two"))
        self.backend.limit = 12
        stream = self.core.chat("bad")
        self.assertEqual(next(stream), TurnStarted(2))
        next(stream)
        stream.close()
        self.backend.limit = 100
        list(self.core.chat("next"))
        self.assertEqual([m.content for m in self.backend.requests[-1]],
                         ["one", "ok", "two", "ok", "next"])

    def test_cleanup_failure_rolls_back_and_releases_guard(self):
        class BrokenClose:
            def __iter__(self):
                return iter([TextDelta("answer"), Completion("stop", 1, 1)])
            def close(self):
                raise BackendError("cleanup failed")
        with patch.object(self.backend, "generate", return_value=BrokenClose()):
            with self.assertRaisesRegex(BackendError, "cleanup failed"):
                list(self.core.chat("bad"))
        list(self.core.chat("next"))
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["next"])

    def test_close_at_turn_started_does_not_generate(self):
        stream = self.core.chat("cancel")
        self.assertEqual(next(stream), TurnStarted(0))
        stream.close()
        self.assertFalse(self.backend.requests)
        self.core.reset()

    def test_active_stream_blocks_chat_reset_and_precreated_iterator(self):
        first = self.core.chat("first")
        second = self.core.chat("second")
        next(first)
        with self.assertRaises(RuntimeError):
            self.core.chat("third")
        with self.assertRaises(RuntimeError):
            self.core.reset()
        with self.assertRaises(RuntimeError):
            next(second)
        with self.assertRaises(RuntimeError):
            self.core.reset()  # Rejected iterator must not clear first's guard.
        first.close()
        self.core.reset()
        list(self.core.chat("works"))

    def test_unstarted_stream_close_has_no_effect(self):
        stream = self.core.chat("unused")
        stream.close()
        self.core.reset()
        self.assertFalse(self.backend.requests)

    def test_completion_is_after_commit_and_backend_cleanup(self):
        stream = self.core.chat("one")
        next(stream)
        next(stream)
        self.assertIsInstance(next(stream), Completion)
        self.assertEqual(self.backend.closed_streams, 1)
        self.assertEqual([m.content for m in self.core._history], ["one", "ok"])
        stream.close()  # Closing after completion must not roll back committed history.
        list(self.core.chat("two"))
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["one", "ok", "two"])

    def test_length_limited_nonempty_answer_is_committed(self):
        def limited(messages, options):
            yield TextDelta("partial answer")
            yield Completion("length", 1, 2)
        with patch.object(self.backend, "generate", side_effect=limited):
            self.assertEqual(list(self.core.chat("one"))[-1].finish_reason, "length")
        list(self.core.chat("two"))
        self.assertEqual([m.content for m in self.backend.requests[-1]],
                         ["one", "partial answer", "two"])

    def test_failure_after_backend_completion_does_not_commit(self):
        def fail(messages, options):
            yield TextDelta("answer")
            yield Completion("stop", 1, 1)
            raise BackendError("late failure")
        with patch.object(self.backend, "generate", side_effect=fail):
            with self.assertRaises(BackendError):
                list(self.core.chat("bad"))
        list(self.core.chat("next"))
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["next"])

    def test_direct_failures_release_guard(self):
        for failure in (BackendError("failed"), KeyboardInterrupt()):
            backend = FakeBackend(failure=failure)
            core = DwindyCore(backend, options=self.options)
            with self.subTest(failure=type(failure).__name__):
                with self.assertRaises(type(failure)):
                    list(core.chat("bad"))
                core.reset()
                list(core.chat("next"))
                self.assertEqual([m.content for m in backend.requests[-1]], ["next"])

    def test_count_failure_and_overflow_release_guard(self):
        with patch.object(self.backend, "count_tokens", side_effect=BackendError("count")):
            with self.assertRaises(BackendError):
                list(self.core.chat("bad"))
        self.backend.limit = 5
        with self.assertRaises(BackendError):
            list(self.core.chat("too long"))
        self.core.reset()
        self.assertFalse(self.backend.requests)

    def test_no_io_and_model_facing_inputs_unchanged(self):
        core = DwindyCore(self.backend, options=self.options, system_prompt="original")
        with patch("builtins.input", side_effect=AssertionError("input")), \
             patch("builtins.open", side_effect=AssertionError("file access")), \
             patch("socket.socket", side_effect=AssertionError("network")), \
             patch("sys.stdout", new_callable=io.StringIO) as output, \
             patch.object(self.backend, "generate", wraps=self.backend.generate) as generate:
            events = list(core.chat("  unchanged text  "))
            self.assertEqual(output.getvalue(), "")
            self.assertIs(generate.call_args.args[1], self.options)
        self.assertEqual(self.backend.requests[-1],
                         [Message("system", "original"), Message("user", "  unchanged text  ")])
        self.assertEqual(events[1], TextDelta("ok"))

    def test_empty_input_does_not_generate_or_reserve_stream(self):
        for value in ("", "  ", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.core.chat(value)
        self.core.reset()
        self.assertFalse(self.backend.requests)
