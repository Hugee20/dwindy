# M5 local persistence

Persistence is opt-in for the HTTP application. Core and terminal chat still perform no
database I/O. There is no new dependency: storage uses Python's `sqlite3` and one dedicated
storage worker, separate from the existing model worker. No retrieval or historical-context
search is implemented.

## Configuration and startup

Add these top-level settings to the explicitly supplied API TOML:

```toml
database_path = 'data/dwindy.sqlite3'
database_max_mib = 128
```

```powershell
.\.venv\Scripts\python.exe -m dwindy.server --config config.local.toml --api-config api.local.toml --chat-root .
```

Omit `database_path` for unchanged ephemeral operation. Disabled mode creates neither a
database nor a data directory. Relative paths resolve against the API configuration file;
the parent directory is created only when enabled. URLs, SQLite URIs, UNC paths and
`:memory:` are rejected. Use physical local storage; mapped drives and cloud-synced folders
cannot reliably be detected. Do not share one database between running Dwindy processes.

Startup opens and validates storage before loading the model. Configured but unavailable
storage fails startup, without ephemeral fallback. Existing empty, corrupt, unrelated,
altered-schema or unsupported-version files are rejected, never replaced or initialized.
An interrupted first initialization may leave an empty/partial file requiring explicit
operator inspection. Existing databases over the configured cap require a larger explicit
cap before opening; no automatic shrink or pruning occurs.

Schema identity is `PRAGMA application_id = 0x44574E44` (`DWND`), with `user_version = 1`.
Startup checks the owned schema, `quick_check` and foreign keys. Future schema migrations
must be explicit; no migrations or migration framework are currently implemented.

## Stored data and retained context

The exact version-1 schema is the `SCHEMA` constant in `src/dwindy/persistence.py`:

```sql
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
```

Timestamps are UTC ISO-8601 strings. Each row contains one completed user/assistant pair,
with exact text and the actual finish reason. No partial output, failed request, credential,
system prompt, model setting, native state or evaluation result is stored here. A conversation
record is created together with its first successful turn; empty SSE conversations remain
memory-only until then. IDs retain the existing server-generated 192-bit opaque format.

**Saved transcript** contains all successfully persisted turns until explicit deletion.
**Active model context** contains only the contiguous suffix starting at `context_start_turn`.
Successful trimming advances this boundary while keeping older rows in the archive. Lazy
restoration loads only that suffix, so previously trimmed turns never reappear in context.
No summarization, retrieval, transcript listing or history endpoint is provided.

Core exposes idle-only `snapshot() -> tuple[Message, ...]` and `restore(messages) -> None`.
Snapshot is a detached tuple of immutable completed user/assistant messages, without a
system message. Restore copies and validates complete, nonblank alternating pairs before
replacing state. Invalid input raises `ValueError` without mutation; active-stream calls
raise `RuntimeError`, including suspension at Completion. Neither method calls the backend
or storage. Current application model settings/system prompt remain authoritative. The
next turn uses unchanged context budgeting. Native model state and deterministic output
across process restarts are not promised.

## API lifecycle and durable completion

The three application endpoints remain unchanged. Health adds `persistence_enabled`:

```json
{"status":"ready","busy":false,"persistence_enabled":true}
```

POST accepts the same request and returns the same JSON/SSE payloads. A supplied ID absent
from memory is restored from storage before inference. Unknown/deleted IDs return 404;
they are never silently recreated. Restoration reserves the conversation and backend before
waiting for storage. Existing capacity (16), whole-turn trimming and inference exclusion
remain unchanged. Memory idle expiry (30 minutes) removes only cached Core instances; disk
records have no automatic expiry. Restoring a disk-only ID needs a free memory slot.

After Core succeeds, the adapter closes its stream, obtains its snapshot, and atomically
inserts the new turn and updates the context boundary/timestamp. JSON success and SSE
`completed` follow database COMMIT. SSE deltas are provisional until `completed`.
No database transaction spans model generation. Empty results, errors, missing completion
and cancellation before Core completion save nothing. Nonempty output-limit answers save
normally with `finish_reason="length"`.

A recoverable full/locked database causes SQL rollback and restores Core's pre-turn snapshot.
No JSON success or SSE completed is sent. Errors retain the existing envelope and use 503:

- `storage_busy`: storage admission or SQLite lock busy; Retry-After: 1; no successful save.
- `storage_full`: configured cap or disk capacity reached; no successful save.
- `storage_unavailable`: storage is unusable or the outcome cannot safely be established.
- `delivery_uncertain`: completion delivery failed after a successful turn; do not retry.

