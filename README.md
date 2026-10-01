# Dwindy

A small, local-first, CPU-first conversational runtime. Milestone 1 established ephemeral
terminal chat with a user-supplied GGUF and a 30-case baseline evaluation. Milestone 2
extracted that conversation behavior into a reusable, in-process `DwindyCore`.
**Milestone 3** exposes Core through an optional, small local HTTP API.
The [project proposal](docs/PROJECT_PROPOSAL.md) is the specification;
[architecture](docs/ARCHITECTURE.md) describes the implemented boundaries.

There is no browser client, persistent chat, retrieval, tool execution, or outbound web access
in this milestone. Dwindy never selects or downloads a model. Model licenses are separate
from the Apache-2.0 source license.

## Windows setup

Python 3.11+ is required. Run these PowerShell commands from the repository root.
The existing development environment was tested on Windows x86-64 / Python 3.13.0;
Python 3.11 and other platforms have not yet been validated. On a new checkout, create
the virtual environment with an installed Python 3.11+ interpreter, for example:

```powershell
py -3.13 -m venv .venv
```

Skip that command if `.venv` already contains the interpreter you want. Activation is
unnecessary; use its interpreter explicitly:

```powershell
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e .
```

This is a **setup-time dependency download**, not a runtime operation. The command uses
the runtime project's published CPU wheel index and fails instead of silently attempting
a native source build if a matching runtime wheel is unavailable. See the
[official installation documentation](https://llama-cpp-python.readthedocs.io/en/latest/)
for compiler-based installation alternatives. Dwindy does not install anything at startup.
Air-gapped setup requires separately prepared dependency wheels and model files.

## Supply and run your own model

Obtain a compatible text instruction/chat GGUF separately, review its license, and keep it
outside version control. M1 requires an embedded `tokenizer.chat_template` supported by
the installed runtime's Jinja formatter. Missing or unsupported templates produce errors;
there is no model-family fallback, tokenizer download, or remote model lookup.
Not every GGUF is a compatible text chat model.

For a direct run, replace this example path with your actual local file:

```powershell
.\.venv\Scripts\python.exe -m dwindy --model 'D:\Models\your-model.gguf'
```

For configuration:

```powershell
Copy-Item config.example.toml config.local.toml
notepad config.local.toml
.\.venv\Scripts\python.exe -m dwindy --config config.local.toml
```

Set `model_path` to your actual file. TOML literal strings accept Windows backslashes,
for example `model_path = 'D:\Models\your-model.gguf'`. Forward slashes also work.
Paths in TOML resolve relative to that file; `--model` overrides only the model path and
resolves relative to the working directory. No configuration is discovered automatically.
Use a physical local filesystem, not network-mapped or cloud-backed storage, for offline use.
URLs and UNC model paths are rejected.

Configuration keys are `model_path`, `context_size`, `max_tokens`, `temperature`, `seed`,
`threads`, and `system_prompt`. Unknown keys fail. Defaults are 4096 context tokens,
256 output tokens, temperature 0.7, seed 42, runtime-chosen thread count, and no system
message. These are starting settings, not benchmark-derived recommendations. Some templates
reject system messages; leave `system_prompt` empty unless your model supports them.

An optional `[chat_template_kwargs]` table passes model-template variables to the runtime
formatter. Omitted or empty means the embedded template's defaults are preserved. For a
template that implements `enable_thinking`, append this **after all top-level settings**:

```toml
[chat_template_kwargs]
enable_thinking = false
```

Values must be strings, booleans, integers, or finite floats. Lists, nested tables, dates,
and non-finite numbers are rejected. Keys must be identifiers without a leading underscore.
Formatter-owned arguments such as messages, special tokens, generation-prefix controls,
tools/functions, and helpers are reserved. The adapter alone forwards these variables;
counting and generation use the same settings. Unrecognized variables may be ignored by
a template, so this is not a universal reasoning switch. No model-name detection, prompt
rewriting, or generated-text filtering is performed. Inspect raw evaluation responses to
verify the effect for your particular GGUF. Effective kwargs are recorded in evaluation settings.

Type `/reset` to discard history and `/exit` to quit. EOF or Ctrl+C at the input prompt
also exits. Ctrl+C during generation discards the incomplete turn and returns to the prompt.
Responses stream to the terminal. The oldest complete turns are removed when necessary
to reserve output space; an oversized current message is rejected. Output limits are shown.
History exists only in memory and is never written by the terminal client. Reset is logical
history removal, not a guarantee of secure erasure from process memory or terminal scrollback.

## Calling Core from Python

Core borrows a backend and owns one in-memory conversation. The application is responsible
for constructing and closing the backend. Core does not import the runtime adapter.

```python
from contextlib import closing
from dwindy.backend import TextDelta
from dwindy.config import load_config
from dwindy.core import DwindyCore
from dwindy.llama_backend import LlamaBackend

config = load_config("config.local.toml")
backend = LlamaBackend(config)
try:
    core = DwindyCore(backend, options=config.options(), system_prompt=config.system_prompt)
    with closing(core.chat("Hello")) as stream:
        for event in stream:
            if isinstance(event, TextDelta):
                print(event.text, end="", flush=True)
    # Subsequent core.chat(...) calls retain completed turns.
    core.reset()  # Discard history without unloading the model.
finally:
    backend.close()
```

`chat()` returns a synchronous closeable iterator: `TurnStarted(dropped_turns)`, text deltas,
then existing backend `Completion` metadata. Completion is exposed only after successful
backend exhaustion, cleanup, and history commit. Core preserves nonempty length-limited
responses in history, matching M1. Failed, empty, incomplete, or cancelled turns do not
commit either the proposed response or proposed history trimming.

Streams are lazy: merely creating one does not start generation or reserve the conversation.
Once iteration begins, exhaust or close it before calling `chat()` again or `reset()`.
Closing before completion discards the pending turn; closing after completion retains it.
Overlapping use raises `RuntimeError`. This is a sequential-use guard, not thread safety;
callers must also serialize access when multiple Core objects borrow the same backend.
Core itself has no session registry, concurrency scheduler, or persistence. The optional
HTTP adapter owns its bounded conversation registry and serializes shared backend access.

Core rejects empty/non-string input with `ValueError`; it otherwise preserves supplied
text. The terminal retains its existing whitespace handling, blank-line skipping, slash
commands, Ctrl+C behavior, and rendering. Slash commands have no special meaning to Core.

## Local HTTP API

Install the optional dependencies, then launch one process with the same model configuration
used by terminal chat. No model or sampling settings are accepted over HTTP.

```powershell
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api]'
.\.venv\Scripts\python.exe -m dwindy.server --config config.local.toml
```

The installed `dwindy-api` entry point is equivalent. Defaults bind **127.0.0.1:8000**.
Optional server settings are separate from model configuration:

```powershell
Copy-Item api.example.toml api.local.toml
.\.venv\Scripts\python.exe -m dwindy.server --config config.local.toml --api-config api.local.toml
```

No file is auto-discovered. Do not use multiple workers, reload, or an alternative launcher
that overrides these binding/lifecycle settings. Ctrl+C requests shutdown; outstanding native
work must finish and its stream must close before the loaded model is released.

### Endpoints and wire contract

| Endpoint | Result |
|---|---|
| `GET /v1/health` | `200 {"status":"ready","busy":false}`; busy describes the global inference lease. Unavailable returns 503. No inference is run. |
| `POST /v1/chat` | One conversational turn; JSON by default, SSE when `stream` is true. |
| `DELETE /v1/conversations/{id}` | 204 with an empty body; unknown/expired IDs return 404, active conversations return 409. |

`GET /openapi.json` provides the local machine-readable contract under the same security
controls. Interactive documentation/CDN assets are disabled.

POST requires `Content-Type: application/json`. Only these fields are accepted:

```json
{"message":"Hello","conversation_id":null,"stream":false}
```

`message` is a required nonblank string, preserved verbatim. `conversation_id` is an optional
32-character opaque ID previously returned by the server; omission or null creates a new
conversation. `stream` is an optional strict boolean, default false. Unknown fields, coercion,
client-selected IDs, and per-request model settings are rejected. Maximum raw body size is
65,536 bytes by default, including chunked requests; the model's context limit is separate.

A successful non-streaming response has this shape (counts are illustrative):

```json
{"conversation_id":"<server-generated-id>","text":"Hello!","finish_reason":"stop","dropped_turns":0,"usage":{"prompt_tokens":12,"text_tokens":2}}
```

`finish_reason` comes from the backend (currently `stop` or `length`). `text_tokens` counts
retokenized raw visible response text, **not** sampled tokens or final-answer-only tokens.
No reasoning tags or other generated content are removed. `dropped_turns` counts oldest
complete conversation turns trimmed for this request. A nonempty length-limited answer is
committed, preserving M1/M2 semantics.

For `stream:true`, the same POST returns `text/event-stream` with JSON data frames:

```text
event: started
data: {"conversation_id":"<server-generated-id>","dropped_turns":0}

event: delta
data: {"text":"Hello!"}

event: completed
data: {"finish_reason":"stop","usage":{"prompt_tokens":12,"text_tokens":2}}

```

There are zero or more `delta` frames. JSON escaping preserves newlines and Unicode; HTTP
chunks need not coincide with SSE frames. Completion is sent after Core commits and closes.
A failure after SSE headers produces a terminal `error` event instead of `completed`:

```text
event: error
data: {"error":{"code":"inference_failed","message":"Inference failed; the turn was not completed."}}

```

Preparation failures, including context overflow, return ordinary JSON with an HTTP error
status **before** SSE headers. A stream ending without `completed` or `error` has uncertain
delivery. Use streaming `fetch` or an HTTP client; browser `EventSource` cannot send this POST
body/bearer header. There are no event IDs, replay, or automatic reconnect semantics.

All application errors use `{"error":{"code":"...","message":"..."}}`; messages do not
echo request content, tokens, or native exceptions. Codes/statuses:

| Status | Codes / meaning |
|---|---|
| 400 | `invalid_json`, `invalid_host`, `invalid_headers`, `incomplete_request` |
| 401 | `unauthorized` (also `WWW-Authenticate: Bearer`) |
| 403 | `origin_denied`, `preflight_denied`, `local_only`, `tls_required` |
| 404 | `conversation_not_found`; unknown routes use `http_error` |
| 405 | `http_error` for unsupported methods |
| 409 | `conversation_busy` |
| 413 / 415 | `request_too_large` / `unsupported_media_type` |
| 422 | `invalid_request` / `context_limit` |
| 500 | `inference_failed` / `internal_error` |
| 503 | `backend_busy`, `conversation_capacity`, `unavailable` |

Busy/capacity/unavailable responses include `Retry-After: 1`; this is a polling hint, not a
completion estimate or queued reservation. Protocol-level failures rejected by the HTTP
server itself need not use the application error envelope.

### Ephemeral conversations and cancellation

The first successful request returns a random ID; send it on later requests to retain context.
SSE exposes the ID in `started`, so even a failed streamed turn may leave an empty conversation.
A new JSON request failing before exposing its ID releases its unused slot. Existing conversation
history survives failed/cancelled turns. There is no list/history endpoint. Delete an idle
conversation and omit the ID on the next chat to start fresh.

Defaults allow 16 conversations, each with Core's existing bounded recent-turn history. Idle
conversations expire after 1,800 seconds since request cleanup. Expiry is lazy at the next chat
or delete request; it never expires an active turn or evicts a live conversation for capacity.
Restart discards all IDs and history. Deletion/expiry are logical removal, not secure memory erasure.

Only one inference request is admitted globally. A simultaneous request for the same conversation
receives 409; another conversation receives 503 immediately, without queuing model work. Health
and idle-conversation deletion remain available while inference runs.

Client disconnect requests cooperative cancellation. Dwindy waits for the pending native call,
closes Core on the same worker, then releases the backend and conversation lease. No thread is
forcibly interrupted; a stuck native call can keep the service busy and delay shutdown indefinitely.
If Core committed just before disconnect, the answer remains in history even when the client did
not receive it. **Do not automatically retry an uncertain request**: it may duplicate a turn.
Delete the conversation and start fresh if an unambiguous reset is necessary. No exactly-once
delivery, request replay, or cancellation endpoint is provided.

### Security and API configuration

Loopback is the default; no outbound requests, update checks, or downloads occur at runtime.
Requests must use an exact allowed Host. Untrusted Origins are rejected, including `null`;
same-origin requests are permitted, and additional browser origins must be explicitly listed.
For example, local development can set `allowed_origins = ["http://localhost:5173"]`. There is
no wildcard CORS and no cookie authentication. Preflight allows GET/POST/DELETE and the
Content-Type/Authorization headers only. CORS does not authenticate non-browser clients.

Loopback bearer authentication is optional. Enable it without saving a secret to TOML:

```powershell
$env:DWINDY_API_TOKEN = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
```

The token is read at startup and must be at least 32 non-whitespace ASCII characters. Send
`Authorization: Bearer <token>` on every application/schema request. Approved browser
preflights do not require the token. Without authentication, other local processes share trust;
conversation IDs are opaque addresses, not user isolation. Do not embed a shared secret in a
publicly shipped widget. M4 client integration is not implemented here.

| API TOML field | Default / rule |
|---|---|
| `host`, `port` | `127.0.0.1`, `8000`; host must be a literal IP |
| `allow_non_loopback` | `false` |
| `allowed_hosts` | `["127.0.0.1", "localhost", "::1"]`; exact names/IPs, without ports |
| `allowed_origins` | `[]`; exact scheme/host/port origins, without trailing slash |
| `token_env` | `"DWINDY_API_TOKEN"`; names the environment variable, never the secret |
| `max_conversations` | `16` |
| `conversation_idle_seconds` | `1800` |
| `max_request_bytes` | `65536` |
| `ssl_certfile`, `ssl_keyfile` | unset; must be supplied together; paths relative to API TOML |

Non-loopback startup requires **all** of explicit exposure opt-in, a valid bearer token, and
a loadable TLS certificate/key. Configure the actual host in `allowed_hosts` too. TLS terminates
in Uvicorn; forwarded/proxy headers are not trusted. Do not commit certificates' private keys,
tokens, local configuration, or user data. Responses disable caching; access logs are disabled.
The application additionally rejects remote peers under loopback configuration and plaintext
HTTP under non-loopback configuration. These safeguards do **not** turn Dwindy into a hardened
public internet service: there are no user accounts, rate limits, reverse-proxy deployment
contracts, or protection against a malicious authorized local client exhausting resources.

An unrelated PowerShell client can integrate using ordinary HTTP:

```powershell
$headers = @{}
if ($env:DWINDY_API_TOKEN) { $headers.Authorization = "Bearer $env:DWINDY_API_TOKEN" }
$reply = Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/chat -Method Post -Headers $headers -ContentType application/json -Body (@{ message = 'Hello' } | ConvertTo-Json)
$reply.text
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/chat -Method Post -Headers $headers -ContentType application/json -Body (@{ message = 'Continue'; conversation_id = $reply.conversation_id } | ConvertTo-Json)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/conversations/$($reply.conversation_id)" -Method Delete -Headers $headers
```

## Tests and evaluation

The frozen M1 evaluation still calls the backend directly: it is a naked-model/runtime
baseline, not a Core benchmark. M2 adds model-free Core lifecycle tests without changing
the dataset, historical results, prompts, sampling defaults, or template behavior.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Tests use fake runtimes; no model or external network is required. API socket tests bind
ephemeral loopback ports. Install their optional dependencies to include them (otherwise
the HTTP test modules skip; the existing 50 M2 tests remain available):

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[api,api-test]'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

An explicit real-model HTTP smoke test covers multi-turn retention, SSE, disconnect rollback
and recovery, deletion, fresh conversation state, and shutdown during generation/model cleanup:

```powershell
.\.venv\Scripts\python.exe tests\smoke_api.py --config config.local.toml
```

It runs synthetic prompts on an ephemeral loopback port and prints observations; it does not
write conversations, change model settings, or rerun the 30-case baseline. Its recall assertion
tests the chosen model as well as integration and may fail with another model's output.
Use the same non-thinking TOML used for validation when comparing the existing Qwen setup.

To test the source without
installing runtime dependencies, set `$env:PYTHONPATH = (Join-Path (Get-Location) 'src')`
before running unittest.

Optional memory measurement dependency and baseline run:

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[eval]'
New-Item -ItemType Directory -Force eval-results | Out-Null
.\.venv\Scripts\python.exe tests\eval\run.py --config config.local.toml --output eval-results\baseline-01.jsonl
```

Use a new output name for every run. The runner requires an explicit output path and refuses
to overwrite existing files. It writes evaluation answers and measurement metadata, never
terminal history. `eval-results/` is ignored by Git.
See [evaluation instructions](tests/eval/README.md) for scoring and metric limitations.

## Dependencies

| Dependency | Role |
|---|---|
| `llama-cpp-python==0.3.35` | In-process CPU inference; pinned because template/runtime APIs matter. |
| `setuptools>=68` | Build backend, used during installation only. |
| `psutil>=5.9,<8` (optional `eval` extra) | Sample process RSS and report machine RAM. |
| `fastapi==0.142.2` (optional `api` extra) | HTTP routing, lifespan integration, and local OpenAPI schema. |
| `pydantic==2.13.5` (optional `api` extra) | Strict request validation and response/schema models; directly imported. |
| `starlette==1.7.0` (optional `api` extra) | Direct ASGI response, disconnect, middleware, and test interfaces. |
| `uvicorn==0.54.0` (optional `api` extra) | Single-process HTTP/TLS server; plain package, not its standard extras. |
| `httpx==0.28.1` (optional `api-test` extra) | Test/smoke HTTP client only; not a server runtime requirement. |
| NumPy (runtime transitive) | Runtime arrays and native inference integration. |
| Jinja2 and MarkupSafe (runtime transitive) | Runtime chat-template rendering and its string support. |
| typing-extensions (runtime transitive) | Runtime typing compatibility. |
| diskcache (runtime transitive) | Upstream runtime dependency; Dwindy does not enable a disk cache. |

Configuration, terminal interaction, tests, JSONL, hashing, and timing use Python's standard
library except for the optional HTTP testing stack above. The API combination was installed,
tested on Windows/Python 3.13, and passed `pip check`. Its transitive dependencies include
AnyIO, Pydantic Core, annotated-types, typing-inspection, annotated-doc, Click, h11, and
OpenTelemetry API. Dwindy configures no telemetry SDK/exporter or outbound telemetry.
HTTPX testing also installs httpcore, certifi, and idna. Starlette currently warns that its
HTTPX TestClient integration is deprecated; the pinned combination remains tested and working.
Installed during initial validation: llama-cpp-python 0.3.35, NumPy 2.5.3,
Jinja2 3.1.6, MarkupSafe 3.0.3, typing-extensions 4.16.0, diskcache 5.6.3, psutil 7.2.2.
These are an observed environment, not a cross-platform lockfile.

The first real-model baseline used Qwen3-1.7B Q4_K_M on an i3-1215U Windows 11 machine
with 7.7 GB usable RAM. All 30 cases executed, but default thinking consumed output budgets.
See the evaluation README for raw-stream metric interpretation and the template-kwargs
correction. These measurements apply to that machine and configuration, not every 8 GB PC.
