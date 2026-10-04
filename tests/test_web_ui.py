"""Narrow static hosting and unchanged API security; no real model required."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from starlette.testclient import TestClient
    from dwindy.api import create_app
    from dwindy.web_ui import frontend_files
except ImportError:
    raise unittest.SkipTest("Optional API test dependencies not installed")

from dwindy.config import Config, ConfigError
from test_terminal import FakeBackend

ROOT = Path(__file__).resolve().parents[1]


class WebUiTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"DWINDY_API_TOKEN": "x" * 32})
        env.start(); self.addCleanup(env.stop)
        app = create_app(Config(Path("unused.gguf"), max_tokens=5), backend=FakeBackend(), chat_root=ROOT)
        self.client = self.enterContext(TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 42)))

    def test_bootstrap_is_public_but_all_api_routes_require_token(self):
        self.assertEqual(self.client.get("/chat/").status_code, 200)
        for url in frontend_files(ROOT):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        for url in ("/v1/health", "/openapi.json"):
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post("/v1/chat", json={"message": "hello"}).status_code, 401)
        self.assertEqual(self.client.delete("/v1/conversations/" + "A" * 32).status_code, 401)

    def test_new_and_original_asset_urls_share_exact_bytes(self):
        for name in ('branding/dwindy-lockup.png', 'branding/dwindy-wordmark.png',
                     'chatheads/dwindy-idle.png', 'chatheads/dwindy-working.png'):
            modern = self.client.get('/dwindy/web/assets/' + name)
            legacy = self.client.get('/dwindy/assets/' + name)
            self.assertEqual(modern.status_code, 200)
            self.assertEqual(modern.content, legacy.content)

    def test_method_and_path_do_not_expand_auth_bypass(self):
        for path in ("/dwindy/web/index.html/", "/dwindy/web/standalone.js.map", "/dwindy/web/tests/index.html",
                     "/dwindy/config.local.toml", "/dwindy/assets/branding/PALETTE.md"):
            self.assertEqual(self.client.get(path).status_code, 401, path)
        self.assertEqual(self.client.post("/dwindy/web/index.html").status_code, 401)

    def test_even_authenticated_requests_cannot_read_repository_or_traversal(self):
        self.client.headers["Authorization"] = "Bearer " + "x" * 32
        for path in ("/dwindy/", "/dwindy/web/", "/dwindy/web/%2e%2e/config.local.toml",
                     "/dwindy/web/%2e%2e%2f%2e%2e%2fconfig.local.toml", "/dwindy/.git/config",
                     "/dwindy/src/dwindy/config.py", "/dwindy/assets/chatheads/dwindy-shocked.png"):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_host_origin_and_peer_guards_still_apply_to_public_files(self):
        self.assertEqual(self.client.get("/chat/", headers={"Host": "evil.example"}).status_code, 400)
        self.assertEqual(self.client.get("/chat/", headers={"Origin": "https://evil.example"}).status_code, 403)

    def test_content_types_csp_and_no_secret_in_page(self):
        page = self.client.get("/chat/")
        self.assertNotIn("x" * 32, page.text)
        self.assertIn("script-src 'self'", page.headers["content-security-policy"])
        self.assertEqual(page.headers["x-content-type-options"], "nosniff")
        self.assertIn("text/javascript", self.client.get("/dwindy/web/api-client.js").headers["content-type"])
        self.assertEqual(self.client.head("/dwindy/web/index.html").content, b"")

    def test_disabled_by_default_and_no_openapi_expansion(self):
        self.client.headers["Authorization"] = "Bearer " + "x" * 32
        self.assertEqual(len(self.client.get("/openapi.json").json()["paths"]), 4)
        app = create_app(Config(Path("unused.gguf")), backend=FakeBackend())
        with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 42),
                        headers={"Authorization": "Bearer " + "x" * 32}) as other:
            self.assertEqual(other.get("/chat/").status_code, 404)

    def test_incomplete_bundle_rejected_before_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ConfigError):
                frontend_files(folder)

    def test_resolved_asset_cannot_escape_bundle(self):
        # Simulate an external symlink target without requiring Windows symlink privileges.
        original = Path.resolve
        def resolve(path, *args, **kwargs):
            if path.name == "index.html": return ROOT.parent / "external.html"
            return original(path, *args, **kwargs)
        with patch.object(Path, "resolve", resolve), self.assertRaises(ConfigError):
            frontend_files(ROOT)
