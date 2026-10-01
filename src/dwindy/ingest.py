"""Explicit local UTF-8 manifest sync. No discovery, model, or network access."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import tomllib

from .retrieval import APPLICATION_ID, SCHEMA, SCHEMA_VERSION, RetrievalError, validate_index

CHUNKER_VERSION = 1
TARGET, HARD, OVERLAP = 1000, 1600, 120
MAX_FILE, MAX_TOTAL, MAX_DOCUMENTS = 1024*1024, 10*1024*1024, 1000


def chunks(text, markdown=False):
    """Yield heading/start/end spans; hard-split only oversized blocks."""
    blocks, offset, start, heading, block_heading, fence = [], 0, 0, "", "", None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line) if markdown else None
        new_heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*$", line) if markdown and fence is None else None
        if new_heading or (not line.strip() and fence is None):
            if text[start:offset].strip():
                blocks.append((block_heading,start,offset))
            start = offset
            if new_heading:
                heading = new_heading.group(1)[:256]
            block_heading = heading
        if marker:
            if fence is None:
                fence = marker.group(1)[0]
            elif marker.group(1)[0] == fence:
                fence = None
        offset += len(line)
    if text[start:offset].strip():
        blocks.append((block_heading,start,offset))
    pending = None
    for title, begin, end in blocks:
        while begin < end and text[begin].isspace(): begin += 1
        while end > begin and text[end-1].isspace(): end -= 1
        if end-begin > HARD:
            if pending:
                yield pending
                pending = None
            while end-begin > HARD:
                cut = max(text.rfind("\n",begin+TARGET//2,begin+TARGET),
                          text.rfind(" ",begin+TARGET//2,begin+TARGET))
                if cut <= begin: cut = begin+TARGET
                yield title, begin, cut
                begin = max(begin+1, cut-OVERLAP)
            if text[begin:end].strip(): yield title,begin,end
        elif pending and pending[0] == title and end-pending[1] <= TARGET:
            pending = title,pending[1],end
        else:
            if pending: yield pending
            pending = title,begin,end
    if pending: yield pending


def manifest_entries(manifest):
    source = Path(manifest).resolve()
    if source.stat().st_size > MAX_FILE: raise ValueError("Manifest is too large")
    with source.open("rb") as handle: data = tomllib.load(handle)
    if set(data) != {"documents"} or not isinstance(data["documents"],list) or len(data["documents"]) > MAX_DOCUMENTS:
        raise ValueError("Expected at most 1000 explicit documents")
    entries, ids, paths = [], set(), set()
    total = 0
    for entry in data["documents"]:
        if not isinstance(entry,dict) or set(entry) != {"id","path","name"}:
            raise ValueError("Each document needs id, path and name only")
        key,path,name = (entry[k] for k in ("id","path","name"))
        if not isinstance(key,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",key) or key in ids:
            raise ValueError("Invalid or duplicate document ID")
        if not isinstance(name,str) or not name.strip() or len(name)>128:
            raise ValueError("Invalid display name")
        if not isinstance(path,str) or Path(path).is_absolute() or ":" in path or "\\" in path:
            raise ValueError("Use relative forward-slash file paths")
        target = (source.parent/path).resolve()
        if not target.is_relative_to(source.parent) or not target.is_file() or target.suffix.lower() not in (".txt",".md") or target in paths:
            raise ValueError("Expected a unique .txt/.md file beneath the manifest directory")
        size = target.stat().st_size
        total += size
        if size > MAX_FILE or total > MAX_TOTAL: raise ValueError("Source byte limit exceeded")
        ids.add(key); paths.add(target)
        entries.append((key,target,target.relative_to(source.parent).as_posix(),name))
    return entries


def sync(manifest, index, max_mib=128):
    entries = manifest_entries(manifest)
    target = Path(index).expanduser().resolve()
    if target in {entry[1] for entry in entries} or target == Path(manifest).resolve():
        raise ValueError("Index must not overwrite input")
    if type(max_mib) is not int or max_mib < 1: raise ValueError("Invalid index cap")
    new = not target.exists()
    if new:
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("xb"): pass
    db = sqlite3.connect(target, timeout=1,isolation_level=None)
    result = dict(indexed=0,unchanged=0,deleted=0)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA cache_size=-2048")
        if new:
            db.executescript("BEGIN IMMEDIATE;" + SCHEMA + f"PRAGMA application_id={APPLICATION_ID};PRAGMA user_version={SCHEMA_VERSION};COMMIT;")
        validate_index(db)
        if db.execute("PRAGMA journal_mode").fetchone()[0] != "delete": raise RetrievalError()
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        pages = max_mib*1024*1024//page_size
        if db.execute("PRAGMA page_count").fetchone()[0] > pages: raise ValueError("Index exceeds configured cap")
        db.execute(f"PRAGMA max_page_count={pages}")
        db.execute("BEGIN IMMEDIATE")
        def remove(key):
            db.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE document_id=?)",(key,))
            db.execute("DELETE FROM documents WHERE id=?",(key,))
        old_ids = {r[0] for r in db.execute("SELECT id FROM documents")}
        total = 0
        for key,path,logical,name in entries:
            with path.open("rb") as handle: raw = handle.read(MAX_FILE+1)
            total += len(raw)
            if len(raw)>MAX_FILE or total>MAX_TOTAL: raise ValueError("Source grew beyond byte limit")
            text = raw.decode("utf-8-sig").replace("\r\n","\n").replace("\r","\n")
            if not text.strip() or "\x00" in text: raise ValueError("Empty or binary input")
            digest = hashlib.sha256(raw).hexdigest()
            old = db.execute("SELECT content_hash,source_path,name,chunker_version FROM documents WHERE id=?",(key,)).fetchone()
            if old == (digest,logical,name,CHUNKER_VERSION):
                result["unchanged"] += 1
                continue
            remove(key)
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)",(key,logical,name,path.suffix.lower(),digest,
                       datetime.now(timezone.utc).isoformat(),CHUNKER_VERSION,"local_text"))
            for ordinal,(heading,start,end) in enumerate(chunks(text,path.suffix.lower()==".md")):
                body = text[start:end]
                chunk_key = hashlib.sha256(f"{key}:{digest}:{CHUNKER_VERSION}:{ordinal}".encode()).hexdigest()
                rowid = db.execute("INSERT INTO chunks(chunk_key,document_id,ordinal,heading,start,end,line_start,line_end,text_hash) VALUES (?,?,?,?,?,?,?,?,?)",
                    (chunk_key,key,ordinal,heading,start,end,text.count("\n",0,start)+1,text.count("\n",0,end-1)+1,hashlib.sha256(body.encode()).hexdigest())).lastrowid
                db.execute("INSERT INTO chunks_fts(rowid,name,heading,body) VALUES (?,?,?,?)",(rowid,name,heading,body))
            result["indexed"] += 1
        for key in old_ids-{e[0] for e in entries}:
            remove(key); result["deleted"] += 1
        db.execute("COMMIT")
        return result
    except BaseException:
        if db.in_transaction: db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["sync"])
    parser.add_argument("--manifest",required=True)
    parser.add_argument("--index",required=True)
    parser.add_argument("--max-mib",type=int,default=128)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(sync(args.manifest,args.index,args.max_mib)))
        return 0
    except (OSError,ValueError,sqlite3.Error,RetrievalError):
        print("Index sync failed. Check manifest, local files, encoding, size limits and index compatibility. Existing indexed content was not partially replaced.",file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
