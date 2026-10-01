"""Runtime-neutral, synchronous streaming inference contract."""

from dataclasses import dataclass
from typing import Iterator, Literal, Protocol, Sequence


class BackendError(RuntimeError):
    """A model loading, formatting, or generation failure."""


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class GenerationOptions:
    max_tokens: int = 256
    temperature: float = 0.7
    seed: int = 42


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Completion:
    finish_reason: str
    prompt_tokens: int
    # Retokenized visible text, not the runtime's sampled token count.
    text_tokens: int


class ModelBackend(Protocol):
    def generate(self, messages: Sequence[Message], options: GenerationOptions
                 ) -> Iterator[TextDelta | Completion]: ...

    def count_tokens(self, messages: Sequence[Message]) -> int: ...

    def context_size(self) -> int: ...

    def close(self) -> None: ...
