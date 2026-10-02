from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_api import create_app, TestClient
from test_terminal import FakeBackend
from dwindy import api, capabilities
from dwindy.config import Config
from dwindy.server import ApiConfig

sys.path.insert(0, str(Path(__file__).parent))
from tools.evaluate import evaluate_host

TOKEN = 'synthetic-capability-test-token-1234567890'


class ApiCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.backend = FakeBackend(limit=20000)
        self.model = Config(Path('unused.gguf'), max_tokens=5)

    def client(self, token=False, **config):
        env = {'DWINDY_API_TOKEN': TOKEN} if token else {}
        with patch.dict(os.environ, env, clear=True):
            app = create_app(self.model, ApiConfig(**config), backend=self.backend)
        return TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1))

    def model_input(self):
        return '\n'.join(m.content for m in self.backend.requests[-1]) if self.backend.requests else ''

    def test_frozen_host_context_contract(self):
        def run(row):
            database = self.root/(row['id'] + '.db')
            persistent = 'persisted_excludes' in row['expected']
            headers = {'Authorization': 'Bearer ' + TOKEN} if row['authenticated'] else {}
            budget = row['expected'].get('budget_override_tokens', api.HOST_CONTEXT_BUDGET_TOKENS)
            before = len(self.backend.requests)
            with patch.object(api, 'HOST_CONTEXT_BUDGET_TOKENS', budget), \
                    self.client(row['token_configured'], database_path=str(database) if persistent else None) as client:
                response = client.post('/v1/chat', json=row['body'], headers=headers)
                data = response.json()
                observed = dict(http_status=response.status_code)
                if 'error' in data:
                    observed['error_code'] = data['error']['code']
                    self.assertEqual(len(self.backend.requests), before)  # Rejected before any model call.
                    return observed
                self.assertEqual(len(self.backend.requests) - before, 1)
                observed.update(model_input=self.model_input(), capabilities=[c['name'] for c in data.get('capabilities', [])])
                observed['host_context_supplied'] = 'Host-application data' in observed['model_input']
                if persistent:
                    client.post('/v1/chat', json={'message': 'And now?', 'conversation_id': data['conversation_id']}, headers=headers)
                    observed['resumed_input'] = self.model_input()
            if persistent:
                with closing(sqlite3.connect(database)) as db:
                    observed['persisted'] = ' '.join(a + ' ' + b for a, b in db.execute('SELECT user_text, assistant_text FROM turns'))
                with self.client(row['token_configured'], database_path=str(database)) as client:
                    client.post('/v1/chat', json={'message': 'Restart?', 'conversation_id': data['conversation_id']}, headers=headers)
                observed['resumed_input'] += ' ' + self.model_input()
            return observed
        result = evaluate_host(run)
        self.assertEqual(result['correct'], 16, [r for r in result['rows'] if not r['correct']])

    def test_capability_metadata_one_call_and_per_request_clock(self):
        with self.client() as client:
            plain = client.post('/v1/chat', json={'message': 'Hello!'}).json()
            self.assertNotIn('capabilities', plain)
            self.assertEqual(self.model_input(), 'Hello!')
            with patch.object(capabilities, 'datetime') as clock:
                clock.now.side_effect = [datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc),
                                         datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc) + timedelta(days=1)]
                first = client.post('/v1/chat', json={'message': 'What is the date today?'}).json()['capabilities']
                second = client.post('/v1/chat', json={'message': 'What is the date today?'}).json()['capabilities']
            self.assertNotEqual(first[0]['value'], second[0]['value'])
            calc = client.post('/v1/chat', json={'message': 'What is 924 × 17?', 'stream': True}).text
            self.assertIn('"name": "calculator"', calc)
            self.assertIn('924 * 17 = 15708', self.model_input())
            self.assertEqual(len(self.backend.requests), 4)

    def test_openapi_documents_host_context(self):
        with self.client() as client:
            schema = client.get('/openapi.json').json()
        body = schema['paths']['/v1/chat']['post']['requestBody']['content']['application/json']['schema']
        self.assertIn('host_context', body['properties'])
        self.assertIn('HostContextItem', body['$defs'])
        self.assertIn('capabilities', schema['components']['schemas']['ChatReply']['properties'])


if __name__ == '__main__':
    unittest.main()
