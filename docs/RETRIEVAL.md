# M6 local document retrieval

Retrieval is opt-in and local. SQLite FTS5/BM25 finds passages in an explicitly supplied
collection; the language model does not ingest files, choose files or perform the search.
No embeddings, model download, network call, project discovery, reranker or new runtime
dependency is introduced. Python's SQLite build must include FTS5; unsupported builds fail
clearly. Windows/Python 3.13/SQLite 3.45.3 is the validated environment.

## Ingest an explicit collection

Keep your source files and manifest in a private local directory. For example:

```toml
# collection.toml -- the complete authoritative collection, not an incremental patch
[[documents]]
id = "manual"
path = "manual.md"
name = "Equipment manual"

[[documents]]
id = "policy"
path = "policies/lending.txt"
name = "Lending policy"
```

Only these three document fields are accepted. IDs are unique ASCII letters/digits/underscore/
hyphen, 1-64 characters; names are nonblank and at most 128 characters. Paths use forward
slashes and resolve beneath the manifest directory. Absolute paths, URLs, escaping symlinks,
duplicate physical files, missing files and other extensions fail. Only UTF-8 .txt/.md is
supported; UTF-8 BOM is accepted, CRLF/CR becomes LF, NUL/binary and blank files fail.
No unlisted file is opened. There is no recursive scan, README selection or remote fetch.

From the repository root in PowerShell, with the API stopped:

```powershell
.\.venv\Scripts\python.exe -m dwindy.ingest sync --manifest .\data\collection.toml --index .\data\retrieval.sqlite3
```

The command prints indexed/unchanged/deleted counts. Limits: 1,000 documents, 1 MiB per
source, 10 MiB aggregate source bytes, 1 MiB manifest and default 128 MiB main index file
(`--max-mib` can change that cap). Journals and transient disk space are additional. Sources
are size-checked again when read. Documents are hashed from raw bytes; changed hash, logical
path, display name or chunker version causes replacement. Unchanged documents retain IDs
and indexed timestamps. Omitted IDs are deleted. `documents = []` deletes the whole collection.
Bad input or a failed write rolls back the entire synchronization of an existing index.
An unsuccessful first sync can leave an empty valid schema; retry after fixing input.

Stop the API before syncing, then restart. Hot reload and concurrent ingestion are not
supported. There is no HTTP ingestion endpoint. A bad/incompatible existing database is
never silently overwritten or migrated. Rebuild into a new explicitly chosen file if needed.

## Configuration and operation

Add these top-level fields to your API TOML, not your model TOML:

```toml
retrieval_index_path = "data/retrieval.sqlite3"
retrieval_context_tokens = 768
```

Paths resolve relative to that TOML. The conversation database and retrieval index must be
different files. The index must already exist; explicit missing/corrupt/incompatible settings
fail startup rather than disable retrieval silently. Omit retrieval_index_path to disable it.
The 768-token incremental allowance is a provisional configurable default, not a fixed
architectural requirement. Model configuration and generation settings are untouched.

```powershell
.\.venv\Scripts\python.exe -m dwindy.server --config config.local.toml --api-config api.local.toml --chat-root .
```

Retrieval works with conversation persistence on or off. Terminal chat stays unchanged.
The optional API's existing Host/Origin/bearer/TLS/body-limit protections also cover retrieval.
All API clients share the configured collection; this is not per-user document authorization.

## Index and ranking

The separate SQLite file has application_id `0x44575249` (DWRI), user_version 1, and chunker
version 1. Startup checks identity, version, schema, SQLite integrity, foreign keys and chunk/
FTS row correspondence. Unknown versions require an explicit future migration/rebuild.
M7 project indexes use user_version 2 with one extra table; manifest sync refuses them and
ranking is identical. See [project awareness](PROJECT_AWARENESS.md).

| Table | Stored columns |
| --- | --- |
| documents | id (PK), source_path, name, format, content_hash, indexed_at (UTC), chunker_version, source_type |
| chunks | id (integer PK), chunk_key (unique), document_id (FK cascade), ordinal, heading, start, end, line_start, line_end, text_hash; unique(document_id, ordinal) |
| chunks_fts | FTS5 name, heading, body; rowid matches chunks.id; unicode61 tokenizer |

