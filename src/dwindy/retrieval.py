"""Concrete, bounded SQLite FTS5 retrieval; no language model is loaded."""
from pathlib import Path
import re
import sqlite3

from .evidence import Passage, Source

APPLICATION_ID = 0x44575249  # DWRI, distinct from conversation storage
SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE documents (
 id TEXT PRIMARY KEY NOT NULL, source_path TEXT NOT NULL, name TEXT NOT NULL,
 format TEXT NOT NULL, content_hash TEXT NOT NULL, indexed_at TEXT NOT NULL,
 chunker_version INTEGER NOT NULL, source_type TEXT NOT NULL DEFAULT 'local_text'
);
CREATE TABLE chunks (
 id INTEGER PRIMARY KEY, chunk_key TEXT UNIQUE NOT NULL,
 document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, heading TEXT NOT NULL,
 start INTEGER NOT NULL, end INTEGER NOT NULL, line_start INTEGER NOT NULL,
 line_end INTEGER NOT NULL, text_hash TEXT NOT NULL,
 UNIQUE(document_id,ordinal)
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(name,heading,body,tokenize='unicode61');
"""
PROJECT_SCHEMA = """
CREATE TABLE project_snapshot (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), project_id TEXT NOT NULL,
 name TEXT NOT NULL, snapshot_id TEXT NOT NULL, policy_version INTEGER NOT NULL,
 indexed_at TEXT NOT NULL
);
"""

# General English function words only; fixed before any benchmark run.
STOPWORDS = frozenset("a an the is are was were be been being to of in on at for from with and or not by as it its this that these those what which who where when why how can could would should may must do does did i we you they their our your me my under than then only".split())


class RetrievalError(RuntimeError):
    def __init__(self, code="retrieval_unavailable"):
        super().__init__("Local retrieval is unavailable; no model-only fallback was performed.")
        self.code = code


def words(text):
    """Case-folded Unicode alphanumeric runs: the tokenization every query uses."""
    return [t.casefold() for t in re.findall(r"[^\W_]+", text, re.UNICODE)]


def query_terms(query):
    """The exact terms a query searches for: first 32 unique non-stopwords."""
    return list(dict.fromkeys(t for t in words(query) if t not in STOPWORDS))[:32]


def match_query(query):
    if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 2048:
        raise ValueError("Retrieval query must be nonblank and at most 2048 UTF-8 bytes.")
    # No raw operators, prefixes, SQL or FTS syntax cross this boundary.
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in query_terms(query))


def validate_index(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if (db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
            or version not in (1, 2)
            or db.execute("PRAGMA quick_check").fetchall() != [("ok",)]
            or db.execute("PRAGMA foreign_key_check").fetchone() is not None):
        raise RetrievalError()
    expected = sqlite3.connect(":memory:")
    try:
        expected.executescript(SCHEMA + (PROJECT_SCHEMA if version == 2 else ""))
        sql = "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
        if db.execute(sql).fetchall() != expected.execute(sql).fetchall():
            raise RetrievalError()
    finally:
        expected.close()
    if db.execute("SELECT count(*) FROM chunks").fetchone() != db.execute("SELECT count(*) FROM chunks_fts").fetchone():
        raise RetrievalError()
    if db.execute("SELECT 1 FROM chunks c LEFT JOIN chunks_fts f ON f.rowid=c.id WHERE f.rowid IS NULL LIMIT 1").fetchone():
        raise RetrievalError()
    if version == 2 and db.execute("SELECT count(*) FROM project_snapshot").fetchone()[0] != 1:
        raise RetrievalError()


class RetrievalIndex:
    """Read-only index, owned by one worker. Stop the server before manifest sync."""
    def __init__(self, path):
        self.connection = None
        self.project_snapshot = None
        try:
            self.connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True,
                                              timeout=1, isolation_level=None)
            # Validate with default tuple rows for predictable metadata comparison.
            validate_index(self.connection)
            self.connection.execute("PRAGMA query_only=ON")
            self.connection.execute("PRAGMA cache_size=-2048")
            self.connection.row_factory = sqlite3.Row
            if self.connection.execute("PRAGMA user_version").fetchone()[0] == 2:
                self.project_snapshot = dict(self.connection.execute(
                    "SELECT project_id,name,snapshot_id,indexed_at FROM project_snapshot").fetchone())
                self.project_snapshot['freshness'] = 'not_checked'
        except (OSError, sqlite3.Error, RetrievalError) as exc:
            self.close()
            raise RetrievalError() from exc

    def search(self, query, limit=3):
        expression = match_query(query)
        if type(limit) is not int or not 1 <= limit <= 12:
            raise ValueError("Invalid result limit")
        if not expression:
            return ()
        try:
            rows = self.connection.execute("""
                SELECT c.*,d.name,d.source_path,d.content_hash,d.source_type,f.body,
                       bm25(chunks_fts,2.0,2.0,1.0) AS score
                FROM chunks_fts f JOIN chunks c ON c.id=f.rowid
                JOIN documents d ON d.id=c.document_id
                WHERE chunks_fts MATCH ?
                ORDER BY score,d.id,c.ordinal LIMIT 12
                """, (expression,)).fetchall()
            result, seen = [], set()
            for row in rows:
                if row["text_hash"] in seen or any(
                    p.source.document_id == row["document_id"] and
                    min(p.source.end,row["end"]) > max(p.source.start,row["start"])
                    for p in result):
                    continue
                seen.add(row["text_hash"])
                project = self.project_snapshot if row['source_type'].startswith('project_') else None
                result.append(Passage(Source(row["document_id"], row["chunk_key"], row["name"],
                    row["source_path"], row["content_hash"], row["line_start"], row["line_end"],
                    row["start"], row["end"], row["heading"], row["source_type"],
                    project['project_id'] if project else None,
                    project['snapshot_id'] if project else None), row["body"], row["score"]))
                if len(result) == limit:
                    break
            return tuple(result)
        except sqlite3.Error as exc:
            raise RetrievalError("retrieval_busy" if getattr(exc,"sqlite_errorcode",0) & 255 in
                                 (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED) else "retrieval_unavailable") from exc

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
