# Dwindy architecture through M8

Status: M1 runtime and template-kwargs correction, M2 Core, M3 local HTTP API, M4 chat interfaces, M5 opt-in SQLite persistence, M6 explicit local retrieval, M7 project awareness, and M8 context selection.
The project proposal remains the specification. This document records implemented decisions.

## Execution and ownership

One Python process contains either the terminal application or the optional HTTP application
and a CPU-only llama.cpp runtime accessed through llama-cpp-python. The terminal opens no
listener; the API explicitly opens a loopback listener by default. No separate model service,
database server or outbound-network client is created. Optional API persistence opens a local SQLite file. Dependencies and model files are
installed/supplied separately from execution.

`core.py` owns an in-memory list of completed user/assistant turns for each `DwindyCore`.
It selects recent complete turns within context, reserving `max_tokens` for generation.
It keeps a configured system message, rejects a current request that cannot fit, and commits
history only after successful backend exhaustion, stream cleanup, and a nonempty completed
answer. Nonempty output-limit responses are retained, preserving M1 behavior. Failed or
cancelled requests do not alter retained history, even when candidate preparation trimmed
old turns. Core itself performs no persistence; the optional API store archives completed turns.

`__main__.py` contains application wiring and terminal rendering. `main()` loads configuration,
constructs the model backend, gives Core its generation options and system prompt, and closes
the backend on exit. The terminal receives Core; it handles input, slash commands, rendering,
and interruption. `/reset` calls Core's reset operation. No model messages, token budgeting,
history storage, or response-commit decisions remain in terminal rendering.

`config.py` reads explicitly selected TOML using `tomllib`, validates settings, and resolves
local model paths. CLI model paths override the file setting. No automatic config search or
environment-based model settings are implemented. CPU execution is fixed, not a toggle.
`server.py` separately validates API-only TOML and an optional bearer token environment
variable. It launches one Uvicorn worker with reload, proxy-header trust, and access logs disabled.

## Core boundary and lifecycle

`DwindyCore(backend, *, options, system_prompt="")` represents one ephemeral conversation.
Its public operations are synchronous `chat(user_text, *, evidence=None)`, `reset()`, `snapshot()` and `restore(messages)`. It borrows a
`ModelBackend`; neither reset nor stream cleanup closes the model itself. It depends on
`backend.py`, not configuration files, GGUF, llama.cpp, or template variables.

`chat()` returns a closeable generator with one Core-owned `TurnStarted(dropped_turns)`
event, existing `TextDelta` events, and an existing `Completion` event. The initial event
lets interfaces preserve M1's trimming notice before response output. Core buffers the
answer for history while forwarding text unchanged; it delays Completion until commit.
Missing completion or empty output retains the M1 backend error behavior.

The stream is lazy. A started stream holds a per-instance active guard until exhausted or
closed, including while suspended at its final Completion event. A second chat or reset is
rejected during that interval. Iteration rechecks the guard so previously created streams
cannot interleave. Closing an unstarted stream changes nothing. Closing a started stream
before completion closes its backend iterator and discards candidate state. Backend errors,
interruptions, and cleanup failures release the guard. Callers must explicitly exhaust or
close streams; abandoned references are not a supported cleanup strategy.

The guard provides sequential-use validation, not thread safety or backend-wide locking.
Separate Core instances have separate history; applications sharing a model backend must
serialize their calls. Core has no registry, session addressing, or concurrency scheduling;
the HTTP adapter supplies a bounded registry and one global inference lease.
Core rejects blank/non-string input without changing state and does not normalize valid text
or interpret slash commands. The terminal keeps its M1 input normalization and commands.

M2 changes ownership, not model policy: prompts, generation settings, budget arithmetic,
whole-turn trimming order, template kwargs, and raw text output are unchanged. Model quality
limitations from the M1 baseline are not addressed by this extraction.

## Backend contract

`backend.py` defines plain immutable messages, generation options, text deltas, completion
metadata, a backend error, and a synchronous Protocol:

- `generate(messages, options)` yields text deltas followed by one completion.
- `count_tokens(messages)` counts rendered model input, including chat formatting.
- `context_size()` returns the actual configured runtime context limit.
- `close()` releases the model; repeated close is safe.

