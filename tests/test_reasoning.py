"""Channel decoding before output/history, including arbitrary stream splits."""
import unittest

from dwindy.backend import BackendError
from dwindy.reasoning import Qwen3Answer


class ReasoningTests(unittest.TestCase):
    def decode(self, chunks, prefix=""):
        answer = Qwen3Answer("<|im_start|>assistant\n" + prefix)
        return "".join(answer.feed(chunk) for chunk in chunks) + answer.finish()

    def test_every_split_hides_only_leading_reasoning(self):
        raw = "<think>private reasoning</think>\n\nFinal <think>literal example</think>."
        for split in range(len(raw) + 1):
            with self.subTest(split=split):
                self.assertEqual(self.decode([raw[:split], raw[split:]]),
                                 "Final <think>literal example</think>.")
        self.assertEqual(self.decode(list(raw)), "Final <think>literal example</think>.")

    def test_open_prefix_and_empty_block(self):
        self.assertEqual(self.decode(list("hidden</think>\nAnswer"), "<think>\n"), "Answer")
        self.assertEqual(self.decode(list("<think></think>\nAnswer")), "Answer")

    def test_closed_non_thinking_prefix_preserves_literal_answer(self):
        self.assertEqual(self.decode(["<think>literal markup</think>"], "<think>\n\n</think>\n\n"),
                         "<think>literal markup</think>")

    def test_plain_text_and_user_markup_are_not_filters(self):
        for raw in ["  normal answer", "Use <think> and </think> literally", "```\n<think>example</think>\n```"]:
            self.assertEqual(self.decode(list(raw)), raw)

    def test_unfinished_channel_never_emits_or_retains_body(self):
        answer = Qwen3Answer("<|im_start|>assistant\n")
        self.assertEqual(answer.feed("<think>" + "hidden" * 10000), "")
        self.assertLessEqual(len(answer.pending), len("</think>") - 1)
        with self.assertRaisesRegex(BackendError, "before a final answer"):
            answer.finish()

    def test_partial_opening_delimiter_is_not_emitted(self):
        answer = Qwen3Answer("<|im_start|>assistant\n")
        self.assertEqual(answer.feed("<thi"), "")
        with self.assertRaises(BackendError):
            answer.finish()