Body text lives in the FTS table. Source paths are manifest-relative, never resolved machine
paths. Offsets are half-open Unicode character offsets into normalized text; lines are 1-based
inclusive. Chunk keys hash document ID, source-content hash, chunker version and ordinal.
Source type is local_text, not a claim of authority. The indexed timestamp describes ingestion.

Chunking is deterministic and unchanged from its initial bounds: 1,000-character target,
1,600 hard maximum, 120-character overlap only while splitting oversized blocks. Markdown
ATX headings and blank-line paragraphs form boundaries; fenced content is kept together
where it fits. Same-heading adjacent paragraphs can combine up to the target. An indivisible
block between target and hard maximum remains whole. Oversized blocks split near whitespace;
headings are retained as metadata. This is a small text chunker, not a complete Markdown parser.

Queries are nonblank and at most 2,048 UTF-8 bytes. The implementation extracts Unicode
alphanumeric terms, case-folds, removes a fixed general-English function-word list, deduplicates
and uses the first 32 terms. Individually quoted terms are OR-combined in a parameter-bound
MATCH expression. User-supplied FTS operators, wildcards and SQL are never executed as syntax.
FTS5 unicode61 tokenization and BM25 weights are name=2, heading=2, body=1. Lower scores sort
first, then document ID and ordinal for ties. There is no relevance threshold or semantic
answerability detector. At most 12 raw candidates are fetched. Exact text-hash duplicates and
overlapping spans from the same source are suppressed; there is no unbounded refill search.
Standalone retrieval returns at most three; chat can budget up to twelve filtered candidates.

This lexical implementation does not understand synonyms, negation, temporal authority or
missing fields. Related documents may not contain an answer. Broad shared words can put an
irrelevant short passage first. The [frozen benchmark report](M6_VALIDATION.md) records these
failures without changing the benchmark or tuning against holdout results.

## Core context boundary

`core.chat(question, evidence=Evidence(tuple_of_passages, max_tokens=768))` is optional.
Evidence is a narrow immutable candidate collection (at most twelve, each at most 1,600
characters), not a plugin mechanism. Core uses backend.count_tokens, including the actual
chat template, to choose up to three whole passages. It never slices token IDs or calls SQL.

The incremental budget includes retrieval guidance, framing, names and passage text compared
with the original configured system message/question. Core selects fitting passages, then
trims oldest complete history pairs for the existing output reservation. It rechecks the
exact final rendered input against an otherwise identical retained-history prompt; if needed,
it removes the last selected passage and repeats. The full prompt plus configured output
allowance must fit the actual context size. If even guidance/question cannot fit, the request
fails with the existing context-limit error. Templates that cannot represent the retrieval
system guidance fail explicitly; there is no model-specific fallback.

Retrieval guidance treats documents as untrusted information and asks the model to acknowledge
insufficient material. Names/text are JSON-quoted, escaping angle/square delimiters to prevent
common textual role markers from being inserted verbatim. This is mitigation, not an
injection-proof boundary or a universal guarantee for every tokenizer/template. No document
content controls roles, file access, SQL, configuration, ingestion, networking or tools.
The same model can still misinterpret natural-language instructions or leak facts in its answer.

Evidence is transient. Only the original question and generated assistant answer enter Core
history, snapshots and M5 archives. Trimmed evidence never reappears via restoration. An
assistant's answer can repeat source facts and remains normal history; that is not an archived
evidence trail. Cancellation, empty answers, failures, output-limit commits and M5 durable
acknowledgement keep their existing semantics. The no-evidence path preserves the original
model message sequence; no new system instructions or sampling changes apply to normal chat.

## HTTP contract

`GET /v1/health` adds boolean `retrieval_enabled`. No filesystem paths are exposed there.
For an M7 project index only, health, retrieve matches and chat sources add project
identity fields; for this M6 index they are omitted and responses are unchanged.

`POST /v1/retrieve`, Content-Type application/json:

