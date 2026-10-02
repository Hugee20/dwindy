from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

try:
    import pathspec  # noqa: F401  Optional dwindy[project] dependency.
except ImportError:
    pathspec = None

from project_support import materialize
from test_api import create_app, TestClient
from test_terminal import FakeBackend
from dwindy.config import Config
from dwindy.ingest import sync as manifest_sync
from dwindy.server import ApiConfig


@unittest.skipIf(pathspec is None, 'requires the optional dwindy[project] dependency')
class ApiProjectTests(unittest.TestCase):
    def setUp(self):
        from dwindy.project import synchronize
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.report = synchronize(materialize(self.root))
        self.index = self.root/'index.sqlite3'
        self.backend = FakeBackend(limit=10000)
        self.model = Config(Path('unused.gguf'), max_tokens=5)

    def client(self, persistent=False, index=None):
        app = create_app(self.model, ApiConfig(retrieval_index_path=str(index or self.index),
            database_path=str(self.root/'conversation.db') if persistent else None), backend=self.backend)
        return TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1))

    def test_health_reports_snapshot_without_project_root(self):
        with self.client() as client:
            health = client.get('/v1/health').json()
        snapshot = health['project_snapshot']
        self.assertEqual(set(snapshot), {'project_id', 'name', 'snapshot_id', 'indexed_at', 'freshness'})
        self.assertEqual((snapshot['project_id'], snapshot['snapshot_id'], snapshot['freshness']),
                         ('lantern', self.report['snapshot_id'], 'not_checked'))
        self.assertNotIn(str(self.root).casefold(), json.dumps(health).casefold())

    def test_retrieve_and_chat_carry_project_provenance(self):
        with self.client() as client:
            match = client.post('/v1/retrieve', json={'query': 'loan duration'}).json()['matches'][0]
            self.assertEqual((match['source_path'], match['project_id'], match['snapshot_id']),
                             ('docs/policy.md', 'lantern', self.report['snapshot_id']))
            reply = client.post('/v1/chat', json={'message': 'What is the loan duration?', 'retrieval': True}).json()
            self.assertEqual(reply['retrieval']['status'], 'supplied')
            self.assertTrue(all(s['project_id'] == 'lantern' for s in reply['retrieval']['sources']))
            self.assertTrue(self.backend.requests[-1][-1].content.startswith('Local entries:'))
            stream = client.post('/v1/chat', json={'message': 'loan duration', 'retrieval': True, 'stream': True}).text
            started = json.loads(next(line[6:] for line in stream.splitlines() if line.startswith('data: ')))
            self.assertEqual(started['retrieval']['sources'][0]['snapshot_id'], self.report['snapshot_id'])
            self.assertIn('event: completed', stream)
            plain = client.post('/v1/chat', json={'message': 'hello', 'retrieval': False}).json()
            self.assertNotIn('retrieval', plain)
            self.assertEqual([m.content for m in self.backend.requests[-1]], ['hello'])

    def test_persistence_on_stores_only_question(self):
        with self.client(persistent=True) as client:
            reply = client.post('/v1/chat', json={'message': 'loan duration', 'retrieval': True}).json()
        with closing(sqlite3.connect(self.root/'conversation.db')) as db:
            self.assertEqual(db.execute('SELECT user_text,assistant_text FROM turns').fetchall(), [('loan duration', 'ok')])
        with self.client(persistent=True) as client:
            client.post('/v1/chat', json={'message': 'continue', 'conversation_id': reply['conversation_id']})
        self.assertEqual([m.content for m in self.backend.requests[-1]], ['loan duration', 'ok', 'continue'])

    def test_m6_index_responses_are_unchanged(self):
        plain = self.root/'plain.sqlite3'
        manifest_sync(Path(__file__).parent/'retrieval/collection.toml', plain)
        with self.client(index=plain) as client:
            self.assertEqual(client.get('/v1/health').json(), {'status': 'ready', 'busy': False,
                             'persistence_enabled': False, 'retrieval_enabled': True,
                             'retrieval_default': 'auto'})
            match = client.post('/v1/retrieve', json={'query': 'Helios retry delay'}).json()['matches'][0]
            self.assertFalse({'project_id', 'snapshot_id'} & match.keys())
            reply = client.post('/v1/chat', json={'message': 'Helios retry delay', 'retrieval': True}).json()
            self.assertFalse(any({'project_id', 'snapshot_id'} & s.keys() for s in reply['retrieval']['sources']))
            self.assertTrue(self.backend.requests[-1][-1].content.startswith('Local entries:'))


if __name__ == '__main__':
    unittest.main()
