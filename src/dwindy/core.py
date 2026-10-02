"""One ephemeral conversation over a borrowed, runtime-neutral model backend."""

from dataclasses import dataclass
from typing import Generator, Sequence

from .backend import BackendError, Completion, ContextLimitError, GenerationOptions, Message, ModelBackend, TextDelta
from .evidence import (Evidence, Facts, GUIDANCE, UNAVAILABLE_GUIDANCE, WEB_GUIDANCE, WEB_SENTENCE_GUIDANCE,
                       evidence_question,
                       facts_block, policy_guidance, host_block, web_facts_block, web_facts_guidance, web_host_block)


@dataclass(frozen=True)
class TurnStarted:
    dropped_turns: int
    retrieval: dict | None = None


def _bounded_messages(backend: ModelBackend, history: Sequence[Message], user: str,
                      options: GenerationOptions, system_prompt: str) -> list[Message]:
    prefix = [Message("system", system_prompt)] if system_prompt else []
    recent = list(history)
    while True:
        messages = prefix + recent + [Message("user", user)]
        if backend.count_tokens(messages) + options.max_tokens <= backend.context_size():
            return messages
        if not recent:
            raise ContextLimitError("Current message cannot fit with the generation allowance. "
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

    def snapshot(self) -> tuple[Message, ...]:
        """Return retained completed turns, excluding the configured system message."""
        self._ensure_idle()
        return tuple(self._history)

    def restore(self, messages: Sequence[Message]) -> None:
        """Replace idle conversation context with validated complete turns; no I/O."""
        self._ensure_idle()
        if not isinstance(messages, Sequence):
            raise ValueError("Expected a sequence of complete user/assistant turns.")
        candidate = list(messages)
        if len(candidate) % 2 or any(
            not isinstance(message, Message)
            or message.role != ("user" if index % 2 == 0 else "assistant")
            or not isinstance(message.content, str) or not message.content.strip()
            for index, message in enumerate(candidate)
        ):
            raise ValueError("Expected nonempty alternating user/assistant messages.")
        self._history = candidate

    def chat(self, user_text: str, *, evidence: Evidence | None = None, facts: Facts | None = None,
             notice: str | None = None) -> Generator[TurnStarted | TextDelta | Completion, None, None]:
        """notice is a transient system instruction for this turn only (M10 offline honesty)."""
        self._ensure_idle()
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("user_text must be a nonempty string.")
        if evidence is not None and not isinstance(evidence, Evidence):
            raise ValueError("Expected Evidence or None")
        if facts is not None and not isinstance(facts, Facts):
            raise ValueError("Expected Facts or None")
        if notice is not None and (not isinstance(notice, str) or not notice.strip()):
            raise ValueError("Expected a nonempty notice or None")
        return self._chat(user_text, evidence, facts or None, notice)

    def _evidence_messages(self, user, evidence, prefix="", extra="", facts=None, notice=None):
        guidance = dict(web=WEB_GUIDANCE, web_sentences=WEB_SENTENCE_GUIDANCE).get(evidence.origin, GUIDANCE)
        system = (self._system_prompt + "\n\n" if self._system_prompt else "") + guidance + ("\n\n" + extra if extra else "")
        base_system = ((self._system_prompt + "\n\n" if self._system_prompt else "") + extra) if extra else self._system_prompt
        base = ([Message("system",base_system)] if base_system else []) + [
            Message("user", prefix + "User question:\n" + user if prefix else user)]
        baseline = self._backend.count_tokens(base)
        def compose(passages, history=()):
            framed_system = system
            if evidence.origin == "local":
                guidance = policy_guidance(facts, passages)
                # Empty local evidence still has the existing explicit no-match framing.
                if not passages and not facts:
                    guidance = guidance or GUIDANCE
                framed_system = (self._system_prompt + "\n\n" if self._system_prompt else "") + guidance
                if notice: framed_system += "\n\n" + notice
            return ([Message("system", framed_system)] if framed_system else []) + list(history) + [
                Message("user", prefix + evidence_question(user, passages, evidence.framing, evidence.origin))]
        def fits(messages):
            count = self._backend.count_tokens(messages)
            return count + self._options.max_tokens <= self._backend.context_size() and max(0,count-baseline) <= evidence.max_tokens
        if not fits(compose([])):
            raise ContextLimitError("Retrieval guidance and question cannot fit the context/evidence allowance.")
        selected, seen = [], set()
        for passage in evidence.passages:
            if passage.text in seen: continue
            if fits(compose([*selected,passage])):
                selected.append(passage); seen.add(passage.text)
            if len(selected) == 3: break
        # Recheck the exact rendered input with retained history: templates and
        # tokenization need not have an additive per-message cost.
        while True:
            recent = list(self._history)
            messages = compose(selected,recent)
            count = self._backend.count_tokens(messages)
            while count + self._options.max_tokens > self._backend.context_size() and recent:
                del recent[:2]
                messages = compose(selected,recent)
                count = self._backend.count_tokens(messages)
            plain = base[:-1] + recent + base[-1:]
            incremental = max(0, count - self._backend.count_tokens(plain))
            if incremental <= evidence.max_tokens and count + self._options.max_tokens <= self._backend.context_size():
                break
            if not selected:
                raise ContextLimitError("Retrieval guidance cannot fit the context/evidence allowance.")
            selected.pop()
        status = "supplied" if selected else "budget_exhausted" if evidence.passages else "no_match"
        return messages,recent,dict(status=status,sources=[p.source.mapping() for p in selected])

    def _chat(self, user_text, evidence, facts=None, notice=None):
        self._ensure_idle()  # Also reject interleaving previously created iterators.
        self._active = True
        try:
            system, retrieval = self._system_prompt, None
            web = evidence is not None and evidence.origin != "local"
            prefix = ""
            extra = "" if web else policy_guidance(facts)
            content = user_text
            if facts:
                # Host data has its own allowance; it is rejected, never truncated, when too large.
                block = web_host_block(facts) if web else host_block(facts)
                if block and (self._backend.count_tokens([Message("user", block)]) -
                              self._backend.count_tokens([Message("user", "")])) > facts.host_budget:
                    raise ContextLimitError("Host context exceeds its token allowance.")
                prefix = web_facts_block(facts) if web else facts_block(facts)
                if web: extra = web_facts_guidance(facts)
                content = prefix + "User question:\n" + user_text
            if notice:
                extra = (extra + "\n\n" if extra else "") + notice
            if evidence is not None and evidence.fallback == "unavailable":
                # Transient instruction only; history still stores the original question.
                system = (system + "\n\n" if system else "") + UNAVAILABLE_GUIDANCE
                retrieval = dict(status="unavailable", sources=[])
            elif evidence is not None:
                try:
                    messages,recent,retrieval = self._evidence_messages(user_text,evidence,prefix,extra,facts,notice)
                except ContextLimitError:
                    if evidence.fallback != "plain":
                        raise
                    retrieval = dict(status="no_match", sources=[])
                if evidence.fallback == "plain" and retrieval["status"] != "supplied":
                    # Opportunistic evidence that cannot be used becomes ordinary chat.
                    retrieval = dict(status="not_used", sources=[])
            if retrieval is None or retrieval["status"] in ("unavailable", "not_used"):
                if extra:
                    system = (system + "\n\n" if system else "") + extra
                messages = _bounded_messages(self._backend, self._history, content,
                                             self._options, system)
                recent = [m for m in messages[:-1] if m.role != "system"]
            removed = len(self._history) - len(recent)
            yield TurnStarted(removed // 2, retrieval)
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
            self._history = recent + [Message("user",user_text)]
            self._history.append(Message("assistant", response))
            yield completion  # Visible only after exhaustion, cleanup, and commit.
        finally:
            self._active = False
