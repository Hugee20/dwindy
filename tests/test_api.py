"""Model-free HTTP contract/security tests; install .[api,api-test] to run."""
import json
from pathlib import Path
import os
import time
import unittest
from unittest.mock import patch

try:
    from starlette.testclient import TestClient
    from dwindy.api import create_app
except ImportError:
    raise unittest.SkipTest("Optional api and api-test dependencies are not installed")

from dwindy.backend import BackendError, Completion, ContextLimitError, TextDelta
from dwindy.config import Config
from dwindy.server import ApiConfig
from test_terminal import FakeBackend


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.backend = FakeBackend()
        self.model = Config(Path("unused.gguf"), max_tokens=5)

    def client(self, config=None, **kwargs):
        self.app = create_app(self.model, config, backend=self.backend)
        client = TestClient(self.app, base_url="http://127.0.0.1", client=("127.0.0.1", 1234), **kwargs)
        return self.enterContext(client)

    def test_json_multiturn_delete_and_isolation(self):
        client = self.client()
        first = client.post("/v1/chat", json={"message": "one"})
        self.assertEqual(first.status_code, 200)
        data = first.json()
        self.assertEqual(set(data), {"conversation_id", "text", "finish_reason", "dropped_turns", "usage"})
        self.assertEqual(data["text"], "ok")
        key = data["conversation_id"]
        self.assertEqual(len(key), 32)
        client.post("/v1/chat", json={"message": "two", "conversation_id": key})
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["one", "ok", "two"])
        other = client.post("/v1/chat", json={"message": "other"}).json()["conversation_id"]
        self.assertNotEqual(other, key)
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["other"])
        self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 204)
        self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 404)
        self.assertEqual(client.post("/v1/chat", json={"message": "again", "conversation_id": key}).status_code, 404)

    def test_sse_contract_and_newline_escaping(self):
        def generate(messages, options):
            yield TextDelta("line one\nline two é")
            yield Completion("length", 3, 4)
        self.backend.generate = generate
        client = self.client()
        result = client.post("/v1/chat", json={"message": "hello", "stream": True})
        self.assertEqual(result.status_code, 200)
        blocks = result.text.strip().split("\n\n")
        self.assertEqual([b.splitlines()[0] for b in blocks], ["event: started", "event: delta", "event: completed"])
        self.assertEqual(json.loads(blocks[1].splitlines()[1][6:]), {"text": "line one\nline two é"})
        self.assertEqual(json.loads(blocks[-1].splitlines()[1][6:]),
                         {"finish_reason": "length", "usage": {"prompt_tokens": 3, "text_tokens": 4}})
        key = json.loads(blocks[0].splitlines()[1][6:])["conversation_id"]
        self.assertEqual(len(self.app.state.dwindy.conversations[key].core._history), 2)

    def test_model_facing_settings_and_text_unchanged(self):
        self.model = Config(Path("unused.gguf"), max_tokens=5, temperature=0.3, seed=17, system_prompt="original")
        client = self.client()
        with patch.object(self.backend, "generate", wraps=self.backend.generate) as generate:
            client.post("/v1/chat", json={"message": "  /reset  "})
        self.assertEqual([m.content for m in generate.call_args.args[0]], ["original", "  /reset  "])
        self.assertEqual(generate.call_args.args[1], self.model.options())

    def test_strict_request_schema(self):
        client = self.client()
        for body in ({}, {"message": " "}, {"message": 4}, {"message": "x", "stream": "true"},
                     {"message": "x", "temperature": 0}, {"message": "x", "conversation_id": "bad"}, []):
            with self.subTest(body=body):
                self.assertEqual(client.post("/v1/chat", json=body).status_code, 422)
        self.assertFalse(self.backend.requests)
        self.assertFalse(self.app.state.dwindy.conversations)

    def test_content_type_json_and_size_limits(self):
        client = self.client(ApiConfig(max_request_bytes=40))
        self.assertEqual(client.post("/v1/chat", content='{"message":"hi"}').status_code, 415)
        for body in ("{", '{"message":NaN}', b'\xff'):
            self.assertEqual(client.post("/v1/chat", content=body, headers={"content-type": "application/json"}).status_code, 400)
        self.assertEqual(client.post("/v1/chat", json={"message": "x" * 50}).status_code, 413)
        self.assertFalse(self.backend.requests)

    def test_context_limit_before_sse_headers_and_capacity_reclaimed(self):
        self.backend.limit = 6
        client = self.client(ApiConfig(max_conversations=1))
        for stream in (False, True):
            result = client.post("/v1/chat", json={"message": "too long", "stream": stream})
            self.assertEqual(result.status_code, 422)
            self.assertEqual(result.json()["error"]["code"], "context_limit")
            self.assertEqual(len(self.app.state.dwindy.conversations), 0)
        self.assertFalse(self.backend.requests)

    def test_whole_turn_trimming(self):
        self.backend.limit = 20
        client = self.client()
        key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
        client.post("/v1/chat", json={"message": "two", "conversation_id": key})
        last = client.post("/v1/chat", json={"message": "three", "conversation_id": key}).json()
        self.assertEqual(last["dropped_turns"], 1)
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["two", "ok", "three"])

    def test_json_failure_is_safe_and_rolls_back(self):
        client = self.client()
        key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
        def fail(messages, options):
            yield TextDelta("partial")
            raise BackendError("SECRET native path")
        with patch.object(self.backend, "generate", side_effect=fail):
            result = client.post("/v1/chat", json={"message": "bad", "conversation_id": key})
        self.assertEqual(result.status_code, 500)
        self.assertNotIn("SECRET", result.text)
        client.post("/v1/chat", json={"message": "next", "conversation_id": key})
        self.assertEqual([m.content for m in self.backend.requests[-1]], ["one", "ok", "next"])

    def test_sse_error_and_no_completed_event(self):
        self.backend.failure = BackendError("SECRET")
        result = self.client().post("/v1/chat", json={"message": "bad", "stream": True})
        self.assertEqual(result.status_code, 200)
        self.assertIn("event: error", result.text)
        self.assertNotIn("event: completed", result.text)
        self.assertNotIn("SECRET", result.text)
        self.assertFalse(self.app.state.dwindy.busy)

    def test_capacity_expiry_and_no_live_eviction(self):
        client = self.client(ApiConfig(max_conversations=1))
        key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
        result = client.post("/v1/chat", json={"message": "two"})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json()["error"]["code"], "conversation_capacity")
        self.app.state.dwindy.conversations[key].touched = time.monotonic() - 1801
        self.assertEqual(client.post("/v1/chat", json={"message": "new"}).status_code, 200)
        self.assertEqual(client.post("/v1/chat", json={"message": "old", "conversation_id": key}).status_code, 404)

    def test_health_schema_and_unavailable(self):
        client = self.client()
        self.assertEqual(client.get("/v1/health").json(), {"status": "ready", "busy": False})
        self.app.state.dwindy.ready = False
        self.assertEqual(client.get("/v1/health").status_code, 503)
        self.assertEqual(client.post("/v1/chat", json={"message": "hi"}).status_code, 503)

    def test_host_origin_and_no_origin_clients(self):
        client = self.client()
        self.assertEqual(client.get("/v1/health", headers={"host": "attacker.example"}).status_code, 400)
        for origin in ("null", "https://attacker.example", "http://127.0.0.1.evil", "http://127.0.0.1/path"):
            self.assertEqual(client.post("/v1/chat", json={"message": "x"}, headers={"origin": origin}).status_code, 403)
        self.assertEqual(client.get("/v1/health", headers={"origin": "http://127.0.0.1"}).status_code, 200)
        self.assertEqual(client.get("/v1/health").status_code, 200)
        self.assertFalse(self.backend.requests)

    def test_cors_explicit_origin_and_preflight(self):
        client = self.client(ApiConfig(allowed_origins=("http://localhost:5173",)))
        headers = {"origin": "http://localhost:5173", "access-control-request-method": "POST",
                   "access-control-request-headers": "authorization,content-type"}
        result = client.options("/v1/chat", headers=headers)
        self.assertEqual(result.status_code, 204)
        self.assertEqual(result.headers["access-control-allow-origin"], headers["origin"])
        self.assertNotIn("access-control-allow-credentials", result.headers)
        headers["access-control-request-headers"] = "x-unapproved"
        self.assertEqual(client.options("/v1/chat", headers=headers).status_code, 403)
        self.assertEqual(client.get("/v1/health", headers={"origin": "http://localhost:5174"}).status_code, 403)

    def test_bearer_applies_to_health_schema_and_chat(self):
        with patch.dict(os.environ, {"DWINDY_API_TOKEN": "a" * 32}):
            client = self.client()
        for path in ("/v1/health", "/openapi.json"):
            self.assertEqual(client.get(path).status_code, 401)
            self.assertEqual(client.get(path, headers={"authorization": "Bearer wrong"}).status_code, 401)
            self.assertEqual(client.get(path, headers={"authorization": "Bearer " + "a" * 32}).status_code, 200)
        self.assertEqual(client.post("/v1/chat", json={"message": "x"}).status_code, 401)
        self.assertEqual(client.options("/v1/chat", headers={"origin": "http://127.0.0.1",
                         "access-control-request-method": "POST"}).status_code, 204)

    def test_duplicate_security_headers_rejected(self):
        client = self.client()
        for name, value in (("host", "127.0.0.1"), ("origin", "http://127.0.0.1"), ("authorization", "Bearer x")):
            self.assertEqual(client.get("/v1/health", headers=[(name, value), (name, value)]).status_code, 400)

    def test_no_browser_assets_and_schema_has_only_application_routes(self):
        client = self.client()
        self.assertEqual(set(client.get("/openapi.json").json()["paths"]),
                         {"/v1/chat", "/v1/health", "/v1/conversations/{conversation_id}"})
        self.assertEqual(client.get("/docs").status_code, 404)
        self.assertEqual(client.get("/redoc").status_code, 404)

    def test_nonlocal_peer_rejected_even_if_host_allowed(self):
        app = create_app(self.model, backend=self.backend)
        with TestClient(app, base_url="http://127.0.0.1", client=("192.0.2.1", 1234)) as client:
            self.assertEqual(client.get("/v1/health").status_code, 403)

    def test_nonloopback_app_requires_https_even_when_run_by_another_server(self):
        config = ApiConfig(host="0.0.0.0", allow_non_loopback=True, ssl_certfile="cert", ssl_keyfile="key")
        with patch.dict(os.environ, {"DWINDY_API_TOKEN": "a" * 32}), \
             patch("dwindy.server.ssl.SSLContext.load_cert_chain"):
            app = create_app(self.model, config, backend=self.backend)
        headers = {"authorization": "Bearer " + "a" * 32}
        with TestClient(app, base_url="http://127.0.0.1", client=("192.0.2.1", 1234)) as client:
            self.assertEqual(client.get("/v1/health", headers=headers).status_code, 403)
            self.assertEqual(client.get("https://127.0.0.1/v1/health", headers=headers).status_code, 200)

    def test_model_startup_failure_fails_lifespan(self):
        app = create_app(self.model)
        with patch("dwindy.llama_backend.LlamaBackend", side_effect=BackendError("load failed")):
            with self.assertRaises(BackendError):
                with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1234)):
                    self.fail("Startup should fail")
        self.assertFalse(app.state.dwindy.ready)
        self.assertTrue(app.state.dwindy.executor._shutdown)

    def test_application_owns_backend_lifetime(self):
        app = create_app(self.model, backend=self.backend)
        with patch.object(self.backend, "close") as close:
            with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1234)) as client:
                client.post("/v1/chat", json={"message": "x"})
                close.assert_not_called()
            close.assert_called_once()
        self.assertFalse(app.state.dwindy.conversations)
