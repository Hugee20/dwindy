"""Streaming Qwen3 channel decoding, not a filter over user or answer text."""

from .backend import BackendError


class Qwen3Answer:
    def __init__(self, prompt: str):
        # A closed, empty thinking prefix already selects the answer channel.
        _, marker, prefix = prompt.rpartition("<|im_start|>assistant\n")
        if not marker:
            prefix = ""
        self.state = "thinking" if prefix.rstrip().endswith("<think>") else (
            "answer" if "</think>" in prefix else "leading")
        self.pending = ""
        self.padding = False

    def feed(self, text: str) -> str:
        if self.state == "leading":
            self.pending += text
            candidate = self.pending.lstrip()
            if not candidate or "<think>".startswith(candidate):
                return ""
            if candidate.startswith("<think>"):
                text = candidate[len("<think>"):]
                self.pending = ""
                self.state = "thinking"
            else:
                text, self.pending = self.pending, ""
                self.state = "answer"
        if self.state == "thinking":
            value = self.pending + text
            end = value.find("</think>")
            if end == -1:
                # Retain only enough to recognize a split closing delimiter.
                self.pending = value[-(len("</think>") - 1):]
                return ""
            text = value[end + len("</think>"):]
            self.pending = ""
            self.state = "answer"
            self.padding = True
        if self.padding:
            text = text.lstrip("\r\n")
            if text:
                self.padding = False
        return text

    def finish(self) -> str:
        if self.state == "thinking" or (self.state == "leading" and self.pending.lstrip()):
            raise BackendError("Generation ended before a final answer was available. "
                               "Reasoning was not shown or saved. Check the model's output allowance "
                               "or its documented non-thinking setting.")
        text, self.pending = self.pending, ""
        return text