Completion metadata includes finish reason, prompt-token count, and **retokenized visible
text** token count. The latter is not the number of tokens actually sampled by the runtime.
Native runtime objects and dictionaries do not cross this boundary.
M3 adds `ContextLimitError(BackendError)` to the existing context-overflow paths in Core
and the adapter. This enables reliable HTTP 422 mapping without matching exception text.
Existing callers catching BackendError retain their behavior; no model-facing logic changes.

`llama_backend.py` alone imports llama-cpp-python. It loads one explicit local GGUF,
forces `n_gpu_layers=0`, reads the embedded chat template, and uses the runtime's Jinja
formatter. There is no hardcoded model-family format or silent fallback. Models requiring
unsupported templates, multimodal handling, or external template assets are outside this
initial adapter's supported path and fail with an explanation.

The same formatting/tokenization path is used for budgeting and generation. Generation
renders again and independently rechecks the budget, then supplies those exact token IDs
to completion. Template-dependent changes between calls cannot bypass the final check.
The adapter preserves formatter stop conditions, streams text, resets logical inference
state between requests, closes streams on cancellation, and translates runtime exceptions.
Reset does not promise secure memory erasure. There is no enabled disk/prompt cache.

The empty default system prompt avoids assuming every template supports a system role.
4096 context tokens and 256 output tokens are configurable starting values, not established
hardware recommendations. The runtime dependency is pinned to 0.3.35 to bound coupling
to its formatting API. A backend change must preserve these semantics; no plugin registry
or generic backend manager exists.

The optional `chat_template_kwargs` TOML table defaults to an empty mapping. Configuration
accepts only string, boolean, integer, and finite-float values under non-private identifier
keys, and rejects formatter-owned arguments. The adapter validates and copies this mapping
at construction, then forwards it through the common `_prepare` path for counting and
generation. It does not send the mapping to the model constructor or completion API.
Evaluation configuration serialization includes the mapping. Templates define whether a
variable has an effect; unfamiliar variables may be ignored. There is no model detection,
universal reasoning mode, message rewriting, or generated-output stripping.

## HTTP ownership, state, and cancellation

`api.py` contains the FastAPI application, strict HTTP schemas/security checks, bounded
conversation registry, and response adapter. Its only runtime construction import is inside
application startup; request handling uses DwindyCore and the existing backend contract.
`create_app(model_config, api_config, backend=...)` permits model-free tests to supply a backend;
the application's lifespan owns and closes either the supplied or constructed backend.
No factory framework, backend registry, or Core dependency on HTTP is introduced.

One event loop owns admission and the in-memory ID-to-Core mapping. One dedicated worker
thread loads the model and performs all synchronous counting/generation/stream cleanup/model
closure. Admission happens without an intervening await: same-conversation overlap gets 409,
other inference gets 503, and rejected operations never enter the worker. ThreadPoolExecutor
is only a mechanism for this single worker, not an inference queue. Health and idle deletion
do not call the model. No native call is made on the event loop.

Opaque 192-bit random IDs identify one ephemeral Core each. Defaults cap the registry at
16 conversations, with lazy 30-minute idle expiry. Active entries cannot expire or be deleted.
There is no live eviction, listing, user ownership, or multi-process sharing. Optional persistence
archives successful turns outside Core; expiry removes only cached state when enabled.
New requests failing before exposing their IDs release their slots. SSE exposes the ID in
`started`, so later failure leaves the addressed conversation available until delete/expiry.
Deleted/unknown IDs return 404 and are never silently recreated. Ephemeral expired IDs return
404; persistent disk-only IDs restore their retained context lazily. Delete plus a chat without
an ID supplies reset semantics. The memory registry disappears on shutdown; enabled storage remains on disk.

The response adapter explicitly owns the closeable Core stream rather than handing a sync
generator to a framework streaming wrapper. It advances to TurnStarted before sending success
headers, preserving normal HTTP errors for preparation failures. It forwards raw deltas and
committed completion metadata into either accumulated JSON or four SSE event types:
`started`, `delta`, `completed`, `error`. Wire schemas and all errors are documented in README
and the local OpenAPI endpoint; there are no fields for unimplemented features.

An ASGI disconnect watcher requests cancellation between synchronous advances. A pending
native next() is shielded from task cancellation; cleanup waits for it to return, closes Core
on the worker, and only then releases conversation/global leases. Cleanup itself is shielded
against repeated task cancellation. Native code is never forcibly interrupted. Close failure
marks the API unavailable instead of permitting unverified backend reuse.

