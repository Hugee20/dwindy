from reach_history_support import reach, module
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import pathspec  # noqa: F401  Needed only for the project-index rows.
except ImportError:
    pathspec = None

from project_support import materialize
from reach_support import ReplayTransport, combined_body, no_network
from test_api import TestClient
create_app = module("api").create_app
from test_terminal import FakeBackend
from dwindy.config import Config, ConfigError
ApiConfig = module("server").ApiConfig

sys.path.insert(0, str(Path(__file__).parent))
from reach.evaluate import evaluate_permission

TOKEN = 'synthetic-reach-test-token-1234567890abcd'
EXTRA = Path(__file__).parent/'context'/'extra'


@unittest.skipIf(pathspec is None, 'requires the optional dwindy[project] dependency')
class ApiReachTests(unittest.TestCase):
    def setUp(self):
        from dwindy.project import synchronize
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        # Reach was not adopted in M10; these tests keep verifying the dormant, frozen contract.
        self.enterContext(patch.object(reach, 'REACH_ADOPTED', True))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(EXTRA, self.root/'extra')
        synchronize(materialize(self.root, documents_manifest='extra/collection.toml'))
        self.index = self.root/'index.sqlite3'
        self.model = Config(Path('unused.gguf'), max_tokens=5)

    def client(self, config, replay, token=False):
        env = {'DWINDY_API_TOKEN': TOKEN} if token else {}
        with patch.dict(os.environ, env, clear=True):
            app = create_app(self.model, config, backend=FakeBackend(limit=20000), reach_backend=reach.WikipediaBackend(transport=replay))
        return TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1))

    def test_frozen_permission_matrix(self):
        def run(row):
            deployment = dict(reach_provider=row['deployment']['reach_provider'], reach_default=row['deployment']['reach_default'],
                              retrieval_index_path=str(self.index) if row['index'] else None)
            try:
                config = ApiConfig(**deployment); config.validate()
            except ConfigError:
                return dict(config_error=True)
            replay = ReplayTransport(combined_body('latest_python'))
            host = 'host_context' in row['body']
            with no_network(allow_loopback=True) as attempts, self.client(config, replay, token=host) as client:
                response = client.post('/v1/chat', json=row['body'],
                                       headers={'Authorization': 'Bearer ' + TOKEN} if host else {})
            self.assertEqual(attempts, [])
            data, observed = response.json(), dict(http_status=response.status_code, network_calls=len(replay.urls))
            if 'error' in data:
                observed['error_code'] = data['error']['code']
                return observed
            meta = data.get('reach') or {}
            observed.update(reach_used=meta.get('used', False), reason=meta.get('reason'), provider=meta.get('provider'),
                            query=meta.get('query'), query_matches_request=replay.sent_queries() == [meta.get('query')])
            return observed
        result = evaluate_permission(run)
        self.assertEqual(result['correct'], 20, [r for r in result['rows'] if not r['correct']])

    def test_shipped_release_refuses_reach(self):
        with patch.object(reach, 'REACH_ADOPTED', False):
            with self.assertRaisesRegex(ConfigError, 'adoption rule'):
                ApiConfig(reach_provider='wikipedia').validate()
            app = create_app(self.model, ApiConfig(), backend=FakeBackend(limit=20000))
            with no_network(allow_loopback=True) as attempts, TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1)) as client:
                self.assertEqual(client.post('/v1/chat', json={'message': 'latest python?', 'reach': True}).json()['error']['code'], 'reach_disabled')
            self.assertEqual(attempts, [])

    def test_unconfigured_deployment_is_byte_identical_and_offline(self):
        with no_network(allow_loopback=True) as attempts:
            app = create_app(self.model, ApiConfig(), backend=(backend := FakeBackend(limit=20000)))
            with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1)) as client:
                plain = client.post('/v1/chat', json={'message': 'What is photosynthesis?'}).json()
                self.assertNotIn('reach', plain)
                self.assertEqual([m.content for m in backend.requests[-1]], ['What is photosynthesis?'])
                fresh = client.post('/v1/chat', json={'message': 'Who is the current CEO of Microsoft?'}).json()
                self.assertEqual(fresh['reach'], dict(used=False, reason='reach_disabled', notice=True))
                self.assertEqual(backend.requests[-1][0].content, reach.HONESTY_NOTICE)
        self.assertEqual(attempts, [])

    def test_used_reach_metadata_stream_and_no_persistence(self):
        replay = ReplayTransport(combined_body('android_version'))
        config = ApiConfig(reach_provider='wikipedia', reach_default='auto', database_path=str(self.root/'c.db'),
                           retrieval_context_tokens=6000)
        with no_network(allow_loopback=True), self.client(config, replay) as client:
            stream = client.post('/v1/chat', json={'message': 'What is the latest version of Android?', 'stream': True}).text
            self.assertIn('"provider": "wikipedia"', stream)
            self.assertIn('"query": "latest version android"', stream)
            self.assertIn('"supplied": true', stream)
            self.assertNotIn('"retrieval": {"status": "supplied"', stream)  # Web results are not local sources.
        with closing(sqlite3.connect(self.root/'c.db')) as db:
            stored = ' '.join(a + b for a, b in db.execute('SELECT user_text, assistant_text FROM turns'))
        self.assertNotIn('Android 17', stored)
        self.assertNotIn('External search results', stored)


if __name__ == '__main__':
    unittest.main()