```json
{"query":"How long is an Amber loan?"}
```

The response is `{"matches":[...]}` with zero to three ranked records. Each record has
`document_id`, `chunk_id`, `name`, `source_path`, `content_hash`, `line_start`, `line_end`,
`start`, `end`, `heading`, `source_type`, `text`, and numeric `score`. It has no conversation
side effects and does not invoke the model. It can run while inference is active if the
storage worker is free. It does not prove that returned text answers the query.

`POST /v1/chat` adds optional strict boolean `retrieval` (default false):

```json
{"message":"How long is an Amber loan?","retrieval":true,"stream":true}
```

Existing conversation_id and stream semantics are unchanged. Retrieval-enabled messages have
the same 2,048-byte query limit. JSON success adds `retrieval`; for SSE the `started` event
adds it. No new event names are introduced; delta/completed/error remain unchanged.

```json
{"status":"supplied","sources":[{"document_id":"manual","chunk_id":"...","name":"Equipment manual","source_path":"manual.md","content_hash":"...","line_start":1,"line_end":6,"start":0,"end":260,"heading":"Loans","source_type":"local_text"}]}
```

Sources contain metadata only for passages actually placed in model input, not every candidate.
They omit body/score. `supplied` means one or more passages were supplied, **not** that the
answer is grounded or correct. `no_match` means no candidates survived lexical search and
deduplication; `budget_exhausted` means candidates existed but no whole passage fit. Both
have empty sources and still generate with insufficient-material guidance when that fits.
Without retrieval opt-in, responses omit retrieval metadata and model input is unchanged.
SSE started metadata is not a successful-generation/durable-commit acknowledgement.

The existing error envelope remains `{"error":{"code":"...","message":"..."}}`.
Invalid inputs return 422, context-limit errors keep their existing 422 mapping, and missing
configuration returns 503 retrieval_disabled. Index failures return 503 retrieval_unavailable,
SQLite locks return 503 retrieval_busy, and an occupied storage worker returns the existing
503 storage_busy. No index failure silently falls back to model-only generation. Existing
inference/conversation busy and authentication errors retain their meanings.

The API uses the existing serialized storage worker for index queries and M5 writes. There
is no retrieval queue or additional service. A retrieval-enabled chat retains the global
inference lease through preparation/cleanup. Disconnect waits for any in-flight synchronous
search and generation step to settle before releasing ownership. Shutdown drains both kinds
of request before closing index, conversation database and model handles.

## Privacy, storage and limits

The index contains local document text and names on disk even when conversations are ephemeral.
It is not encrypted. Use physical local storage and normal OS access restrictions; avoid cloud-
synced/network-mapped locations for offline privacy. Queries/answers may expose indexed content
to any authorized API client. Do not index secrets you do not intend those clients to access.
Model output is still untrusted text. No secure erasure is promised for deleted SQLite pages,
rollback journals, filesystem backups, process memory or generated answers.

Rollback journal mode, FULL synchronization, one-second lock timeout and a 2 MiB SQLite cache
are used. The main-file cap does not cap journal size or process RSS. Synchronization is atomic
but reads documents sequentially; it is not an OS-level atomic snapshot of files being edited.
No pruning, auto-discovery, indexing watcher, vacuum schedule or persistence migration is added.
Existing gitignore covers data/, SQLite files and journals. Keep private manifests outside
tracked paths too. The M5 conversation schema remains version 1 and unchanged.

## Validation commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe tests/retrieval_run.py --split dev
.\.venv\Scripts\python.exe tests/retrieval_run.py --split holdout
.\.venv\Scripts\python.exe tests/retrieval_perf.py
.\.venv\Scripts\python.exe tests/smoke_retrieval.py --config eval-results/nonthinking.config.local.toml --browser 'C:\Program Files\Google\Chrome\Application\chrome.exe'
```

The performance script alone uses the existing optional eval dependency psutil. The real-model
smoke uses temporary synthetic files, index and conversation database and never runs the M1
baseline. See [validation results](M6_VALIDATION.md) for measured results and caveats.
