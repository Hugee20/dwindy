from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_api import create_app, TestClient
from test_api_http import live_server, wait_for
from test_terminal import FakeBackend
from dwindy.config import Config
from dwindy.ingest import sync
from dwindy.retrieval import RetrievalError
from dwindy.server import ApiConfig


class ApiRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ,{},clear=True))
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.index=self.root/'index.sqlite3'
        sync(Path(__file__).parent/'retrieval/collection.toml',self.index)
        self.backend=FakeBackend(limit=10000)
        self.model=Config(Path('unused.gguf'),max_tokens=5)

    def app(self,persistent=False):
        return create_app(self.model,ApiConfig(retrieval_index_path=str(self.index),
            database_path=str(self.root/'conversation.db') if persistent else None),backend=self.backend)

    def client(self,app):
        return TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',1))

    def test_model_free_retrieve_and_explicit_chat_opt_in(self):
        app=self.app()
        with self.client(app) as client:
            schemas=client.get('/openapi.json').json()['components']['schemas']
            self.assertEqual(schemas['RetrievalMetadata']['properties']['status']['enum'],
                             ['supplied','no_match','budget_exhausted'])
            self.assertIn('text',schemas['RetrievalMatch']['properties'])
            result=client.post('/v1/retrieve',json={'query':'Helios retry delay'}).json()
            self.assertTrue(result['matches'])
            self.assertEqual(self.backend.requests,[])
            reply=client.post('/v1/chat',json={'message':'Helios retry delay','retrieval':True}).json()
            self.assertEqual(reply['retrieval']['status'],'supplied')
            self.assertLessEqual(len(reply['retrieval']['sources']),3)
            self.assertEqual(app.state.dwindy.conversations[reply['conversation_id']].core.snapshot()[0].content,'Helios retry delay')
            plain=client.post('/v1/chat',json={'message':'hello'}).json()
            self.assertNotIn('retrieval',plain)
            self.assertEqual(len(self.backend.requests[-1]),1)

    def test_sse_no_match_and_budget_status(self):
        with self.client(self.app()) as client:
            response=client.post('/v1/chat',json={'message':'Zircon submarine coordinates','retrieval':True,'stream':True})
            payload=json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith('data: ')))
            self.assertEqual(payload['retrieval'],dict(status='no_match',sources=[]))
            self.assertIn('event: completed',response.text)

    def test_persistence_stores_only_original_question_and_restores_without_passages(self):
        app=self.app(True)
        with self.client(app) as client:
            reply=client.post('/v1/chat',json={'message':'Amber lending duration','retrieval':True}).json()
            key=reply['conversation_id']
        with closing(sqlite3.connect(self.root/'conversation.db')) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT user_text,assistant_text FROM turns').fetchall(),[('Amber lending duration','ok')])
        with self.client(self.app(True)) as client:
            client.post('/v1/chat',json={'message':'continue','conversation_id':key})
            self.assertEqual([m.content for m in self.backend.requests[-1]],['Amber lending duration','ok','continue'])

    def test_disabled_failure_invalid_input_and_security(self):
        with self.client(create_app(self.model,backend=self.backend)) as client:
            self.assertEqual(client.post('/v1/retrieve',json={'query':'hi'}).json()['error']['code'],'retrieval_disabled')
            self.assertEqual(client.post('/v1/chat',json={'message':'hi','retrieval':True}).status_code,503)
        app=self.app()
        with self.client(app) as client:
            for body in ({'query':'x'*2049},{'query':' '},{'query':'hello','path':'secret'},{'query':23}):
                self.assertEqual(client.post('/v1/retrieve',json=body).status_code,422)
            self.assertEqual(client.post('/v1/retrieve',json={'query':'x'},headers={'Origin':'https://evil.invalid'}).status_code,403)
            with patch.object(app.state.dwindy.index,'search',side_effect=RetrievalError()):
                result=client.post('/v1/chat',json={'message':'hello','retrieval':True})
                self.assertEqual(result.json()['error']['code'],'retrieval_unavailable')
            self.assertEqual(self.backend.requests,[])

    def test_disconnect_waits_for_retrieval_and_does_not_generate(self):
        app=self.app()
        entered,release=threading.Event(),threading.Event()
        with live_server(app) as (client,server,thread):
            original=app.state.dwindy.index.search
            def blocked(*args):
                entered.set()
                if not release.wait(10): raise RuntimeError('barrier')
                return original(*args)
            import httpx
            with patch.object(app.state.dwindy.index,'search',side_effect=blocked):
                try:
                    with self.assertRaises(httpx.ReadTimeout):
                        client.post('/v1/chat',json={'message':'Amber','retrieval':True},timeout=.2)
                    self.assertTrue(entered.is_set())
                    self.assertTrue(client.get('/v1/health').json()['busy'])
                    self.assertEqual(client.post('/v1/chat',json={'message':'busy'}).status_code,503)
                finally: release.set()
                wait_for(lambda:not client.get('/v1/health').json()['busy'])
            self.assertEqual(self.backend.requests,[])

    def test_retrieval_requires_existing_bearer_security_and_closes_index(self):
        token='synthetic-local-test-token-1234567890'
        with patch.dict(os.environ,{'DWINDY_API_TOKEN':token}):
            app=self.app()
            with self.client(app) as client:
                self.assertEqual(client.post('/v1/retrieve',json={'query':'cedar'}).status_code,401)
                response=client.post('/v1/retrieve',json={'query':'cedar'},headers={'Authorization':'Bearer '+token})
                self.assertEqual(response.status_code,200)
            self.assertIsNone(app.state.dwindy.index.connection)

    def test_retrieval_configuration_is_separate_and_validated(self):
        from dwindy.server import load_api_config
        config=self.root/'api.toml'
        config.write_text('retrieval_index_path="index.sqlite3"\nretrieval_context_tokens=321\n')
        value=load_api_config(config)
        self.assertEqual(Path(value.retrieval_index_path),self.index)
        self.assertEqual(value.retrieval_context_tokens,321)
        for values in ({'retrieval_context_tokens':0},{'retrieval_context_tokens':True},
                       {'retrieval_index_path':str(self.index),'database_path':str(self.index)}):
            with self.assertRaises(ValueError): ApiConfig(**values).validate()
