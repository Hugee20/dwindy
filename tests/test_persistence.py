from pathlib import Path
import sqlite3
import tempfile
import unittest

from dwindy.backend import Message
from dwindy.persistence import APPLICATION_ID, ConversationStore, StorageError
from dwindy.server import ApiConfig, load_api_config
from dwindy.config import ConfigError

KEY = "a" * 32
PAIR = (Message("user", "  hello 🌲  "), Message("assistant", "answer\n"))


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "data" / "chat.sqlite3"

    def store(self, size=128):
        store = ConversationStore(self.path, size)
        self.addCleanup(store.close)
        return store

    def test_schema_settings_roundtrip_and_windows_handles(self):
        store = self.store()
        db = store.connection
        for pragma, value in (("application_id", APPLICATION_ID), ("user_version", 1),
                              ("journal_mode", "delete"), ("foreign_keys", 1), ("synchronous", 2)):
            self.assertEqual(db.execute("PRAGMA " + pragma).fetchone()[0], value)
        store.append(KEY, PAIR, "length")
        self.assertEqual(store.load(KEY), PAIR)
        self.assertEqual(db.execute("SELECT finish_reason FROM turns").fetchone()[0], "length")
        store.close()
        moved = self.path.with_suffix(".moved")
        self.path.rename(moved)
        moved.rename(self.path)
        self.assertEqual(self.store().load(KEY), PAIR)

    def test_archive_kept_but_trimmed_context_never_restored(self):
        store = self.store()
        store.append(KEY, PAIR, "stop")
        recent = (Message("user", "recent"), Message("assistant", "ok"))
        store.append(KEY, recent, "stop")
        self.assertEqual(store.load(KEY), recent)
        self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0], 2)
        self.assertEqual(store.connection.execute("SELECT context_start_turn FROM conversations").fetchone()[0], 2)

    def test_delete_cascades_and_unknown_does_not_create(self):
        store = self.store()
        self.assertIsNone(store.load(KEY))
        self.assertFalse(store.delete(KEY))
        store.append(KEY, PAIR, "stop")
        self.assertTrue(store.delete(KEY))
        self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0], 0)

    def test_failed_transaction_has_no_partial_pair_or_boundary_change(self):
        store = self.store()
        store.append(KEY, PAIR, "stop")
        bad = (Message("user", "new"), Message("assistant", ""))
        with self.assertRaises(StorageError):
            store.append(KEY, bad, "stop")
        self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0], 1)
        self.assertEqual(store.connection.execute("SELECT context_start_turn FROM conversations").fetchone()[0], 1)

    def test_full_database_rolls_back_and_remains_usable(self):
        store = self.store(1)
        store.append(KEY, PAIR, "stop")
        with self.assertRaises(StorageError) as caught:
            store.append(KEY, (Message("user", "new"), Message("assistant", "x" * 2000000)), "stop")
        self.assertEqual(caught.exception.code, "storage_full")
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(store.load(KEY), PAIR)
        self.assertTrue(store.delete(KEY))

    def test_external_lock_is_bounded_and_recoverable(self):
        store = self.store()
        other = sqlite3.connect(self.path, isolation_level=None)
        try:
            other.execute("BEGIN IMMEDIATE")
            with self.assertRaises(StorageError) as caught:
                store.append(KEY, PAIR, "stop")
            self.assertEqual(caught.exception.code, "storage_busy")
            other.execute("ROLLBACK")
            store.append(KEY, PAIR, "stop")
        finally:
            other.close()

    def test_wrong_version_schema_and_corruption_are_preserved(self):
        for kind in ("version", "schema", "corrupt", "empty"):
            with self.subTest(kind=kind):
                path = Path(self.temp.name) / (kind + ".db")
                if kind in ("corrupt", "empty"):
                    path.write_bytes(b"not a database" if kind == "corrupt" else b"")
                else:
                    store = ConversationStore(path)
                    store.connection.execute("PRAGMA user_version=99" if kind == "version" else "CREATE TABLE surprise(x)")
                    store.close()
                before = path.read_bytes()
                with self.assertRaises(StorageError):
                    ConversationStore(path)
                self.assertEqual(path.read_bytes(), before)

    def test_config_paths_and_invalid_options(self):
        config = Path(self.temp.name) / "api.toml"
        config.write_text("database_path = 'data/chat.db'\ndatabase_max_mib = 2\n")
        self.assertEqual(load_api_config(config).database_path, str((config.parent / "data/chat.db").resolve()))
        self.assertFalse((config.parent / "data").exists())
        for path in ("", ":memory:", "file:chat.db", "https://host/chat", "//host/share", "\\\\host\\share"):
            with self.subTest(path=path), self.assertRaises(ConfigError):
                ApiConfig(database_path=path).validate()
        for size in (0, -1, True, 1.5):
            with self.assertRaises(ConfigError):
                ApiConfig(database_max_mib=size).validate()

    def test_readonly_write_failure_quarantines_without_partial_data(self):
        store = self.store()
        store.connection.execute("PRAGMA query_only=ON")
        with self.assertRaises(StorageError) as caught:
            store.append(KEY, PAIR, "stop")
        self.assertTrue(caught.exception.uncertain)
        self.assertTrue(store.quarantined)
        self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0], 0)
        with self.assertRaises(StorageError):
            store.load(KEY)

    def test_existing_oversize_database_is_not_shrunk(self):
        store = self.store()
        store.append(KEY, (Message("user", "large"), Message("assistant", "x" * 2000000)), "stop")
        store.close()
        size = self.path.stat().st_size
        with self.assertRaises(StorageError) as caught:
            ConversationStore(self.path, 1)
        self.assertEqual(caught.exception.code, "storage_full")
        self.assertEqual(self.path.stat().st_size, size)