Shutdown stops admission, cancels/drains active response tasks, then closes the model on the
same worker and joins the worker. The launcher gives requests a one-second graceful window
before requesting cancellation; this is not a deadline for killing native work. A stuck native
call can prevent safe shutdown. Connected requests cancelled during shutdown receive an
unavailable error after cleanup where delivery is still possible. Startup cancellation waits for model construction
so the model cannot be abandoned while loading.

Core commit precedes HTTP completion delivery. With persistence enabled, SQLite COMMIT also
precedes completion delivery; the adapter owns rollback/quarantine and retains the lease
through native cleanup and durable settlement. A disconnect racing with commit can leave a
completed turn in history without the client knowing it succeeded. There is no exactly-once
delivery, replay, automatic retry, resumable SSE, or idempotency store. Nonempty output-limit
responses still commit. Failed/cancelled turns roll back under the existing Core semantics.

## HTTP security boundary

The supported launcher binds literal 127.0.0.1 by default and never uses reload or multiple
workers. Separate API configuration requires explicit opt-in, bearer authentication, and a
loadable TLS certificate/key for non-loopback binding. TLS terminates directly in Uvicorn;
proxy headers are disabled. Application checks also reject non-loopback peers in local mode
and plaintext requests in non-loopback mode. These controls do not make this a public internet
service; accounts, rate limiting, hostile-client availability guarantees, and proxy deployments
are outside M3.

Host headers must match exact configured names/IPs. Browser Origin headers must match the
request origin or an explicitly allowed origin; all others, including null, are rejected before
application work. CORS is not authentication. Only approved methods/headers receive preflight
permission, and cookies/credentialed CORS are not enabled. Optional loopback authentication
uses one environment-supplied bearer token and constant-time comparison; it is mandatory for
non-loopback exposure. The token is not written to configuration, logs, or responses. Local
clients share the same trust boundary; opaque IDs do not provide per-user access control.

Bodies are bounded while reading, including chunked requests, before JSON parsing. Schemas
reject unknown fields and coercion, preserving valid message text. Application errors do not
echo submitted values or native exception details. Responses disable caching and the launcher
disables access logs. Interactive docs/CDN assets are disabled; /openapi.json uses the same
Host/Origin/auth rules. Model loading and API operation make no outbound requests.

## Browser clients through M4

`web/dwindy-chat.js` implements one autonomous custom element with open Shadow DOM and
an external component stylesheet. The standalone shell selects inline presentation; embedding
uses the same component with a launcher/native modal dialog. No framework, bundler, browser
package dependency, CDN or outbound asset fetch is introduced. Default assets resolve relative
to the module and use the existing canonical `assets/` tree. Idle and working indicate idle/
completed and active request processing respectively; no other mascot state is activated.

`web/api-client.js` is an internal shared transport: fetch, streamed UTF-8/SSE parsing,
conversation ID, bearer credential, abort and DELETE lifecycle. It uses only public M3 endpoints.
Core, model configuration, prompts, inference settings and backend behavior are unchanged.
The browser never sends its displayed transcript as model history. User/model output is inserted
as text, not HTML/Markdown. Display retention is bounded separately from server context.

Credentials and IDs exist only in component/page memory. Each element has independent state.
Failed requests preserve drafts; uncertain cancellation/EOF requires an explicit new conversation.
Explicit reset/delete removes the server conversation before clearing the display; failures retain the address.
Closing a dialog hides it, while element removal aborts outstanding requests. No unload deletion,
automatic chat retry, browser storage, event bus, frontend accounts or model logic exists.

`web_ui.py` provides optional same-server static delivery selected by `--chat-root`. A fixed
mapping serves the six runtime frontend files and four required PNGs, plus the /chat/ redirect.
Resolved files must remain in the explicitly selected source bundle. No directory is mounted.
Only exact static GET/HEAD paths bypass bearer checks for browser bootstrap; Host/Origin and
exposure checks still apply, and all M3 API/schema authentication remains intact. The frontend
contains no injected backend token. Static paths do not expand the application OpenAPI surface.

Copying the same component/assets into another host's static directory is equally supported.
No static server or Dwindy Python integration is needed in the host application; only its HTTP
API destination and M3 Origin permissions. Source assets are not yet bundled in the Python wheel.
The customization contract consists of the documented attributes, memory-only bearer setter,
reset/new/resume methods, and four CSS color variables. Shadow DOM provides style isolation, not security.

