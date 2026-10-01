from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from dwindy.backend import BackendError, Completion, GenerationOptions, Message, TextDelta
from dwindy.config import Config
from dwindy.llama_backend import LlamaBackend


class FakeLlama:
    instances = []
    template = "embedded template"

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.metadata = {"tokenizer.chat_template": self.template}
        self.closed = False
        self.resets = 0
        self.instances.append(self)

    def token_eos(self): return 2
    def token_bos(self): return 1
    def detokenize(self, ids, special=False): return b"<special>"
    def tokenize(self, text, add_bos, special):
        self.last_tokenize = (text, add_bos, special)
        return list(text)
    def n_ctx(self): return 100
    def reset(self): self.resets += 1
    def close(self): self.closed = True

    def create_completion(self, **kwargs):
        self.completion_kwargs = kwargs
        yield {"choices": [{"text": "ok", "finish_reason": None}]}
        yield {"choices": [{"text": "", "finish_reason": "stop"}]}


class FakeFormatter:
    def __init__(self, **kwargs): self.kwargs = kwargs
    def __call__(self, messages, **kwargs):
        self.last_kwargs = kwargs
        return types.SimpleNamespace(prompt="<role>" + messages[-1]["content"] + "<answer>"
                                     + kwargs.get("suffix", ""),
                                     added_special=True, stop=["<end>"], stopping_criteria=None)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        modules = {"llama_cpp": types.SimpleNamespace(Llama=FakeLlama),
                   "llama_cpp.llama_chat_format": types.SimpleNamespace(Jinja2ChatFormatter=FakeFormatter)}
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.cfg = Config(Path("local.gguf"), max_tokens=5)

    def test_cpu_only_and_exact_prompt_tokens(self):
        backend = LlamaBackend(self.cfg)
        self.addCleanup(backend.close)
        model = FakeLlama.instances[-1]
        self.assertEqual(model.kwargs["n_gpu_layers"], 0)
        self.assertNotIn("chat_format", model.kwargs)
        messages = [Message("user", "hi")]
        count = backend.count_tokens(messages)
        events = list(backend.generate(messages, self.cfg.options()))
        self.assertEqual(len(model.completion_kwargs["prompt"]), count)
        self.assertEqual(model.completion_kwargs["stop"], ["<end>"])
        self.assertEqual(events, [TextDelta("ok"), Completion("stop", count, 2)])
        self.assertEqual(model.resets, 2)

    def test_missing_template_closes_model(self):
        with patch.object(FakeLlama, "template", ""), self.assertRaisesRegex(BackendError, "no tokenizer"):
            LlamaBackend(self.cfg)
        self.assertTrue(FakeLlama.instances[-1].closed)

    def test_overflow_rejected_before_inference(self):
        backend = LlamaBackend(self.cfg)
        self.addCleanup(backend.close)
        with self.assertRaisesRegex(BackendError, "exceeds"):
            list(backend.generate([Message("user", "x" * 100)], GenerationOptions(5)))
        self.assertFalse(hasattr(FakeLlama.instances[-1], "completion_kwargs"))

    def test_stream_close_clears_runtime_state(self):
        backend = LlamaBackend(self.cfg)
        self.addCleanup(backend.close)
        stream = backend.generate([Message("user", "hi")], self.cfg.options())
        next(stream)
        stream.close()
        self.assertEqual(FakeLlama.instances[-1].resets, 2)

    def test_bad_template_error(self):
        backend = LlamaBackend(self.cfg)
        self.addCleanup(backend.close)
        with patch.object(FakeFormatter, "__call__", side_effect=ValueError("bad template")):
            with self.assertRaisesRegex(BackendError, "render/tokenize"):
                backend.count_tokens([Message("user", "hi")])

    def test_close_is_idempotent(self):
        backend = LlamaBackend(self.cfg)
        backend.close()
        backend.close()
        with self.assertRaisesRegex(BackendError, "closed"):
            backend.count_tokens([Message("user", "hi")])

    def test_template_kwargs_shared_by_counting_and_generation(self):
        cfg = Config(Path("local.gguf"), max_tokens=5,
                     chat_template_kwargs={"suffix": "EXTRA", "enable_thinking": False})
        backend = LlamaBackend(cfg)
        self.addCleanup(backend.close)
        messages = [Message("user", "hi")]
        count = backend.count_tokens(messages)
        model = FakeLlama.instances[-1]
        counted_prompt = model.last_tokenize[0]
        self.assertTrue(counted_prompt.endswith(b"EXTRA"))
        self.assertEqual(backend._formatter.last_kwargs, cfg.chat_template_kwargs)
        # The adapter holds a snapshot; later caller mutation cannot change its policy.
        cfg.chat_template_kwargs["suffix"] = "CHANGED"
        events = list(backend.generate(messages, cfg.options()))
        self.assertEqual(bytes(model.completion_kwargs["prompt"]), counted_prompt)
        self.assertEqual(events[-1].prompt_tokens, count)
        self.assertNotIn("enable_thinking", model.kwargs)
        self.assertNotIn("enable_thinking", model.completion_kwargs)

    def test_generated_text_is_not_stripped(self):
        backend = LlamaBackend(self.cfg)
        self.addCleanup(backend.close)
        raw = "<think>test fixture</think>answer"
        chunks = [{"choices": [{"text": raw, "finish_reason": "stop"}]}]
        with patch.object(FakeLlama, "create_completion", return_value=iter(chunks)):
            events = list(backend.generate([Message("user", "hi")], self.cfg.options()))
        self.assertEqual(events[0], TextDelta(raw))
