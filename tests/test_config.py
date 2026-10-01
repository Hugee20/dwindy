import tempfile
from pathlib import Path
import unittest

from dataclasses import asdict
from dwindy.config import Config, ConfigError, RESERVED_TEMPLATE_ARGUMENTS, load_config


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "fake.gguf").write_bytes(b"test fixture, not a model")
        self.path = self.root / "config.toml"

    def write(self, extra=""):
        self.path.write_text('model_path = "fake.gguf"\n' + extra, encoding="utf-8")
        return self.path

    def test_relative_model_resolves_against_config(self):
        cfg = load_config(self.write())
        self.assertEqual(cfg.model_path, self.root / "fake.gguf")
        self.assertEqual(cfg.options().max_tokens, 256)

    def test_explicit_override(self):
        self.path.write_text('model_path = "missing.gguf"', encoding="utf-8")
        self.assertEqual(load_config(self.path, self.root / "fake.gguf").model_path,
                         self.root / "fake.gguf")

    def test_invalid_settings(self):
        for setting in ('threads = true', 'context_size = 0', 'max_tokens = -1',
                        'max_tokens = 4096', 'temperature = nan', 'temperature = inf',
                        'temperature = true', 'temperature = 3', 'seed = -1',
                        'seed = 4294967296', 'system_prompt = 1', 'typo = 1'):
            with self.subTest(setting=setting), self.assertRaises(ConfigError):
                load_config(self.write(setting))

    def test_missing_model_and_config(self):
        for kwargs in ({}, {"model_path": "missing.gguf"}, {"path": self.path}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ConfigError):
                load_config(**kwargs)

    def test_reject_remote_model(self):
        for path in ("https://example.com/model.gguf", "//server/model.gguf",
                     "\\\\server\\model.gguf"):
            with self.subTest(path=path), self.assertRaises(ConfigError):
                load_config(model_path=path)

    def test_bad_toml(self):
        self.path.write_text("broken = [", encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_config(self.path)

    def test_template_kwargs_default_and_scalar_types(self):
        self.assertEqual(load_config(self.write()).chat_template_kwargs, {})
        cfg = load_config(self.write('[chat_template_kwargs]\nenable_thinking = false\n'
                                     'label = "plain"\ncount = 2\nratio = 0.5\n'))
        expected = {"enable_thinking": False, "label": "plain", "count": 2, "ratio": 0.5}
        self.assertEqual(cfg.chat_template_kwargs, expected)
        self.assertEqual(asdict(cfg)["chat_template_kwargs"], expected)

    def test_reject_invalid_template_values(self):
        for value in ('[]', '"text"', 'true', '1'):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                load_config(self.write(f'chat_template_kwargs = {value}'))
        for value in ('[]', '{}', 'nan', 'inf', '-inf', '2026-10-01', '12:00:00'):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                load_config(self.write(f'[chat_template_kwargs]\noption = {value}'))

    def test_reserved_template_arguments(self):
        for key in RESERVED_TEMPLATE_ARGUMENTS | {"_private", "bad-name", ""}:
            with self.subTest(key=key), self.assertRaises(ConfigError):
                load_config(self.write(f'[chat_template_kwargs]\n"{key}" = false'))

    def test_direct_config_validates_and_copies_template_kwargs(self):
        with self.assertRaises(ConfigError):
            Config(self.root / "fake.gguf", chat_template_kwargs={"messages": "override"})
        options = {"enable_thinking": False}
        cfg = Config(self.root / "fake.gguf", chat_template_kwargs=options)
        options["enable_thinking"] = True
        self.assertIs(cfg.chat_template_kwargs["enable_thinking"], False)
