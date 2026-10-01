"""All GGUF, template, tokenization, and llama.cpp coupling lives here."""

from dataclasses import asdict
from typing import Iterator, Sequence

from .backend import BackendError, Completion, ContextLimitError, GenerationOptions, Message, TextDelta
from .config import Config, validate_template_kwargs


class LlamaBackend:
    def __init__(self, config: Config):
        self._model = None
        self._template_kwargs = validate_template_kwargs(config.chat_template_kwargs)
        try:
            from llama_cpp import Llama
            from llama_cpp.llama_chat_format import Jinja2ChatFormatter
        except (ImportError, OSError, RuntimeError) as exc:
            raise BackendError(
                "Cannot import llama-cpp-python. Install a compatible CPU build; "
                "see README.md. No model is downloaded by Dwindy."
            ) from exc
        try:
            kwargs = dict(model_path=str(config.model_path), n_ctx=config.context_size,
                          n_gpu_layers=0, verbose=False)
            if config.threads is not None:
                kwargs.update(n_threads=config.threads, n_threads_batch=config.threads)
            self._model = Llama(**kwargs)
            template = self._model.metadata.get("tokenizer.chat_template")
            if not isinstance(template, str) or not template.strip():
                raise BackendError(
                    "GGUF has no tokenizer.chat_template. M1 requires an embedded "
                    "text chat template supported by this runtime; no family fallback is used."
                )
            def token_text(token_id):
                if token_id < 0:
                    return ""
                return self._model.detokenize([token_id], special=True).decode("utf-8")
            self._formatter = Jinja2ChatFormatter(
                template=template,
                eos_token=token_text(self._model.token_eos()),
                bos_token=token_text(self._model.token_bos()),
                add_generation_prompt=True,
            )
        except BaseException as exc:
            self.close()
            if isinstance(exc, (BackendError, KeyboardInterrupt, SystemExit)):
                raise
            raise BackendError(
                f"Cannot load GGUF/chat template ({type(exc).__name__}). "
                "Check model compatibility, available RAM, and runtime version."
            ) from exc

    def _prepare(self, messages):
        if self._model is None:
            raise BackendError("Model backend is closed.")
        try:
            formatted = self._formatter(messages=[asdict(m) for m in messages],
                                        **self._template_kwargs)
            tokens = self._model.tokenize(formatted.prompt.encode("utf-8"),
                                          add_bos=not formatted.added_special,
                                          special=True)
            if not tokens:
                raise ValueError("empty prompt")
            return formatted, tokens
        except Exception as exc:
            raise BackendError(
                "Cannot render/tokenize this conversation with the embedded chat template. "
                "Check template support and whether it permits system messages."
            ) from exc

    def count_tokens(self, messages: Sequence[Message]) -> int:
        return len(self._prepare(messages)[1])

    def context_size(self) -> int:
        if self._model is None:
            raise BackendError("Model backend is closed.")
        return self._model.n_ctx()

    def generate(self, messages: Sequence[Message], options: GenerationOptions
                 ) -> Iterator[TextDelta | Completion]:
        formatted, tokens = self._prepare(messages)
        if options.max_tokens < 1 or len(tokens) + options.max_tokens > self.context_size():
            raise ContextLimitError("Request plus generation allowance exceeds model context.")
        stream = None
        try:
            # Reset logical inference state; supplied messages are the sole history.
            self._model.reset()
            stream = self._model.create_completion(
                prompt=tokens, max_tokens=options.max_tokens,
                temperature=options.temperature, seed=options.seed,
                stop=[s for s in (formatted.stop or []) if s],
                stopping_criteria=formatted.stopping_criteria,
                stream=True,
            )
            pieces = []
            reason = None
            for chunk in stream:
                choice = chunk["choices"][0]
                if choice["text"]:
                    pieces.append(choice["text"])
                    yield TextDelta(choice["text"])
                if choice.get("finish_reason"):
                    reason = choice["finish_reason"]
            if reason is None:
                raise BackendError("Runtime ended without a completion result.")
            count = len(self._model.tokenize("".join(pieces).encode("utf-8"),
                                              add_bos=False, special=False))
            yield Completion(reason, len(tokens), count)
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Local generation failed ({type(exc).__name__}); "
                "the incomplete turn was not retained."
            ) from exc
        finally:
            if stream is not None and hasattr(stream, "close"):
                stream.close()
            self._model.reset()

    def close(self) -> None:
        model, self._model = self._model, None
        if model is not None:
            model.close()
