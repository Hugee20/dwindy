"""Real TCP tests with controlled fake inference; no GGUF or external network."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import threading
import time
import unittest
from unittest.mock import patch

try:
    import httpx
    import uvicorn
    from dwindy.api import create_app
except ImportError:
    raise unittest.SkipTest("Optional api and api-test dependencies are not installed")

from dwindy.backend import Completion, TextDelta
from dwindy.config import Config
from dwindy.server import ApiConfig
from test_terminal import FakeBackend


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for HTTP/worker state")


@contextmanager
def live_server(app, startup_timeout=10):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
        loop="asyncio", http="h11", ws="none", proxy_headers=False, access_log=False,
        server_header=False, log_level="critical", timeout_graceful_shutdown=0.1))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        wait_for(lambda: server.started or not thread.is_alive(), timeout=startup_timeout)
        if not server.started:
            raise AssertionError("Server failed startup")
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False) as client:
            yield client, server, thread
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        if thread.is_alive():
            raise AssertionError("Server failed to drain and stop")


class BlockingBackend(FakeBackend):
    def __init__(self):
        super().__init__(limit=1000)
        self.armed = False
        self.inside_next = threading.Event()
        self.allow_next = threading.Event()
        self.inside_cleanup = threading.Event()
        self.allow_cleanup = threading.Event()
        self.model_closed = threading.Event()
        self.cleanup_finished = False
        self.closed_while_running = False

    def generate(self, messages, options):
        if not self.armed:
            yield from super().generate(messages, options)
            return
        self.armed = False
        self.requests.append(list(messages))
        try:
            yield TextDelta("first")
            self.inside_next.set()
            if not self.allow_next.wait(10):
                raise RuntimeError("test did not release native next")
            yield TextDelta("second")
            yield Completion("stop", 1, 2)
        finally:
            self.inside_cleanup.set()
            if not self.allow_cleanup.wait(10):
                raise RuntimeError("test did not release stream cleanup")
            self.cleanup_finished = True
            self.closed_streams += 1

    def close(self):
        if self.inside_next.is_set() and not self.cleanup_finished:
            self.closed_while_running = True
        self.model_closed.set()


class LiveHttpTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.backend = BlockingBackend()
        self.addCleanup(self.backend.allow_next.set)
        self.addCleanup(self.backend.allow_cleanup.set)
        self.app = create_app(Config(Path("unused.gguf"), max_tokens=5), backend=self.backend)

    def first_delta(self, response):
        lines = response.iter_lines()
        key = None
        for line in lines:
            if line.startswith("data: "):
                data = json.loads(line[6:])
                key = data.get("conversation_id", key)
                if "text" in data:
                    return key
        self.fail("No delta delivered")

    def test_disconnect_holds_backend_through_native_next_and_cleanup(self):
        with live_server(self.app) as (client, server, thread):
            key = client.post("/v1/chat", json={"message": "one"}).json()["conversation_id"]
            self.backend.armed = True
            with client.stream("POST", "/v1/chat", json={"message": "cancel", "conversation_id": key, "stream": True}) as response:
                self.assertEqual(self.first_delta(response), key)
                self.assertTrue(self.backend.inside_next.wait(5))
            # Socket closed; native next() is still running.
            self.assertTrue(client.get("/v1/health").json()["busy"])
            same = client.post("/v1/chat", json={"message": "same", "conversation_id": key})
            self.assertEqual(same.status_code, 409)
            self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 409)
            other = client.post("/v1/chat", json={"message": "other"})
            self.assertEqual(other.status_code, 503)
            self.assertEqual(other.headers["retry-after"], "1")
            # Expiry never discards an active conversation.
            self.app.state.dwindy.conversations[key].touched = time.monotonic() - 2000
            self.assertEqual(client.delete("/v1/conversations/" + key).status_code, 409)
            self.backend.allow_next.set()
            self.assertTrue(self.backend.inside_cleanup.wait(5))
            self.assertTrue(client.get("/v1/health").json()["busy"])
            self.assertEqual(client.post("/v1/chat", json={"message": "still busy"}).status_code, 503)
            self.backend.allow_cleanup.set()
            wait_for(lambda: not client.get("/v1/health").json()["busy"])
            self.assertTrue(self.backend.cleanup_finished)
            self.assertEqual(client.post("/v1/chat", json={"message": "next", "conversation_id": key}).status_code, 200)
            self.assertEqual([m.content for m in self.backend.requests[-1] if m.role != "system"], ["one", "ok", "next"])
        self.assertTrue(self.backend.model_closed.is_set())
        self.assertFalse(self.backend.closed_while_running)

    def test_shutdown_waits_for_native_cleanup_before_model_close(self):
        with live_server(self.app) as (client, server, thread):
            self.backend.armed = True
            with client.stream("POST", "/v1/chat", json={"message": "cancel", "stream": True}) as response:
                lines = response.iter_lines()
                for line in lines:
                    if line.startswith("data: ") and "text" in json.loads(line[6:]):
                        break
                self.assertTrue(self.backend.inside_next.wait(5))
                server.should_exit = True
                wait_for(lambda: server.force_exit or not self.app.state.dwindy.ready)
                self.assertFalse(self.backend.model_closed.is_set())
                self.assertTrue(thread.is_alive())
                self.backend.allow_next.set()
                self.assertTrue(self.backend.inside_cleanup.wait(5))
                self.assertFalse(self.backend.model_closed.is_set())
                self.backend.allow_cleanup.set()
                remaining = "\n".join(lines)
                self.assertIn("event: error", remaining)
                self.assertIn('"code": "unavailable"', remaining)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertTrue(self.backend.model_closed.is_set())
        self.assertFalse(self.backend.closed_while_running)

    def test_json_disconnect_reclaims_unexposed_conversation(self):
        # HTTP JSON has no early response headers, so use a raw socket to disconnect.
        with live_server(self.app) as (client, server, thread):
            self.backend.armed = True
            address = ("127.0.0.1", client.base_url.port)
            with socket.create_connection(address, timeout=5) as conn:
                body = b'{"message":"cancel"}'
                conn.sendall(b"POST /v1/chat HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: "
                             + str(len(body)).encode() + b"\r\n\r\n" + body)
                self.assertTrue(self.backend.inside_next.wait(5))
            self.assertTrue(client.get("/v1/health").json()["busy"])
            self.backend.allow_next.set()
            self.assertTrue(self.backend.inside_cleanup.wait(5))
            self.backend.allow_cleanup.set()
            wait_for(lambda: not client.get("/v1/health").json()["busy"])
            self.assertFalse(self.app.state.dwindy.conversations)
            self.assertEqual(client.post("/v1/chat", json={"message": "recovered"}).status_code, 200)

    def test_chunked_body_limit_and_real_security_headers(self):
        self.app = create_app(Config(Path("unused.gguf"), max_tokens=5),
                              ApiConfig(max_request_bytes=40), backend=self.backend)
        with live_server(self.app) as (client, server, thread):
            response = client.post("/v1/chat", content=iter([b'{"message":"', b"x" * 50, b'"}']),
                                   headers={"content-type": "application/json"})
            self.assertEqual(response.status_code, 413)
            self.assertEqual(client.get("/v1/health", headers={"host": "evil.example"}).status_code, 400)
            self.assertEqual(client.get("/v1/health", headers={"origin": "https://evil.example"}).status_code, 403)
            self.assertFalse(self.backend.requests)