Native keyboard controls and dialog behavior, status/error announcements, completion-only
answer announcements, bounded autoscroll, reduced motion and narrow-viewport styles are
implemented. `docs/CHAT_INTERFACES.md` records the exact behavior, security requirements,
test commands, browser coverage and remaining accessibility/device validation limitations.

## Evaluation and validation

`tests/eval/core_v0.jsonl` holds 30 synthetic cases across six categories. The explicit
runner evaluates each independently, without importing terminal history. It writes answers,
case rubrics, execution failures, settings, hashes, machine information, and measurements
only to a user-selected new output file. Human quality fields begin unscored.

The frozen M1 runner continues calling the backend directly, bypassing Core. M2 tests cover
Core state ownership, trimming and rollback, stream cleanup, overlap rejection, backend
ownership, and terminal behavior. Historical evaluation artifacts and rubrics are unchanged.
The existing M2 behavior remains covered without model-policy changes. M3 tests cover HTTP contracts, strict validation,
body bounds, state expiry/capacity, security and binding policy, and real loopback socket
disconnects/shutdown with a controlled fake backend. Blocking native-next and cleanup phases
verify backend exclusion until cleanup finishes, including rollback of a cancelled turn.
The optional HTTP dependencies are pinned to the combination tested on Windows/Python 3.13.
No real model is required for automated tests.

`tests/smoke_api.py` is an explicit synthetic real-model smoke, separate from M1 evaluation.
The existing Qwen3-1.7B Q4_K_M non-thinking configuration (4096 context, 256 output,
temperature 0.7, seed 42) retained CEDAR across HTTP requests and after disconnect recovery;
JSON, SSE, deletion, fresh conversation state, and shutdown during generation/model cleanup
passed. Observed disconnect recovery was approximately 0.15–0.20 seconds on the development
machine; it is an observation, not a latency guarantee or a new baseline measurement.

Time to first nonempty text is measured rather than claiming raw first-token latency.
Throughput counts retokenized visible text over total request time, including prefill.
Optional psutil samples process RSS every 50 ms; unavailable memory measurements remain
null. Model hashing precedes loading and warms the filesystem cache, so recorded load time
is not a cold-start result. Full metric definitions are in the evaluation README.

Model-free tests cover config validation, history and budget behavior, interrupted/failing
streams, adapter contract translation, and evaluation structure. Initial testing used
Windows x86-64 and Python 3.13.0. A subsequent Qwen3-1.7B Q4_K_M baseline executed all
30 cases on an i3-1215U / 7.7 GB usable RAM / Windows 11 machine, exposing default thinking
and output-budget exhaustion. The template-kwargs correction addresses template selection
without filtering output. Python 3.11 and other platforms remain unvalidated; measurements
apply to the tested machine/configuration. The evaluation README explains the original
baseline's raw-stream timing semantics.

## Local data boundaries

No terminal history, weights, personal paths, local configuration, or benchmark results belong
in version control. The example configuration contains placeholders. Evaluation results
exclude the absolute model path but still contain generated text and any explicitly supplied
system prompt; review before sharing. Model access uses a local path, never a download API.
Offline operation also requires users to avoid network-mapped/cloud-backed filesystem paths.
There is no OS sandbox or secure-memory-erasure claim.


## SQLite ownership through M5

`persistence.py` implements the concrete standard-library SQLite store on one dedicated
storage worker. Core's idle-only snapshot/restore operations are the sole state boundary;
no SQL or filesystem dependency enters Core. `api.py` owns storage startup/shutdown, lazy
restoration, admission, durable completion and deletion. `server.py` validates opt-in
`database_path` and `database_max_mib` separately from model configuration.

Schema version 1 stores conversations and complete turn pairs. `context_start_turn` separates
the archived transcript from the retained model-context suffix. Restoration never reintroduces
trimmed turns. A short transaction saves a pair and boundary together after generation, before
JSON success/SSE completed. Confirmed capacity/lock failures restore the pre-turn snapshot;
uncertain storage failures quarantine admission. Cancellation cleanup settles pending saves.

The existing browser component adds manual ID resume, a storage notice, non-destructive new
conversation and explicit destructive deletion when enabled; floating controls use a native
details disclosure. Ephemeral reset behavior remains available. No history/list UI or browser
storage exists. See [persistence](PERSISTENCE.md) for exact schema, transactions, quotas,
configuration, privacy and validation, and [chat interfaces](CHAT_INTERFACES.md) for UI lifecycle.

## Explicit local retrieval through M6

