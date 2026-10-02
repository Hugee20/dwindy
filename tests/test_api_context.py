import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

try:
    import pathspec  # noqa: F401  Optional dwindy[project] dependency.
except ImportError:
    pathspec = None

from project_support import materialize
from test_api import create_app, TestClient
from test_terminal import FakeBackend
from dwindy import context_policy
from dwindy.config import Config, ConfigError
from dwindy.evidence import GUIDANCE, UNAVAILABLE_GUIDANCE
from dwindy.persistence import StorageError
from dwindy.retrieval import RetrievalError
from dwindy.server import ApiConfig

sys.path.insert(0, str(Path(__file__).parent))
from context.evaluate import evaluate_failures

EXTRA = Path(__file__).parent/'context'/'extra'


def model_outcome(messages):
    """Classify what the model actually received, independently of response metadata."""
    system = messages[0].content if messages and messages[0].role == 'system' else ''
    if UNAVAILABLE_GUIDANCE in system:
        return 'unavailable'
    if 'Local entries:\n' in messages[-1].content:
        return 'context' if 'Source 1 ' in messages[-1].content else 'honest_empty'
    return 'direct'


@unittest.skipIf(pathspec is None, 'requires the optional dwindy[project] dependency')
class ApiContextTests(unittest.TestCase):
    def setUp(self):
        from dwindy.project import synchronize
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(EXTRA, self.root/'extra')
        synchronize(materialize(self.root, documents_manifest='extra/collection.toml'))
        self.index = self.root/'index.sqlite3'
        self.backend = FakeBackend(limit=10000)
        self.model = Config(Path('unused.gguf'), max_tokens=5)

    def client(self, **config):
        config.setdefault('retrieval_index_path', str(self.index))
        app = create_app(self.model, ApiConfig(**config), backend=self.backend)
        return TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1))

    def chat(self, client, body):
        before = len(self.backend.requests)
        response = client.post('/v1/chat', json=body)
        self.assertLessEqual(len(self.backend.requests) - before, 1)  # One model call per turn, at most.
        return response

    def test_configured_index_defaults_to_auto(self):
        # FakeBackend counts characters, so give evidence a character-sized allowance.
        with self.client(retrieval_context_tokens=4000) as client:
            self.assertEqual(client.get('/v1/health').json()['retrieval_default'], 'auto')
            hello = self.chat(client, {'message': 'Hello!'}).json()['retrieval']
            self.assertEqual(hello, dict(mode='auto', attempted=False, status='not_used', reason='conversational', sources=[]))
            self.assertEqual(model_outcome(self.backend.requests[-1]), 'direct')
            found = self.chat(client, {'message': 'How do I reserve a microscope?'}).json()['retrieval']
            self.assertEqual((found['status'], found['reason']), ('supplied', 'relevant_match'))
            self.assertEqual(found['sources'][0]['source_path'], 'docs/tasks/reservations.md')
            self.assertEqual(self.backend.requests[-1][-1].content.splitlines()[-1], 'How do I reserve a microscope?')
            directed = self.chat(client, {'message': 'What does this system do?', 'stream': True}).text
            started = json.loads(next(l[6:] for l in directed.splitlines() if l.startswith('data: ')))
            self.assertTrue(started['retrieval']['query_normalized'])
            self.assertEqual(self.backend.requests[-1][-1].content.splitlines()[-1], 'What does this system do?')

    def test_off_and_explicit_values_preserve_m7_exactly(self):
        with self.client(retrieval_default='off') as client:
            self.assertEqual(client.get('/v1/health').json()['retrieval_default'], 'off')
            plain = self.chat(client, {'message': 'How do I reserve a microscope?'}).json()
            self.assertNotIn('retrieval', plain)
            omitted = self.backend.requests[-1]
        with self.client() as client:
            self.assertNotIn('retrieval', self.chat(client, {'message': 'How do I reserve a microscope?', 'retrieval': False}).json())
            self.assertEqual(self.backend.requests[-1], omitted)
            forced = self.chat(client, {'message': 'Hello!', 'retrieval': True}).json()['retrieval']
            self.assertEqual(set(forced), {'status', 'sources'})  # Unchanged M6 shape for on.
            for value in (None, 'always', 1):
                self.assertEqual(client.post('/v1/chat', json={'message': 'hi', 'retrieval': value}).status_code, 422)
            self.assertEqual(client.post('/v1/chat', json={'message': 'x' * 2049, 'retrieval': True}).status_code, 422)
            long = self.chat(client, {'message': 'x' * 2049}).json()['retrieval']
            self.assertEqual(long['reason'], 'message_too_long')

    def test_without_index(self):
        app = create_app(self.model, ApiConfig(), backend=self.backend)
        with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1)) as client:
            self.assertNotIn('retrieval_default', client.get('/v1/health').json())
            self.assertNotIn('retrieval', client.post('/v1/chat', json={'message': 'hi'}).json())
            auto = client.post('/v1/chat', json={'message': 'hi', 'retrieval': 'auto'}).json()['retrieval']
            self.assertEqual((auto['reason'], auto['attempted']), ('no_index', False))
            self.assertEqual(client.post('/v1/chat', json={'message': 'hi', 'retrieval': True}).json()['error']['code'],
                             'retrieval_disabled')

    def test_configuration(self):
        for config in (dict(retrieval_default='on', retrieval_index_path='x.sqlite3'), dict(retrieval_default='auto'),
                       dict(retrieval_default=True, retrieval_index_path='x.sqlite3')):
            with self.assertRaises(ConfigError): ApiConfig(**config).validate()

    def test_startup_notice_names_default_and_opt_out(self):
        import io
        from dwindy import server
        (self.root/'model.gguf').write_bytes(b'unused')
        (self.root/'model.toml').write_text("model_path = 'model.gguf'\n", encoding='utf-8')
        for extra, expected in (('', 'Local context: auto by default'), ('retrieval_default = "off"\n', 'Local context: off by default')):
            (self.root/'api.toml').write_text(f"retrieval_index_path = 'index.sqlite3'\n{extra}", encoding='utf-8')
            with patch('uvicorn.Server') as uvicorn_server, patch('sys.stderr', new_callable=io.StringIO) as err:
                uvicorn_server.return_value.started = True
                server.main(['--config', str(self.root/'model.toml'), '--api-config', str(self.root/'api.toml')])
            self.assertIn(expected, err.getvalue())
            self.assertIn('retrieval_default', err.getvalue())

    def test_frozen_failure_injection(self):
        def run(case):
            with self.client() as client:
                app_state = client.app.state.dwindy
                with patch.object(app_state.index, 'search', side_effect=RetrievalError(case['inject'])):
                    before = len(self.backend.requests)
                    if case['surface'] == 'retrieve':
                        response = client.post('/v1/retrieve', json={'query': case['message']})
                    else:
                        body = {'message': case['message']}
                        if case['mode'] == 'on':
                            body['retrieval'] = True
                        response = client.post('/v1/chat', json=body)
                data = response.json()
                observed = dict(http_status=response.status_code)
                if 'error' in data:
                    observed['error_code'] = data['error']['code']
                else:
                    meta = data['retrieval']
                    observed.update(outcome=model_outcome(self.backend.requests[-1]), attempted=meta['attempted'],
                                    status=meta['status'], reason=meta['reason'])
                self.assertLessEqual(len(self.backend.requests) - before, 1)
                return observed
        result = evaluate_failures(run, fallback_adopted=context_policy.CONSTRAINED_FALLBACK)
        self.assertEqual(result['correct'], result['cases'], result['rows'])
        with patch.object(context_policy, 'CONSTRAINED_FALLBACK', False):
            rejected = evaluate_failures(run, fallback_adopted=False)
        self.assertEqual(rejected['correct'], rejected['cases'], rejected['rows'])

    def test_busy_storage_worker_is_a_busy_retrieval(self):
        with self.client() as client:
            with patch.object(client.app.state.dwindy, 'storage', AsyncMock(side_effect=StorageError('storage_busy'))):
                meta = self.chat(client, {'message': 'What does this app do?'}).json()['retrieval']
                self.assertEqual((meta['status'], meta['reason']), ('unavailable', 'retrieval_busy'))
                self.assertEqual(model_outcome(self.backend.requests[-1]), 'unavailable')
                meta = self.chat(client, {'message': 'How long is a loan?'}).json()['retrieval']
                self.assertEqual((meta['status'], meta['reason']), ('unavailable', 'retrieval_busy'))
                self.assertEqual(model_outcome(self.backend.requests[-1]), 'direct')

    def test_persistence_stores_only_original_turns(self):
        from contextlib import closing
        import sqlite3
        with self.client(database_path=str(self.root/'conversation.db')) as client:
            client.post('/v1/chat', json={'message': 'What does this system do?'})
            with patch.object(client.app.state.dwindy.index, 'search', side_effect=RetrievalError('retrieval_busy')):
                client.post('/v1/chat', json={'message': 'Who uses this app?'})
        with closing(sqlite3.connect(self.root/'conversation.db')) as db:
            self.assertEqual([row[0] for row in db.execute('SELECT user_text FROM turns ORDER BY 1')],
                             ['What does this system do?', 'Who uses this app?'])


if __name__ == '__main__':
    unittest.main()
