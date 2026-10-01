"""One ephemeral conversation over a borrowed, runtime-neutral model backend."""

from dataclasses import dataclass
from typing import Generator, Sequence

from .backend import BackendError, Completion, GenerationOptions, Message, ModelBackend, TextDelta


@dataclass(frozen=True)
class TurnStarted:
    dropped_turns: int


def _bounded_messages(backend: ModelBackend, history: Sequence[Message], user: str,
                      options: GenerationOptions, system_prompt: str) -> list[Message]:
    prefix = [Message("system", system_prompt)] if system_prompt else []
    recent = list(history)
    while True:
        messages = prefix + recent + [Message("user", user)]
        if backend.count_tokens(messages) + options.max_tokens <= backend.context_size():
            return messages
        if not recent:
            raise BackendError("Current message cannot fit with the generation allowance. "
                               "Shorten it or adjust the context/output settings.")
        del recent[:2]  # Preserve M1: drop oldest complete user/assistant turn.


class DwindyCore:
    """Sequential-only conversation; caller owns and closes the backend.

    Streams are lazy. Iteration starts a turn; exhaust or explicitly close each
    started stream before another turn/reset. This guard is not a thread lock.
    """

    def __init__(self, backend: ModelBackend, *, options: GenerationOptions,
                 system_prompt: str = ""):
        self._backend = backend
        self._options = options
        self._system_prompt = system_prompt
        self._history: list[Message] = []
        self._active = False

    def _ensure_idle(self):
        if self._active:
            raise RuntimeError("A conversation stream is active; exhaust or close it first.")

    def reset(self) -> None:
        self._ensure_idle()
        self._history.clear()

    def chat(self, user_text: str) -> Generator[TurnStarted | TextDelta | Completion, None, None]:
        self._ensure_idle()
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("user_text must be a nonempty string.")
        return self._chat(user_text)

    def _chat(self, user_text):
        self._ensure_idle()  # Also reject interleaving previously created iterators.
        self._active = True
        try:
            messages = _bounded_messages(self._backend, self._history, user_text,
                                         self._options, self._system_prompt)
            removed = len(self._history) - sum(m.role != "system" for m in messages[:-1])
            yield TurnStarted(removed // 2)
            pieces = []
            completion = None
            stream = None
            try:
                stream = self._backend.generate(messages, self._options)
                for event in stream:
                    if isinstance(event, TextDelta):
                        pieces.append(event.text)
                        yield event
                    elif isinstance(event, Completion):
                        completion = event
            finally:
                if stream is not None and hasattr(stream, "close"):
                    stream.close()
            if completion is None:
                raise BackendError("Backend ended without a completion result.")
            response = "".join(pieces)
            if not response.strip():
                raise BackendError("Model produced no visible answer; turn not retained.")
            self._history = [m for m in messages if m.role != "system"]
            self._history.append(Message("assistant", response))
            yield completion  # Visible only after exhaustion, cleanup, and commit.
        finally:
            self._active = False
