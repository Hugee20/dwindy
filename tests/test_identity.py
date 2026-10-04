import unittest

from dwindy.backend import ContextLimitError, GenerationOptions, Message
from dwindy.core import DwindyCore
from dwindy.evidence import Evidence
from dwindy.identity import runtime_system_prompt
from test_terminal import FakeBackend


class IdentityTests(unittest.TestCase):
    def test_application_identity_is_generic_with_optional_configured_text(self):
        identity = ('You are Dwindy, a local AI assistant.\n'
                    'You are powered by a local large language model.\n'
                    'Dwindy is developed as part of the Dwindy project, a small, modular, local-first chatbot.')
        self.assertEqual(runtime_system_prompt(), identity)
        self.assertEqual(runtime_system_prompt('Configured system text.'),
                         identity + '\n\nConfigured system text.')

    def test_api_identity_does_not_read_or_expose_backend_metadata(self):
        import os
        from pathlib import Path
        from unittest.mock import Mock, patch
        from test_api import create_app, TestClient
        from dwindy.config import Config
        backend = FakeBackend()
        backend.model_metadata = Mock(return_value={'name': 'Specific model', 'architecture': 'specific_arch'})
        with patch.dict(os.environ, {}, clear=True):
            app = create_app(Config(Path('unused.gguf'), max_tokens=5), backend=backend)
        with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1)) as client:
            reply = client.post('/v1/chat', json={'message': 'What powers you?'}).json()
        self.assertEqual(reply['text'], 'ok')
        backend.model_metadata.assert_not_called()
        self.assertEqual(backend.requests[-1][0], Message('system', runtime_system_prompt()))

    def test_identity_is_transient_and_native_history_survives(self):
        backend = FakeBackend(limit=20000)
        prompt = runtime_system_prompt()
        core = DwindyCore(backend, options=GenerationOptions(max_tokens=5), system_prompt=prompt)
        user = 'Literal <think>user text</think>'
        list(core.chat(user))
        saved = (Message('user', user), Message('assistant', 'ok'))
        self.assertEqual(core.snapshot(), saved)
        restored = DwindyCore(backend, options=GenerationOptions(max_tokens=5), system_prompt=prompt)
        restored.restore(saved)
        list(restored.chat('Follow-up'))
        self.assertEqual(backend.requests[-1], [Message('system', prompt), *saved, Message('user', 'Follow-up')])
        self.assertEqual(len(backend.requests), 2)

    def test_identity_is_counted_and_not_charged_to_evidence_allowance(self):
        backend = FakeBackend(limit=20000)
        prompt = runtime_system_prompt()
        options = GenerationOptions(max_tokens=5)
        core = DwindyCore(backend, options=options, system_prompt=prompt)
        backend.limit = backend.count_tokens([Message('system', prompt), Message('user', 'Hello')]) + 4
        with self.assertRaises(ContextLimitError):
            list(core.chat('Hello'))
        self.assertFalse(backend.requests)
        backend.limit += 1
        list(core.chat('Hello'))
        backend.limit = 20000
        events = list(core.chat('Follow-up', evidence=Evidence((), max_tokens=1, fallback='plain')))
        self.assertEqual(events[0].retrieval['status'], 'not_used')
        self.assertEqual(backend.requests[-1][0], Message('system', prompt))