`ingest.py` reads an authoritative TOML manifest of explicitly named UTF-8 text/Markdown
files and synchronizes a separate, rebuildable FTS5 SQLite index in one transaction.
It performs no directory discovery. `retrieval.py` validates and queries that index;
it never constructs model input or accesses source files at query time. The M5 database
schema and store are unchanged. Both stores share the existing serialized storage worker;
the model worker remains separate. No additional runtime dependency is introduced.

`evidence.py` contains immutable passage/source records and data framing. Core accepts
at most twelve candidates through a narrow per-turn Evidence value, selects at most three,
and uses the backend's real rendered token counts for the incremental allowance and final
context limit. Only retrieval-enabled turns receive untrusted-document guidance. The absent
evidence path retains the existing message sequence and prompt behavior. Core imports no
SQLite, ingestion, API configuration or filesystem operations.

Evidence and its guidance are never committed to conversation history. Snapshot, archival
and restoration still contain only original questions and generated answers; an answer may
itself repeat a document fact. Source metadata appears in the current JSON response or SSE
started event, not in a persistent conversation evidence trail. `supplied` describes model
input, not verified answerability, grounding or correctness.

The API opens a configured index read-only at startup and closes it on the storage worker
after draining requests. Explicit POST /v1/retrieve performs no inference. Chat opts in with
retrieval:true. It holds the existing inference lease through retrieval, token preparation,
generation and cleanup; disconnects do not permit unsafe backend reuse. Explicit retrieval
failures do not silently fall back to model-only generation. Index synchronization is an
offline CLI operation: stop the server, sync, then restart. No live index management API exists.

See [retrieval](RETRIEVAL.md) for schema, limits, security, wire contract and the separate
[M6 validation report](M6_VALIDATION.md).

## Project awareness through M7

`project_policy.py` owns the filesystem boundary: hard exclusions, `.gitignore` and
configured deny patterns (through the optional pathspec matcher, used for matching only),
link/junction/reparse-point and hard-link rejection on every component, bounded directory
listing and signature-checked reads. `project.py` loads the explicit project TOML, captures
a bounded documentation-first selection plus individually listed source/configuration files,
generates the overview and metadata documents, and computes the snapshot identity. Neither
imports a model, Core or HTTP code; neither runs Git, a shell or project code.

Capture produces the same internal `Document` records as an M6 manifest. `ingest.py` now has
one authoritative atomic writer, `write_documents`, shared by manifest sync and project sync.
It accepts precomputed spans (declaration-aware source chunking) and a precommit callback,
which project sync uses to recheck every input before COMMIT. Project indexes use
`user_version` 2 plus a singleton `project_snapshot` table; neither kind of sync adopts the
other's index. `retrieval.py` validates both versions, attaches `project_id` and
`snapshot_id` to project passages, and keeps M6 ranking unchanged.

Core is unchanged apart from serializing source metadata without empty project fields.
`evidence.py` adds a short project-observation note to the untrusted-passage framing only
when a supplied passage comes from a project. The API reads the snapshot identity once when
it opens the index and adds it to health. Unset project fields are omitted from health and
retrieve responses, so M6 responses are unchanged. Sync remains an offline CLI operation.
See [project awareness](PROJECT_AWARENESS.md) and the [M7 validation report](M7_VALIDATION.md).

## Context selection through M8

`context_policy.py` decides per turn whether local evidence deserves model context. It is pure
apart from calling a caller-supplied `search` function: it has no model, configuration, HTTP or
filesystem dependency, and Core does not import it. Callers run `decide(message, mode, ...)` and
pass the resulting `Evidence` to the unchanged `DwindyCore.chat`. The API, the terminal (with
optional `--retrieval-index`) and direct Python use share this one policy. In the API, the
decision runs as one call on the existing serialized storage worker; if that worker is
occupied, the decision is made immediately as a busy retrieval rather than queued.

Core gained one narrow field: `Evidence.fallback`. `insufficient` keeps the M6 path
byte-for-byte. `plain` turns opportunistic evidence that cannot be used into ordinary chat with
identical model input. `unavailable` adds the transient constrained-fallback instruction with no
passages. Instructions and evidence still never enter history or persistence, and generation
remains the only model call per turn. M6 ranking is unchanged: `retrieval.py` only exposes the
query terms its search already used. The mode is resolved per request, then from
`retrieval_default`, then `auto` when an index is configured. See [context selection](CONTEXT_SELECTION.md)
and the [M8 validation report](M8_VALIDATION.md).
