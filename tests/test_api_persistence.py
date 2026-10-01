import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from test_api import TestClient, create_app
from test_api_http import live_server, wait_for, BlockingBackend
from test_terminal import FakeBackend
from dwindy.backend import BackendError, Completion, TextDelta
from dwindy.config import Config
from dwindy.persistence import StorageError
from dwindy.server import ApiConfig


class ApiPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(self.temp) / "chat.db"
        self.model = Config(Path("unused.gguf"), max_tokens=5)

    def app(self, backend=None, **options):
        self.backend = backend or FakeBackend(limit=1000)
        return create_app(self.model, ApiConfig(database_path=str(self.path), **options), backend=self.backend)

    def client(self, app):
        return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1234))

    def rows(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT user_text,assistant_text FROM turns ORDER BY turn_number").fetchall()

    def test_restart_and_expiry_restore_only_retained_window_and_delete_disk_only(self):
        app = self.app(FakeBackend(limit=20))
        with self.client(app) as client:
            key = client.post("/v1/chat", json={"message": "12345678"}).json()["conversation_id"]
            result = client.post("/v1/chat", json={"message": "abcdefgh", "conversation_id": key})
            self.assertEqual(result.json()["dropped_turns"], 1)
            self.assertEqual(len(self.rows()), 2)
        app = self.app()
        with self.client(app) as client:
            self.assertTrue(client.get("/v1/health").json()["persistence_enabled"])
            client.post("/v1/chat", json={"message": "again", "conversation_id": key})
            self.assertEqual([m.content for m in self.backend.requests[-1]], ["abcdefgh", "ok", "again"])
            app.state.dwindy.conversations[key].touched = time.monotonic() - 2000
            client.post("/v1/chat", json={"message": "after expiry", "conversation_id": key})
            self.assertIn("again", [m.content for m in self.backend.requests[-1]])
        with self.client(self.app()) as client:
            self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 204)
            self.assertEqual(client.post("/v1/chat", json={"message": "gone", "conversation_id": key}).status_code, 404)
        self.assertEqual(self.rows(), [])

    def test_confirmed_write_failure_rolls_back_core_and_sse_never_completes(self):
        app = self.app()
        with self.client(app) as client:
            key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
            for stream in (False, True):
                with patch.object(app.state.dwindy.store, "append", side_effect=StorageError("storage_full")):
                    result = client.post("/v1/chat", json={"message": "failed", "conversation_id": key, "stream": stream})
                self.assertIn("storage_full", result.text)
                self.assertNotIn("event: completed", result.text)
                self.assertEqual(len(self.rows()), 1)
                self.assertEqual([m.content for m in app.state.dwindy.conversations[key].core.snapshot()], ["one", "ok"])
            client.post("/v1/chat", json={"message": "next", "conversation_id": key})
            self.assertEqual([m.content for m in self.backend.requests[-1]], ["one", "ok", "next"])

    def test_uncertain_write_quarantines_api(self):
        app = self.app()
        with self.client(app) as client:
            with patch.object(app.state.dwindy.store, "append", side_effect=StorageError(uncertain=True)):
                response = client.post("/v1/chat", json={"message": "one"})
            self.assertEqual(response.status_code, 503)
            self.assertFalse(app.state.dwindy.conversations)
            self.assertEqual(client.get("/v1/health").status_code, 503)
            self.assertEqual(client.post("/v1/chat", json={"message": "two"}).status_code, 503)

    def test_delete_failure_keeps_cache_and_database(self):
        app = self.app()
        with self.client(app) as client:
            key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
            with patch.object(app.state.dwindy.store, "delete", side_effect=StorageError("storage_busy")):
                self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 503)
            self.assertIn(key, app.state.dwindy.conversations)
            self.assertEqual(len(self.rows()), 1)

    def test_empty_failure_and_length(self):
        class Backend(FakeBackend):
            def generate(self, messages, options):
                if messages[-1].content == "fail":
                    raise BackendError("private")
                yield TextDelta(" " if messages[-1].content == "empty" else "partial answer")
                yield Completion("length", 1, 1)
        with self.client(self.app(Backend(limit=1000))) as client:
            for message in ("fail", "empty"):
                self.assertEqual(client.post("/v1/chat", json={"message": message}).status_code, 500)
            self.assertEqual(self.rows(), [])
            self.assertEqual(client.post("/v1/chat", json={"message": "length"}).json()["finish_reason"], "length")
            self.assertEqual(len(self.rows()), 1)

    def test_disabled_has_no_storage_and_restart_forgets(self):
        with patch("dwindy.api.ConversationStore", side_effect=AssertionError("no SQLite")):
            app = create_app(self.model, backend=FakeBackend())
            with self.client(app) as client:
                key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
            with self.client(create_app(self.model, backend=FakeBackend())) as client:
                self.assertEqual(client.post("/v1/chat", json={"message": "next", "conversation_id": key}).status_code, 404)
        self.assertFalse(self.path.exists())

    def test_invalid_database_fails_before_model_load(self):
        self.path.write_bytes(b"private unrelated data")
        with patch("dwindy.llama_backend.LlamaBackend") as model:
            with self.assertRaises(StorageError):
                with self.client(create_app(self.model, ApiConfig(database_path=str(self.path)))):
                    pass
            model.assert_not_called()
        self.assertEqual(self.path.read_bytes(), b"private unrelated data")

    def test_disconnect_during_save_keeps_lease_until_durable_settlement(self):
        app = self.app()
        entered, release = threading.Event(), threading.Event()
        with live_server(app) as (client, server, thread):
            key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
            original = app.state.dwindy.store.append
            def blocked(*args):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("test save barrier")
                return original(*args)
            with patch.object(app.state.dwindy.store, "append", side_effect=blocked):
                try:
                    with client.stream("POST", "/v1/chat", json={"message": "two", "conversation_id": key, "stream": True}) as response:
                        lines = response.iter_lines()
                        while next(lines) != "event: delta":
                            pass
                        self.assertTrue(entered.wait(5))
                    self.assertTrue(client.get("/v1/health").json()["busy"])
                    self.assertEqual(client.post("/v1/chat", json={"message": "blocked"}).status_code, 503)
                    self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 409)
                    self.assertEqual(len(self.rows()), 1)
                finally:
                    release.set()
                wait_for(lambda: not client.get("/v1/health").json()["busy"])
            self.assertEqual(len(self.rows()), 2)
        with self.client(self.app()) as client:
            client.post("/v1/chat", json={"message": "three", "conversation_id": key})
            self.assertEqual([m.content for m in self.backend.requests[-1]], ["one", "ok", "two", "ok", "three"])

    def test_disconnect_native_cleanup_does_not_persist_partial_turn(self):
        backend = BlockingBackend()
        app = self.app(backend)
        with live_server(app) as (client, server, thread):
            key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
            backend.armed = True
            try:
                with client.stream("POST", "/v1/chat", json={"message": "cancel", "conversation_id": key, "stream": True}) as response:
                    for line in response.iter_lines():
                        if line == "event: delta":
                            break
                    self.assertTrue(backend.inside_next.wait(5))
                backend.allow_next.set()
                self.assertTrue(backend.inside_cleanup.wait(5))
                self.assertTrue(client.get("/v1/health").json()["busy"])
            finally:
                backend.allow_next.set()
                backend.allow_cleanup.set()
            wait_for(lambda: not client.get("/v1/health").json()["busy"])
            self.assertEqual(self.rows(), [("one", "ok")])

    def test_shutdown_waits_for_save_and_no_success_before_commit(self):
        app = self.app()
        entered, release = threading.Event(), threading.Event()
        with live_server(app) as (client, server, thread):
            original = app.state.dwindy.store.append
            def blocked(*args):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("save barrier")
                return original(*args)
            with patch.object(app.state.dwindy.store, "append", side_effect=blocked):
                try:
                    with client.stream("POST", "/v1/chat", json={"message": "one", "stream": True}) as response:
                        lines = response.iter_lines()
                        while next(lines) != "event: delta":
                            pass
                        self.assertTrue(entered.wait(5))
                        self.assertEqual(self.rows(), [])
                        server.should_exit = True
                        wait_for(lambda: not app.state.dwindy.ready)
                        self.assertTrue(thread.is_alive())
                        self.assertIsNotNone(app.state.dwindy.store.connection)
                        release.set()
                        remaining = "\n".join(lines)
                        self.assertIn("event: error", remaining)
                        self.assertNotIn("event: completed", remaining)
                finally:
                    release.set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertIsNone(app.state.dwindy.store.connection)
            self.assertEqual(len(self.rows()), 1)

    def test_restore_reserves_id_and_backend_before_database_await(self):
        with self.client(self.app()) as client:
            key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
        app = self.app()
        entered, release = threading.Event(), threading.Event()
        with live_server(app) as (client, server, thread):
            original = app.state.dwindy.store.load
            def blocked(*args):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("load barrier")
                return original(*args)
            from concurrent.futures import ThreadPoolExecutor
            with patch.object(app.state.dwindy.store, "load", side_effect=blocked), ThreadPoolExecutor(max_workers=1) as worker:
                future = worker.submit(client.post, "/v1/chat", json={"message": "two", "conversation_id": key})
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertEqual(client.post("/v1/chat", json={"message": "same", "conversation_id": key}).status_code, 409)
                    self.assertEqual(client.post("/v1/chat", json={"message": "other"}).status_code, 503)
                    self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 409)
                finally:
                    release.set()
                self.assertEqual(future.result(5).status_code, 200)

    def test_idle_delete_during_inference(self):
        backend = BlockingBackend()
        app = self.app(backend)
        with live_server(app) as (client, server, thread):
            key = client.post("/v1/chat", json={"message": "delete me"}).json()["conversation_id"]
            backend.armed = True
            try:
                with client.stream("POST", "/v1/chat", json={"message": "active", "stream": True}) as response:
                    for line in response.iter_lines():
                        if line == "event: delta":
                            break
                    self.assertTrue(backend.inside_next.wait(5))
                    self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 204)
            finally:
                backend.allow_next.set()
                backend.allow_cleanup.set()
            wait_for(lambda: not client.get("/v1/health").json()["busy"])
            self.assertEqual(self.rows(), [])

    def test_completion_delivery_follows_commit_and_lease_release(self):
        app = self.app()
        observed = []
        rows = self.rows
        class Observe:
            def __init__(self, app):
                self.app = app
            async def __call__(self, scope, receive, send):
                async def checked(message):
                    if message["type"] == "http.response.body" and b'"finish_reason"' in message.get("body", b""):
                        observed.append((app.state.dwindy.busy, len(rows())))
                    await send(message)
                await self.app(scope, receive, checked)
        app.add_middleware(Observe)
        with self.client(app) as client:
            for stream in (False, True):
                self.assertEqual(client.post("/v1/chat", json={"message": "one", "stream": stream}).status_code, 200)
        self.assertEqual(observed, [(False, 1), (False, 2)])

    def test_delivery_failure_after_commit_is_not_reported_as_inference_rollback(self):
        app = self.app()
        class FailDelivery:
            def __init__(self, app):
                self.app = app
            async def __call__(self, scope, receive, send):
                async def failing(message):
                    if b"event: completed" in message.get("body", b""):
                        raise OSError("synthetic transport failure")
                    await send(message)
                await self.app(scope, receive, failing)
        app.add_middleware(FailDelivery)
        with self.client(app) as client:
            response = client.post("/v1/chat", json={"message": "one", "stream": True})
            self.assertIn("delivery_uncertain", response.text)
            self.assertNotIn("inference_failed", response.text)
            self.assertEqual(len(self.rows()), 1)

    def test_overlapping_storage_operations_are_rejected_without_queue(self):
        app = self.app()
        entered, release = threading.Event(), threading.Event()
        with live_server(app) as (client, server, thread):
            key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
            original = app.state.dwindy.store.delete
            def blocked(*args):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("delete barrier")
                return original(*args)
            from concurrent.futures import ThreadPoolExecutor
            with patch.object(app.state.dwindy.store, "delete", side_effect=blocked), ThreadPoolExecutor(max_workers=1) as worker:
                future = worker.submit(client.delete, "/v1/conversations/" + key)
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 409)
                    response = client.delete("/v1/conversations/" + "b" * 32)
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["error"]["code"], "storage_busy")
                    self.assertEqual(client.get("/v1/health").status_code, 200)
                finally:
                    release.set()
                self.assertEqual(future.result(5).status_code, 204)