Unexpected SQLite/I/O errors are conservatively quarantined, even when rollback appeared
successful. The API stops admitting inference and requires operator inspection/restart;
it does not switch to ephemeral mode. Error bodies disclose no paths or conversation text.
The browser treats unavailable storage as uncertain; it never automatically retries chat.

Pending native work, stream closure and persistence finalization settle before releasing the
lease, including after disconnect or shutdown cancellation. If Core completion wins a race
with disconnect, the turn may be saved without delivery. A new JSON conversation's ID may
also be lost with its response. There is no exactly-once delivery, replay or ID recovery list.

DELETE works for cached or disk-only records. It reserves the ID, commits cascading deletion,
then removes cached Core state and returns 204. Confirmed storage failure preserves existing
state; uncertain failure stops admission. Memory and SQLite are not one distributed
transaction: a process crash after database deletion also destroys its memory cache.
Deletion of active/restoring IDs returns 409. Idle deletion remains available during inference.

One worker owns the SQLite connection with normal thread checks enabled. External storage
operations encountering an active storage operation receive immediate storage_busy; they do
not accumulate executor jobs. Only the single admitted inference finalizer may wait for the
current short operation. Shutdown drains those operations before closing either worker.

## Storage and privacy

SQLite uses DELETE rollback journaling, foreign keys, FULL synchronization, a one-second
lock timeout and a 2 MiB page-cache target. WAL/checkpointing is not enabled. A preexisting
non-DELETE journal mode is rejected instead of silently converted. The 128 MiB default main
database cap uses actual page size and max_page_count; journals/filesystem overhead require
additional free space. The cache setting is a target, not a process-memory hard limit.
Deletes free pages for reuse; file size need not shrink. No automatic VACUUM or pruning runs.

Conversation content is **unencrypted on disk**. OS filesystem permissions apply; IDs are
addresses, not user authorization. All authorized API clients share the existing trust
boundary. Deletion is logical, not forensic erasure: free pages, journals, backups and OS
snapshots may retain text. Use a private local directory. Do not copy a live database as a
backup; stop the server cleanly first. Dwindy supplies no backup scheduler, encryption system,
accounts or cloud synchronization. API content remains no-store and access logging disabled.

The existing gitignore already excludes data/, common database extensions, journals, WAL
and SHM files. Local configuration and real model weights remain untracked. No database or
personal path belongs in the repository.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$browser = Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe tests\browser_checks.py --browser $browser
.\.venv\Scripts\python.exe tests\smoke_persistence.py --config eval-results/nonthinking.config.local.toml --browser $browser
```

The last command is explicit synthetic real-model validation using separate server processes
and an isolated temporary database. It tests stream acknowledgement, restart/manual browser
resume, recall, deletion across restart, ephemeral operation, model/database shutdown and
Windows rename-after-close. It prints database size and optional psutil RSS observations;
it does not rerun or modify the frozen M1 evaluation. Model-free socket tests separately
control cancellation during native work, storage commit and shutdown.

### M5 validation observations

On the existing Windows/Python 3.13 environment, the Python suite passes 117 tests: all
89 M4 tests (one intentional additive health-field assertion update) plus 28 M5 tests.
Chrome 154.0.8037.59 and Edge 154.0.4258.37 each pass 37 browser-native tests, including
the original 33, and existing real-HTTP same-origin/cross-origin, keyboard, style isolation,
mobile viewport, zoom and accessibility-tree checks. No full screen-reader audit or
Firefox/Safari/physical-mobile validation is claimed.

The separate Qwen3-1.7B Q4_K_M smoke used the existing non-thinking configuration unchanged.
It streamed `OK.`, restarted into a different server process, manually resumed in Chrome,
and returned `CEDAR`. Deletion survived restart. Ephemeral mode returned `HELLO.` and its
ID did not survive restart. Each server asserted model/database closure; database rename
after shutdown and temporary-directory cleanup succeeded on Windows.

One tiny saved turn occupied 20,480 bytes. An isolated store observation measured 14.1 ms
initialization, 7.9 ms for one commit, and 1,167,360 bytes additional process RSS. This
includes initialization effects and is not a hard bound or steady-state benchmark.
Separate model-process observations were 1,586,065,408 bytes RSS after the persistent turn
and 2,208,268,288 bytes after an ephemeral turn. They use different prompts/processes and
Windows working-set conditions: the difference is **not** a persistence-overhead estimate,
and neither is a sampled peak. Windows virtual-environment launchers were excluded by
measuring the largest interpreter process in the child tree. Results apply to this machine.

The existing Starlette TestClient deprecation warning and intermittent Windows Proactor
WinError 10054 on browser connection reset remain; tested cleanup and recovery pass.
Frozen M1 dataset and both historical baseline hashes were verified unchanged.
