import io
import os
from pathlib import Path
import tempfile
import unittest
from importlib.util import find_spec
from unittest.mock import patch

from dwindy.config import ConfigError
from dwindy.server import ApiConfig, load_api_config, main


class ServerConfigTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_defaults_are_loopback_and_bounded(self):
        config = load_api_config()
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.max_conversations, 16)
        self.assertEqual(config.conversation_idle_seconds, 1800)
        self.assertEqual(config.max_request_bytes, 65536)
        self.assertIsNone(config.validate())

    def test_invalid_api_values(self):
        for values in ({"host": "localhost"}, {"host": 2130706433}, {"port": 0}, {"port": True}, {"port": 65536},
                       {"allow_non_loopback": "false"}, {"max_conversations": 0},
                       {"conversation_idle_seconds": -1}, {"max_request_bytes": 0},
                       {"allowed_hosts": ()}, {"allowed_hosts": ("*",)},
                       {"allowed_origins": ("*",)}, {"allowed_origins": ("null",)},
                       {"allowed_origins": ("http://localhost/",)},
                       {"allowed_origins": ("http://localhost:bad",)},
                       {"token_env": "BAD NAME"}, {"ssl_certfile": "only-cert"}):
            with self.subTest(values=values), self.assertRaises(ConfigError):
                ApiConfig(**values).validate()

    def test_nonloopback_requires_all_three_controls(self):
        for values in ({}, {"allow_non_loopback": True}, {"ssl_certfile": "cert", "ssl_keyfile": "key"}):
            with self.subTest(values=values), self.assertRaises(ConfigError):
                ApiConfig(host="0.0.0.0", **values).validate()
        with patch.dict(os.environ, {"DWINDY_API_TOKEN": "x" * 32}):
            with self.assertRaises(ConfigError):
                ApiConfig(host="0.0.0.0", allow_non_loopback=True).validate()
            with patch("dwindy.server.ssl.SSLContext.load_cert_chain") as load:
                cfg = ApiConfig(host="0.0.0.0", allow_non_loopback=True, ssl_certfile="cert", ssl_keyfile="key")
                self.assertEqual(cfg.validate(), "x" * 32)
                load.assert_called_once()

    def test_bad_token_and_invalid_tls_fail_closed(self):
        for value in ("", "short", "x" * 32 + " ", "é" * 32):
            with patch.dict(os.environ, {"DWINDY_API_TOKEN": value}), self.assertRaises(ConfigError):
                ApiConfig().validate()
        with self.assertRaises(ConfigError):
            ApiConfig(ssl_certfile="missing-cert", ssl_keyfile="missing-key").validate()

    def test_explicit_toml_and_unknown_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "api.toml"
            path.write_text('port=8099\nallowed_origins=["http://localhost:5173"]', encoding="utf-8")
            self.assertEqual(load_api_config(path).port, 8099)
            path.write_text('model_path="forbidden"', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_api_config(path)
            path.write_text('port=[', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_api_config(path)

    def test_bad_binding_fails_before_model_load(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "api.toml"
            path.write_text('host="0.0.0.0"', encoding="utf-8")
            with patch("dwindy.server.load_config") as model, patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(main(["--api-config", str(path)]), 1)
                model.assert_not_called()

    @unittest.skipUnless(find_spec("uvicorn") and find_spec("fastapi"), "Optional API dependencies not installed")
    def test_launcher_pins_safe_server_settings_and_reports_startup_failure(self):
        with patch("dwindy.server.load_config"), patch("dwindy.api.create_app"), \
             patch("uvicorn.Config") as uv_config, patch("uvicorn.Server") as server:
            server.return_value.started = True
            self.assertEqual(main([]), 0)
            settings = uv_config.call_args.kwargs
            self.assertEqual(settings["host"], "127.0.0.1")
            self.assertEqual(settings["workers"], 1)
            for flag in ("reload", "proxy_headers", "access_log", "server_header"):
                self.assertFalse(settings[flag])
            self.assertEqual(settings["timeout_graceful_shutdown"], 1)
            server.return_value.started = False
            self.assertEqual(main([]), 1)
