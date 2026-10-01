"""Local completed-turn archive. Used only by the opt-in HTTP application."""

from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3

from .backend import Message

APPLICATION_ID = 0x44574E44  # DWND
SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE conversations (
    id TEXT PRIMARY KEY NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    context_start_turn INTEGER NOT NULL CHECK (context_start_turn >= 1)
);
CREATE TABLE turns (
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL CHECK (turn_number >= 1),
    user_text TEXT NOT NULL CHECK (length(user_text) > 0),
    assistant_text TEXT NOT NULL CHECK (length(assistant_text) > 0),
    finish_reason TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    PRIMARY KEY (conversation_id, turn_number)
);
"""


class StorageError(RuntimeError):
    def __init__(self, code="storage_unavailable", *, uncertain=False):
        super().__init__("Conversation storage is unavailable; no success was acknowledged.")
        self.code, self.uncertain = code, uncertain


class ConversationStore:
    """One connection, constructed/used/closed on its owning storage worker.

    Only one Dwindy process may use a database. SQL transactions are short and
    never span model generation. No automatic migrations, pruning or fallback.
    """

    def __init__(self, path, max_mib=128):
        self.connection = None
        self.quarantined = False
        path = Path(path)
        try:
            new = not path.exists()
            if new:
                path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation: never initialize over a preexisting file.
                with path.open("xb"):
                    pass
            self.connection = sqlite3.connect(path, timeout=1, isolation_level=None)
            db = self.connection
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            if new:
                db.executescript("BEGIN IMMEDIATE;" + SCHEMA +
                                 f"PRAGMA application_id={APPLICATION_ID};"
                                 f"PRAGMA user_version={SCHEMA_VERSION};COMMIT;")
            self._validate()
            # Do not convert an unexpected journal configuration silently.
            if db.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                raise StorageError()
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA cache_size=-2048")
            size = db.execute("PRAGMA page_size").fetchone()[0]
            limit = max_mib * 1024 * 1024 // size
            if db.execute("PRAGMA page_count").fetchone()[0] > limit:
                raise StorageError("storage_full")
            db.execute(f"PRAGMA max_page_count={limit}")
        except (OSError, sqlite3.Error, StorageError) as exc:
            self.close()
            if isinstance(exc, StorageError):
                raise
            raise StorageError() from exc

    def _validate(self):
        db = self.connection
        if (db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION
                or db.execute("PRAGMA quick_check").fetchall() != [("ok",)]
                or db.execute("PRAGMA foreign_key_check").fetchone() is not None):
            raise StorageError()
        # Exact owned schema; reject triggers, views and unexpected alterations.
        expected = sqlite3.connect(":memory:")
        try:
            expected.executescript(SCHEMA)
            query = "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
            if db.execute(query).fetchall() != expected.execute(query).fetchall():
                raise StorageError()
        finally:
            expected.close()

    def _ensure(self):
        if self.quarantined or self.connection is None:
            raise StorageError(uncertain=True)

    def _failure(self, exc):
        code = getattr(exc, "sqlite_errorcode", 0) & 255
        safe = code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_FULL)
        self.quarantined = not safe
        return StorageError("storage_full" if code == sqlite3.SQLITE_FULL else
                            "storage_busy" if safe else "storage_unavailable",
                            uncertain=not safe)

    def load(self, key):
        self._ensure()
        try:
            row = self.connection.execute("SELECT context_start_turn FROM conversations WHERE id=?", (key,)).fetchone()
            if row is None:
                return None
            rows = self.connection.execute(
                "SELECT turn_number,user_text,assistant_text FROM turns WHERE conversation_id=? AND turn_number>=? ORDER BY turn_number",
                (key, row[0])).fetchall()
            if not rows or any(r[0] != row[0] + i or not isinstance(r[1], str) or not r[1].strip()
                               or not isinstance(r[2], str) or not r[2].strip() for i, r in enumerate(rows)):
                self.quarantined = True
                raise StorageError(uncertain=True)
            return tuple(message for _, user, assistant in rows
                         for message in (Message("user", user), Message("assistant", assistant)))
        except sqlite3.Error as exc:
            raise self._failure(exc) from exc

    def _transaction(self, operation):
        self._ensure()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            result = operation()
            self.connection.execute("COMMIT")
            return result
        except sqlite3.Error as exc:
            try:
                if self.connection.in_transaction:
                    self.connection.execute("ROLLBACK")
            except sqlite3.Error:
                self.quarantined = True
                raise StorageError(uncertain=True) from exc
            raise self._failure(exc) from exc
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            raise

    def append(self, key, snapshot, finish_reason):
        if not re.fullmatch(r"[A-Za-z0-9_-]{32}", key) or len(snapshot) < 2 or len(snapshot) % 2:
            raise ValueError("Invalid completed conversation")
        now = datetime.now(timezone.utc).isoformat()

        def write():
            db = self.connection
            number = db.execute("SELECT COALESCE(MAX(turn_number),0)+1 FROM turns WHERE conversation_id=?", (key,)).fetchone()[0]
            start = number - len(snapshot) // 2 + 1
            if start < 1:
                raise ValueError("Retained context exceeds saved transcript")
            db.execute("INSERT OR IGNORE INTO conversations VALUES (?,?,?,?)", (key, now, now, start))
            db.execute("INSERT INTO turns VALUES (?,?,?,?,?,?)", (key, number, snapshot[-2].content,
                       snapshot[-1].content, finish_reason, now))
            db.execute("UPDATE conversations SET context_start_turn=?,updated_at=? WHERE id=?", (start, now, key))
        self._transaction(write)

    def delete(self, key):
        return self._transaction(lambda: self.connection.execute("DELETE FROM conversations WHERE id=?", (key,)).rowcount > 0)

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
