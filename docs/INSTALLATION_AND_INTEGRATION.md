# Dwindy installation and integration

This is the practical guide to obtaining, configuring, using and integrating Dwindy
1.0.0 from its source repository. Begin with the common installation, then choose a
frontend and optional features. No knowledge of the project's milestone history is needed.

Commands use **Windows PowerShell**, run from the repository root unless stated otherwise.
Replace example model paths with an existing GGUF on your machine. Commands that launch a
server keep that terminal occupied; use a second terminal for HTTP requests.

## Contents

1. [What Dwindy provides](#1-what-dwindy-provides)
2. [Choose your setup](#2-choose-your-setup)
3. [Get Dwindy](#3-get-dwindy)
4. [Create the environment and install](#4-create-the-environment-and-install)
5. [Provide and configure a GGUF](#5-provide-and-configure-a-gguf)
6. [Run the standalone demo](#6-run-the-standalone-demo)
7. [Configuration and feature switches](#7-configuration-and-feature-switches)
8. [Local document retrieval](#8-local-document-retrieval)
9. [Project Awareness](#9-project-awareness)
10. [Wikipedia Reach](#10-wikipedia-reach)
11. [Conversation persistence](#11-conversation-persistence)
12. [Capabilities and application identity](#12-capabilities-and-application-identity)
13. [Embed the Web Component](#13-embed-the-web-component)
14. [Custom frontend and Python integration](#14-custom-frontend-and-python-integration)
15. [Customize the frontend](#15-customize-the-frontend)
16. [Operation, troubleshooting and validation](#16-operation-troubleshooting-and-validation)

## 1. What Dwindy provides

Dwindy is a small, modular, local-first chatbot runtime. A local GGUF supplies the
language-generation backend; **Dwindy is the assistant/product identity**. The backend
is interchangeable, subject to runtime and chat-template compatibility.

The information path is:

```text
selected sources → ingestion/indexing → discovery → admission → bounded evidence → local model
                                              actual supply → API/UI source and status metadata
```

Dwindy owns infrastructure: clock/calculator execution, source acquisition, local search,
admission, context budgeting, conversation lifecycle and deterministic receipts. The model
interprets supplied information and generates conversational language. Its wording is not
the authority for tool execution, retrieval success or system state.

Production retrieval is lexical SQLite FTS5. There is no semantic encoder, vector database,
autonomous browsing, project-code execution, host-action executor or second model generation.
Known retrieval and model limitations remain limitations, not promised capabilities.

Standalone browser chat and the embedded modal are **two frontends over the same HTTP
API/runtime**. Neither needs a frontend framework, build process, Node or npm. Another
frontend can use the API without either bundled presentation.

## 2. Choose your setup

All six recipes share sections 3–5: get the repository, create `.venv`, provide the GGUF
and create `config.local.toml`. Each installation command below includes the tested CPU
wheel source. Run `pip check` after installing or changing extras.

For each optional API configuration, copy the example once, then edit it:

```powershell
Copy-Item api.example.toml api.local.toml
notepad api.local.toml
```

Do not copy over an existing configuration you want to keep. The snippets below show the
minimum active optional settings; commented examples do not enable features.

### Recipe 1: minimal standalone chat

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\dwindy-api.exe --config config.local.toml --chat-root .
```

No `api.local.toml` is required. Open **http://127.0.0.1:8000/chat/**. Expect ordinary local
conversation, clock/calculator facts when applicable, and in-memory conversation history.
Reach, local documents and saved conversations are disabled.

### Recipe 2: standalone with Reach

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api,reach]'
.\.venv\Scripts\python.exe -m pip check
```

Set in `api.local.toml`:

```toml
reach_provider = "wikipedia"
reach_default = "auto"
```

```powershell
.\.venv\Scripts\dwindy-api.exe --config config.local.toml --api-config api.local.toml --chat-root .
```

Open `/chat/`. **Use Wikipedia** starts checked. Selected freshness/lookup requests can
send a minimized query online; ordinary conversation remains local. Use `reach_default =
"off"` instead if online requests should require client opt-in. Section 10 explains receipts.

### Recipe 3: standalone with local documents

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api]'
.\.venv\Scripts\python.exe -m pip check
```

Create the example files in section 8, then synchronize with the API stopped:

```powershell
.\.venv\Scripts\python.exe -m dwindy.ingest sync --manifest .\data\collection.toml --index .\data\retrieval.sqlite3
```

Set in `api.local.toml`:

```toml
retrieval_index_path = "data/retrieval.sqlite3"
retrieval_context_tokens = 768
retrieval_default = "auto"
```

```powershell
.\.venv\Scripts\dwindy-api.exe --config config.local.toml --api-config api.local.toml --chat-root .
```

Open `/chat/`. **Use local documents** starts checked. Questions can receive selected local
passages; the server does not discover or ingest unlisted documents during chat.

### Recipe 4: Reach + documents + persistence

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api,reach]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m dwindy.ingest sync --manifest .\data\collection.toml --index .\data\retrieval.sqlite3
```

Create the section 8 collection first. Set in `api.local.toml`:

```toml
reach_provider = "wikipedia"
reach_default = "auto"
retrieval_index_path = "data/retrieval.sqlite3"
retrieval_context_tokens = 768
retrieval_default = "auto"
database_path = "data/conversations.sqlite3"
database_max_mib = 128
```

```powershell
.\.venv\Scripts\dwindy-api.exe --config config.local.toml --api-config api.local.toml --chat-root .
```

Expect both optional evidence controls and saved-conversation controls at `/chat/`.
Conversation and retrieval databases are different files. Reach does not automatically
augment every local retrieval turn; local evidence/project-directed requests can suppress it.
Persistence saves completed conversation text, not an evidence archive.

### Recipe 5: embedded modal in another page

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api]'
.\.venv\Scripts\python.exe -m pip check
```

For the existing repository example, set in `api.local.toml`:

```toml
allowed_origins = ["http://127.0.0.1:8080"]
```

Start the API:

```powershell
.\.venv\Scripts\dwindy-api.exe --config config.local.toml --api-config api.local.toml
```

In a second terminal at the repository root, serve the example host page:

```powershell
.\.venv\Scripts\python.exe -m http.server 8080 --bind 127.0.0.1 --directory web
```

Open **http://127.0.0.1:8080/examples/embedded.html** and click the chat launcher. This
second server represents the independent host application for this development example;
the normal standalone recipe needs only one server. The example does not give Dwindy
knowledge of the Garden Club page. For an actual application, serve the component files
from that application's static directory as described in section 13.

### Recipe 6: custom frontend/API-only

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\dwindy-api.exe --config config.local.toml
```

No API configuration file is required for local non-browser requests; no bundled UI is
served. Use section 14's HTTP examples. An independently hosted browser frontend needs
its exact origin in `allowed_origins` and an explicit API base. Optional features use
the same settings as the standalone recipes, not a different runtime installation.

## 3. Get Dwindy

With Git installed:

```powershell
git clone https://github.com/Hugee20/dwindy.git
Set-Location dwindy
```

Without Git, visit [Dwindy on GitHub](https://github.com/Hugee20/dwindy), select **Code →
Download ZIP**, extract the archive, and open PowerShell in the extracted directory.
Confirm it contains `pyproject.toml`, `config.example.toml`, `src/` and `web/`.
Cloning preserves Git history/update tools; the ZIP supplies source without a Git checkout.
The current `main` includes the post-1.0.0 standalone/setup fixes described here; the original
`v1.0.0` tag predates those fixes. Use current source for this documented flow.

Python **3.11+** is declared supported by package metadata. The validated reference
environment is **Windows x86-64, Python 3.13.0**, with an Intel i3-1215U and about 7.7 GB
usable RAM. That is an observed working environment, not a minimum hardware guarantee.
Other Python versions/platforms are not equivalently validated. The selected native
runtime wheel must support your Python and platform. Browser validation covers Chromium
on Windows; no equivalent Firefox/Safari coverage is claimed.

This guide assumes a source installation. Python packaging does not include the frontend
bundle: retain the checkout/ZIP's `web/` and `web/assets/` for standalone or embedding use.

## 4. Create the environment and install

From the source directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api]'
.\.venv\Scripts\python.exe -m pip check
```

Expected final check: `No broken requirements found.` Activation is unnecessary when
using the explicit executables above. If desired, `.\.venv\Scripts\Activate.ps1`
activates the environment, subject to your
PowerShell execution policy; this guide does not require changing that policy.

`-e` installs the current source editably. The base dependency is pinned
`llama-cpp-python==0.3.35`. The CPU wheel index is maintained by that runtime project;
`--only-binary=llama-cpp-python` makes installation fail if no suitable runtime wheel
exists instead of unexpectedly compiling it. Other dependencies may still use build
isolation. Installation needs network access unless dependency wheels were prepared separately.
There is no installation or model download during ordinary Dwindy startup.

| Extra | Purpose |
|---|---|
| `api` | FastAPI/Uvicorn server; needed for standalone, embedded and custom HTTP clients |
| `reach` | `truststore==0.10.4`, OS-native verified TLS for Wikipedia; use with `api` |
| `project` | `pathspec==1.1.1`, bounded project ignore matching during synchronization |
| `api-test` | HTTP test client; unnecessary for normal chat |
| `eval` | Resource-measurement support; unnecessary for normal chat |

For a dependency-fetch timeout, including setuptools in pip's isolated build environment,
retry the same installation with a longer socket timeout:

```powershell
.\.venv\Scripts\python.exe -m pip install --timeout 120 --retries 5 --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api]'
.\.venv\Scripts\python.exe -m pip check
```

Substitute the chosen extras, for example `.[api,reach,project]`, without dropping the
CPU-wheel options. A timeout does not establish a Dwindy runtime defect. If there is no
matching wheel, consult the [runtime installation documentation](https://llama-cpp-python.readthedocs.io/en/latest/)
for compiler-based alternatives; do not assume a source build needs no toolchain.

## 5. Provide and configure a GGUF

### Tested reference artifact

The validation model is **Qwen3-1.7B Q4_K_M**, ggml-org's GGUF quantization of the upstream
model. This is setup/license information, not Dwindy's conversational identity.

| Field | Value |
|---|---|
| Publisher/repository | `ggml-org/Qwen3-1.7B-GGUF` on Hugging Face |
| Pinned revision | `daeb8e2d528a760970442092f6bf1e55c3b659eb` |
| Filename | `Qwen3-1.7B-Q4_K_M.gguf` |
| Size | 1,282,439,264 bytes; about 1.28 GB / 1.19 GiB |
| SHA-256 | `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5` |
| Model license | Apache-2.0; review the publisher's model card/upstream license |

Use the [revision-pinned artifact page](https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/blob/daeb8e2d528a760970442092f6bf1e55c3b659eb/Qwen3-1.7B-Q4_K_M.gguf)
to download deliberately in your browser and save it, for example, in `D:\Models`.
Verify it:

```powershell
Get-FileHash 'D:\Models\Qwen3-1.7B-Q4_K_M.gguf' -Algorithm SHA256
```

Hash letter case is irrelevant. Other compatible text chat GGUFs can be used, but matching
names or quantization labels do not make them the tested artifact. Models need a supported
embedded `tokenizer.chat_template` that can represent system messages. Dwindy does not
download missing templates, infer a model-family fallback, or support every GGUF.
The repository's [Apache-2.0 source license](../LICENSE) is separate from model licensing;
preserve applicable notices when distributing either.

### Create the model configuration

```powershell
Copy-Item config.example.toml config.local.toml
notepad config.local.toml
```

For the reference model at the example path, the complete minimal configuration is:

```toml
model_path = 'D:\Models\Qwen3-1.7B-Q4_K_M.gguf'

[chat_template_kwargs]
enable_thinking = false
```

The copied example also supplies reasonable starting defaults: `context_size = 4096`,
`max_tokens = 256`, `temperature = 0.7`, `seed = 42`, runtime-selected threads and empty
additional `system_prompt`. Change only what you need. Keep `[chat_template_kwargs]`
**after all top-level model settings**; otherwise subsequent assignments belong to that table.

These Windows TOML paths are equivalent:

```toml
model_path = "D:/Models/Qwen3-1.7B-Q4_K_M.gguf"
# Or a literal string:
# model_path = 'D:\Models\Qwen3-1.7B-Q4_K_M.gguf'
# Or escaped backslashes in a double-quoted string:
# model_path = "D:\\Models\\Qwen3-1.7B-Q4_K_M.gguf"
```

An ordinary double-quoted `"D:\Models\..."` is invalid because backslashes introduce TOML
escapes. Relative model paths resolve against the model TOML's directory, not necessarily
the shell directory. `--model` overrides the path and resolves relative paths against the
shell directory. URLs and UNC model paths are rejected; keep offline data on physical local storage.

For compatible Qwen3 templates, `enable_thinking = false` avoids spending the short output
budget on reasoning. It is a template variable, not a universal model switch. Recognized
Qwen3 leading reasoning is decoded before Core/API/UI/new saved assistant turns even when
thinking is enabled. Literal user text and tags in the final answer are not stripped.
If generation exhausts its allowance before reaching a final answer, the turn fails instead
of exposing/saving reasoning. Other backend protocols are not promised equivalent decoding.

Use an editor to save **UTF-8 without BOM**. Windows PowerShell 5.1's `Set-Content -Encoding
utf8` adds a BOM rejected by the configuration TOML parser. Copy/edit the examples instead.

## 6. Run the standalone demo

```powershell
.\.venv\Scripts\dwindy-api.exe --config config.local.toml --chat-root .
```

Equivalent module launch:

```powershell
.\.venv\Scripts\python.exe -m dwindy.server --config config.local.toml --chat-root .
```

Wait for startup, then open **http://127.0.0.1:8000/chat/**. It redirects to
`/dwindy/web/index.html`. `--chat-root .` explicitly selects the repository's complete
`web/` bundle. It does not mount the repository, local configs, models or test pages publicly.
The one process serves both the API and this UI; no static server/CORS setup is needed.

The demo uses the same model/API configuration as any API client. Add `--api-config
api.local.toml` only when using optional server settings. Neither file is auto-discovered.
API-hosted chat defaults to its own origin. A separately served `web/` page defaults to
`http://127.0.0.1:8000`; its Connection settings allow an alternate API base and token.

The interface renders plain text, not Markdown/HTML. Enter sends, Shift+Enter inserts a
newline. Reach/retrieval controls appear only after health reports them configured; saved
conversation controls appear when persistence is enabled. A checked evidence control
requests automatic selection, not guaranteed evidence supply.

Stop with **Ctrl+C**, allow shutdown to finish, then rerun the same command to restart.
Model/config/source changes require restart. Do not launch multiple workers or use reload.
Restart loses ephemeral conversation IDs; persistent IDs can be manually resumed.
Section 11 explains New conversation versus Delete saved conversation.

## 7. Configuration and feature switches

### Which file owns which settings?

| File | Implemented settings |
|---|---|
| `config.local.toml` | `model_path`, `context_size`, `max_tokens`, `temperature`, `seed`, `threads`, `system_prompt`, `[chat_template_kwargs]` |
| `api.local.toml` | Binding/security, conversation capacity, persistence, local index, evidence allowance, Reach provider/default |
| `project.local.toml` | Project identity/root, permitted discovery/selections, exclusions and project index path |
| `collection.toml` | Explicit `[[documents]]` records with `id`, `path`, `name` |

Unknown configuration keys fail. There is no `retrieval_enabled`, `retrieval_root` or
`reach_enabled` setting: these enabled flags are health output, not input.
API paths resolve against the API TOML; project config paths resolve against the project
TOML, with selected-file lists relative to its project root.

### Feature matrix

| Feature | Dependency | Configuration/control | Default | Enable example | Disable example | Restart? |
|---|---|---|---|---|---|---|
| Reach | `api,reach` | API `reach_provider`, `reach_default`; request `reach` | No provider; off | `reach_provider = "wikipedia"`, `reach_default = "auto"` | Omit provider globally; request `false` for one turn | Yes for server config; no for request |
| Documents | `api`; stdlib SQLite with FTS5 | API `retrieval_index_path`, `retrieval_default`, `retrieval_context_tokens`; request `retrieval` | No index; auto when configured | Existing index path, default `"auto"` | Omit index globally; request `false` | Yes for config/index refresh; no for request |
| Persistence | `api`; stdlib SQLite | API `database_path`, `database_max_mib` | Ephemeral; cap 128 MiB if enabled | `database_path = "data/conversations.sqlite3"` | Omit path; existing saved files are not deleted | Yes |
| Thinking | Base runtime; compatible template | Model `[chat_template_kwargs] enable_thinking` | Template default | `enable_thinking = true` if supported | `enable_thinking = false` if supported | Yes |
| Standalone hosting | `api` and source `web/` bundle | CLI `--chat-root` | Not hosted | `--chat-root .` | Omit argument | Yes |
| Cross-origin browser access | `api` | API `allowed_origins` | Same-origin only | `["http://127.0.0.1:8080"]` | `[]` | Yes |
| Bearer authentication | `api` | API `token_env`; named environment variable | None unless variable is set | Set `DWINDY_API_TOKEN` before launch | Unset variable before launch | Yes |
| Project Awareness | `project` for sync; `api` for HTTP | Project config, manual sync; API `retrieval_index_path` | No snapshot | Build project index, point API to it | Omit API index path | Yes after sync/config; no automatic refresh |

`reach_default = "off"` or `retrieval_default = "off"` disables automatic use but still
allows an explicitly enabled request. Removing the provider/index disables the feature
at deployment level. Enabling persistence creates its parent directory; retrieval requires
an index that already exists. Project and document collections share one configured index;
a project configuration can explicitly combine one ordinary manifest.

### Mode syntax: keep the three interfaces distinct

| Interface | Automatic | Forced | Off |
|---|---|---|---|
| API TOML `retrieval_default` / `reach_default` | `"auto"` | Not accepted | `"off"` |
| HTTP JSON `retrieval` / `reach` | `"auto"` | `true` | `false` |
| Terminal CLI `--retrieval` | `auto` | `on` | `off` |

JSON omission uses the server default; explicit `null`, `"on"` and `"off"` are invalid for
these request fields. Forced local search bypasses automatic usefulness selection;
forced Reach still applies its admission checks. Both obey budget/availability boundaries
and do not guarantee an answer-bearing passage. The bundled checkboxes send `"auto"` or
`false`, not `true`. Terminal defaults to `auto` when `--retrieval-index` is supplied;
terminal Reach and API persistence are not enabled through that CLI.

### API/server settings

| Key | Default / purpose |
|---|---|
| `host`, `port` | `"127.0.0.1"`, `8000`; host is a literal IP |
| `allow_non_loopback` | `false` |
| `allowed_hosts` | `["127.0.0.1", "localhost", "::1"]`; exact names/IPs, no ports |
| `allowed_origins` | `[]`; additional exact scheme/host/port origins, no trailing slash |
| `token_env` | `"DWINDY_API_TOKEN"`; environment variable name, not secret value |
| `max_conversations` | `16` in-memory conversations |
| `conversation_idle_seconds` | `1800`; memory-cache idle expiry |
| `max_request_bytes` | `65536`; separate from model context limits |
| `ssl_certfile`, `ssl_keyfile` | Unset; configure both together |
| `database_path`, `database_max_mib` | Unset path; `128` MiB main-file cap |
| `retrieval_index_path` | Unset; existing local document/project index |
| `retrieval_context_tokens` | `768`; incremental evidence allowance, including framing, for local retrieval/Reach |
| `retrieval_default` | Auto with an index, otherwise off; explicit values `"auto"`, `"off"` |
| `reach_provider`, `reach_default` | No provider; off. Only provider `"wikipedia"`; defaults `"auto"`, `"off"` |

To enable local bearer authentication without saving a secret in TOML:

```powershell
$env:DWINDY_API_TOKEN = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\dwindy-api.exe --config config.local.toml --chat-root .
```

Keep the token available to your authorized client. Enter it in the standalone connection
form; API calls use `Authorization: Bearer ...`. To disable in this shell before restarting:

```powershell
Remove-Item Env:DWINDY_API_TOKEN -ErrorAction SilentlyContinue
```

Tokens must contain at least 32 non-whitespace ASCII characters. Static bootstrap assets
remain accessible without the token; API/schema routes require it. CORS is not authentication.
All authorized clients share a trust boundary; conversation IDs are not per-user permissions.
Never publish a deployment-wide bearer secret in a widget, HTML, URL or JavaScript bundle.

Non-loopback serving additionally requires `allow_non_loopback = true`, a token, existing
TLS certificate/key files and appropriate `allowed_hosts`. This is not a public-service
deployment framework: there are no accounts, reverse-proxy contracts or rate limiting.
Use local defaults for the demo.

## 8. Local document retrieval

Dwindy does **not** scan a documents folder automatically. The manifest is the complete
authoritative collection. Create files with an editor rather than PowerShell-generated TOML:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
notepad .\data\manual.md
```

Save `data/manual.md` as UTF-8 with this example text:

```text
# Equipment manual

An Amber equipment loan lasts 21 days. Return the equipment to reception.
```

Then create the manifest:

```powershell
notepad .\data\collection.toml
```

Save:

```toml
[[documents]]
id = "manual"
path = "manual.md"
name = "Equipment manual"
```

Paths resolve beneath the manifest directory, so `manual.md` means `data/manual.md`.
Only UTF-8 `.md`/`.txt` files are accepted; PDFs, Word documents and arbitrary directories
are not supported. IDs must be unique, 1–64 ASCII letters/digits/underscore/hyphen; names
are nonblank and at most 128 characters. Absolute/escaping paths are refused.

With the API stopped:

```powershell
.\.venv\Scripts\python.exe -m dwindy.ingest sync --manifest .\data\collection.toml --index .\data\retrieval.sqlite3
```

Add `retrieval_index_path = "data/retrieval.sqlite3"` to the explicitly passed API TOML,
then restart. A missing/corrupt/incompatible configured index fails startup. The collection
and conversation database must use different files. SQLite must provide FTS5.

After document changes, additions or deletions, update the authoritative manifest as needed,
stop the API, repeat the same sync command, and restart. Omitted document IDs are deleted
from the index. `documents = []` intentionally empties the collection. There are no watchers,
HTTP ingestion routes or hot reload. Failed synchronization of an existing index rolls back.

Search explicitly using section 14's `/v1/retrieve` example. For chat, `retrieval:true` forces
search, while `"auto"` applies context selection before Core budgeting. At most three whole
passages enter the model. FTS ranking, automatic usefulness checks and budgets are distinct
steps; finding a candidate does not mean it was supplied.

Local chat metadata contains `retrieval.status` and `retrieval.sources` with document/chunk
IDs, source path/hash, heading and spans. Sources represent actual supplied entries, not
every match. `/v1/retrieve` returns passage text and ranking scores, but is a separate search,
not a receipt for an earlier conversation. Its scores are rankings, not factual confidence.
The bundled UI shows a passage-count/status line rather than a local-document source browser.

The index stores source text unencrypted. All authorized API clients can search the configured
collection. Retrieval misses synonyms/morphology and can admit irrelevant lexical matches;
it does not verify truth, freshness or answerability. See [retrieval details](RETRIEVAL.md).

Terminal use of the same index is optional:

```powershell
.\.venv\Scripts\python.exe -m dwindy --config config.local.toml --retrieval-index .\data\retrieval.sqlite3 --retrieval auto
```

Use `--retrieval on` to force local search or `--retrieval off` to omit it. These terminal
arguments do not read `api.local.toml` or enable API persistence/online Reach.

## 9. Project Awareness

Project Awareness builds a controlled snapshot of **one explicitly configured project**,
then uses the same lexical retrieval. It is not live codebase understanding.

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api,project]'
.\.venv\Scripts\python.exe -m pip check
Copy-Item project.example.toml project.local.toml
notepad project.local.toml
```

For a separate sibling project directory, an example is:

```toml
project_id = "my-project"
name = "My Project"
root = "../my-project"
index_path = "data/my-project.sqlite3"
documentation_dirs = ["docs"]
source_files = []
config_files = []
exclude = []
```

Set `root` to an existing approved directory. Keep the index **outside** that directory;
if indexing Dwindy's own repository, choose an index outside the Dwindy root instead.
Retain a stable developer-chosen `project_id`.

With the API stopped:

```powershell
.\.venv\Scripts\python.exe -m dwindy.project sync --config project.local.toml --dry-run
.\.venv\Scripts\python.exe -m dwindy.project sync --config project.local.toml
```

Point `api.local.toml` at the built index with `retrieval_index_path`, then launch as usual.
Project indexes use schema version 2 and include snapshot metadata; ordinary document
indexes use version 1. They are not silently migrated/repurposed. Do not use manifest-only
`dwindy.ingest sync` on a project index. A project's optional `documents_manifest` can
explicitly combine one ordinary collection during project sync.

Default discovery includes root `DWINDY.md`/README `.md`/`.txt`, permitted documentation
directories and narrowly selected metadata. Source files are not discovered by default:
list individual `.py/.js/.jsx/.ts/.tsx` files; configuration selections support `.toml/.json`.
Hard exclusions override selections/ignore negation, `.gitignore` is respected, and unsafe
links/reparse points are refused. These controls are not secret scanning.

`DWINDY.md` is untrusted knowledge, never an agent instruction or a grant of permissions.
Typed PROJECT entries and narrow observation warnings are representation, not guarantees
of model obedience. Health exposes `project_snapshot` identity and `freshness: "not_checked"`,
not the absolute project root. Nothing scans or synchronizes automatically at startup/chat.
Repeat dry-run/sync/restart to refresh changed/deleted files. See [Project Awareness](PROJECT_AWARENESS.md)
for exclusions, format/resource limits, provenance and rollback details.

## 10. Wikipedia Reach

Install `.[api,reach]` and configure `reach_provider = "wikipedia"` to permit Reach.
The `reach` extra supplies OS-native certificate verification needed on the reference
Windows platform. TLS verification is never disabled. Omitted provider means disabled;
configured provider with omitted default means off.

`reach_default = "auto"` permits the implemented freshness/explicit-lookup cues. Request
`reach:true` deliberately asks for lookup, `"auto"` selects the detector, and `false` keeps
that turn offline. The UI's **Use Wikipedia** checkbox selects auto/false. A question's
wording may not trigger auto; direct API `true` is the explicit lookup control.

| Public state | Meaning |
|---|---|
| `disabled` | Provider absent or turn off |
| `not_attempted` | No transport attempt; for example not fresh, local context or unusable query |
| `unavailable` | Transport/provider/certificate error or busy transport |
| `not_supplied` | No results, rejected material or no entry fitting Core's allowance |
| `supplied` | At least one admitted WEB entry actually survived Core preparation/budgeting |

Inspect `reason`, `attempted`, `candidate_count`, `admitted_entry_ids`, `supplied_entry_ids`
and `sources`. The minimized `query` appears only after an attempted transport request.
Article links derive from **supplied** entries; multiple entry IDs may collapse to one
article source. Rejected/budget-excluded entries are not advertised as supplied.

The frontend renders one separate receipt for unavailable/not-supplied/supplied states;
disabled/not-attempted turns do not clutter the transcript. `Referenced from Wikipedia — <article>`
means article material entered the model input. It does not mean Wikipedia
verified the answer, that every statement is supported, or that the model used it correctly.

Reach uses one bounded request: verified HTTPS, five-second caller deadline, 512 KiB
response ceiling, up to three selected results of at most 1,600 characters, no retries,
redirects, cookies, crawling or additional providers. Core still limits actual supply to
three entries and the configured evidence allowance. A timed-out native request holds its
single transport slot until it finishes; further requests fall back with `transport_busy`
instead of accumulating queued work.

Only a minimized current-message query leaves the machine, at most 12 terms/200 characters.
History, local passages and host context are not appended; filtering is not comprehensive
secret detection. Wikipedia/network operators can see the query. Keep Reach off for private
inputs. Network failure preserves ordinary local/model operation.

Complete plain-text introductions are acquired within the response bound, then literal
query/title coverage selects bounded verbatim passages. Exact source-title context helps
admission; related qualified titles are not equivalent subjects. There is no infobox parser,
semantic matching, abbreviation expansion (`UN` versus `United Nations`), freshness verifier
or generated summary. Wikipedia coverage and literal admission can miss answer-bearing
material. See [practical Reach](REACH_V1.md); historical Reach/H2 experiments are not the
operational acceptance contract.

## 11. Conversation persistence

Add to the API TOML and restart:

```toml
database_path = "data/conversations.sqlite3"
database_max_mib = 128
```

No extra storage package is needed. Omit the path for ephemeral operation. Configuration
does not delete old databases when disabled. Configured unavailable/corrupt storage fails
instead of silently becoming ephemeral. Keep the database on private physical local storage
and do not share it between running processes.

Storage contains completed original user text, final assistant text, finish reason,
timestamps and retained-context boundaries. Leading recognized reasoning, evidence packets,
Reach receipts, host context, system identity/prompts, credentials and incomplete turns are
not stored. An assistant answer can repeat source content: transience is not secret scrubbing.
Conversation text is **unencrypted**; deletion is logical, not secure erasure.

JSON success and SSE `completed` follow successful persistence. Earlier streamed output is
provisional. On restart, a known ID restores the retained context suffix; old trimmed turns
stay in the archive but do not reappear in model context. There is no transcript-list/history
endpoint or ID-recovery list. Save the ID before leaving the page; browser storage is not used.

| Operation | Ephemeral server | Persistent server |
|---|---|---|
| UI New conversation / `newConversation()` | DELETE current known ID, then clear | Detach/clear UI; keep saved turns |
| `resetConversation()` / DELETE API | Remove known conversation | Delete saved turns and cached conversation |
| Reload page | Browser loses ID/transcript | Browser loses ID/transcript; saved turns remain |
| Restart server | IDs/history lost | Saved IDs can resume |

The UI supports copying/resuming IDs and explicit **Delete saved conversation** with
confirmation. Resume restores model context on the next message, not old transcript display.
Stop cleanly before database backups. See [persistence](PERSISTENCE.md) for failure/delivery races.

## 12. Capabilities and application identity

Dwindy computes explicit bounded arithmetic itself, without `eval` or model tool calling.
Try `924 * 17` or `calculate 3 * (4 + 5)`. Word problems, units and arbitrary code execution
are outside its calculator. Clock cues such as `What's the current year?` supply a fresh
**server-local** time/date fact, not the user's inferred time zone. Neither feature needs
a toggle/dependency. API `capabilities` metadata reports computed facts; Qwen's rendered
answer is still generated and can misstate them. See [capabilities](CAPABILITIES.md).

Authenticated host context is optional information from an application's trusted backend:

```json
{"message":"When is my loan due?","host_context":[{"label":"Current loan","text":"Microscope M-2 is due 2026-10-10."}]}
```

It requires bearer authentication and host-side authorization. The host backend should
proxy the request and attach context/token, not ship secrets to a public browser.
Limits: 1–8 entries, labels up to 64 characters, each text up to 2,000, total text up to
4,000, with a separate 1,024-token host allowance. Context is transient information, not
an instruction, capability grant or host action. Dwindy has no executor for host actions.

API/terminal wiring adds transient system identity: **Dwindy, a local AI assistant powered
by a local large language model**, developed as part of the Dwindy project. Ordinary identity
contains no model/vendor name. Empty configured `system_prompt` means no additional custom
system text, not absence of Dwindy's built-in identity. This identity uses normal token
accounting and is not saved history; it remains input to a generative model, not an enforced
response template. Loaded backend name/architecture can be read by Python through optional
`LlamaBackend.model_metadata()`; unknown values remain `None`. There is no public model-info
HTTP endpoint. Licensing attribution belongs in distribution documentation, not assistant branding.

## 13. Embed the Web Component

Copy the source `web/` bundle into your application's static directory, preserving layout:

```text
vendor/dwindy/web/
  index.html
  standalone.js
  standalone.css
  api-client.js
  dwindy-chat.js
  dwindy-chat.css
  assets/branding/dwindy-lockup.png
  assets/branding/dwindy-wordmark.png
  assets/chatheads/dwindy-idle.png
  assets/chatheads/dwindy-working.png
```

Embedded-only use needs `dwindy-chat.js`, `api-client.js`, `dwindy-chat.css`, wordmark and
two chatheads. Keeping all ten runtime files also permits standalone use. The module loads
its stylesheet/assets relative to itself, not the embedding page route. `web/examples/embedded.html`
is the existing example; `web/tests/` is not needed for deployment.

In the host page:

```html
<script type="module" src="/vendor/dwindy/web/dwindy-chat.js"></script>
<dwindy-chat api-base="http://127.0.0.1:8000"
             display-name="Dwindy"
             position="bottom-right"
             placeholder="Ask a question"></dwindy-chat>
```

For **same-origin** hosting, omit `api-base` or set it to the origin/base prefix serving the
API. No additional allowed origin is needed. Your application must actually expose `/v1/*`
at that selected base; copying JS alone does not mount Dwindy's API into a host application.

For **cross-origin** hosting, specify the API base and allow the **page's** exact origin:

```toml
allowed_origins = ["http://127.0.0.1:8080"]
```

Pass that API TOML explicitly. `localhost` and `127.0.0.1` are different origins. Do not use
`file://`; null origins are denied. The bundled server allowlists its own frontend files;
it does not host arbitrary embedded examples/host pages. Browser mixed-content, local-network
permissions and the host's CSP can impose additional restrictions. Allow the chosen API
in `connect-src` and self-host modules/styles/images.

For a user-entered token in a trusted local/private host page:

```javascript
await customElements.whenDefined('dwindy-chat');
const chat = document.querySelector('dwindy-chat');
chat.bearerToken = tokenEnteredByTheUser;
chat.setAttribute('open', '');       // Open floating modal.
chat.removeAttribute('open');       // Close; preserve conversation/request.
await chat.newConversation();       // Preserve saved turns on persistent servers.
await chat.resetConversation();     // Explicitly delete current conversation.
// While fresh/idle, after connecting to a persistence-enabled server:
// chat.resumeConversation(savedId);
```

These are separate operations, not a sequence needed for every turn. Boolean attributes
use presence: `open="false"` still opens. The default presentation is floating; set
`presentation="inline"` before attachment for inline use. Removing/reparenting the component
aborts an active request; closing the modal merely hides it.

`chat.connect(base, token)` applies connection settings together. Changing destination/token
detaches the old conversation locally without deleting it or forwarding old credentials/IDs.
Unchanged connection settings use normal New conversation behavior. Settings cannot change
during an active operation. The host owns authorization, page layout and any host context;
Dwindy owns conversation lifecycle, evidence handling and deterministic status.
See [the component contract](CHAT_INTERFACES.md) for accessibility and lifecycle details.

## 14. Custom frontend and Python integration

### Inspect health

In a second PowerShell window:

```powershell
$headers = @{}
if ($env:DWINDY_API_TOKEN) { $headers.Authorization = "Bearer $env:DWINDY_API_TOKEN" }
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/health' -Headers $headers
```

If you started with a token in another shell, provide that same token here; environment
variables do not automatically transfer between existing terminals. Basic demo health:

```json
{"status":"ready","busy":false,"persistence_enabled":false,"retrieval_enabled":false}
```

A configured index adds `retrieval_default`; a project index adds `project_snapshot`.
A configured provider adds `reach_enabled:true`, `reach_provider:"wikipedia"` and
`reach_default`. Those Reach fields are omitted when unconfigured. Enabled means permitted,
not provider availability or evidence supply. Health performs no inference/provider lookup.

### Non-streaming chat, follow-up and deletion

```powershell
$body = @{ message = 'Hello'; stream = $false; retrieval = $false; reach = $false } | ConvertTo-Json
$reply = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/chat' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
$reply.text
$id = $reply.conversation_id

$body = @{ message = 'Remember the number 418 for this conversation.'; conversation_id = $id; stream = $false; retrieval = $false; reach = $false } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/chat' -Method Post -Headers $headers -ContentType 'application/json' -Body $body

# Explicit reset/deletion, including saved turns if persistence is enabled:
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/conversations/$id" -Method Delete -Headers $headers
```

Omit `conversation_id`/use `null` for a new conversation; reuse the returned 32-character
opaque ID for follow-ups. The server retains native history; do not resend a client transcript.
Non-streaming success includes `text`, `conversation_id`, `finish_reason`, `dropped_turns`,
`usage` and applicable retrieval/Reach/capability metadata. DELETE returns 204; unknown/expired
IDs return 404, active conversations 409. There is no endpoint to clear every conversation.

An equivalent ordinary-chat request using PowerShell's actual `curl.exe`:

```powershell
'{"message":"Hello","stream":false,"retrieval":false,"reach":false}' | curl.exe --request POST 'http://127.0.0.1:8000/v1/chat' --header 'Content-Type: application/json' --data-binary '@-'
```

This last example assumes no configured token; add `--header "Authorization: Bearer
$env:DWINDY_API_TOKEN"` when needed. For non-ASCII request text, use a client that sends
explicit UTF-8 rather than relying on Windows PowerShell 5.1's native-pipeline encoding.

### Inspect local retrieval and Reach

With the section 8 index configured:

```powershell
$body = @{ query = 'How long is an Amber equipment loan?' } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/retrieve' -Method Post -Headers $headers -ContentType 'application/json' -Body $body

$body = @{ message = 'How long is an Amber equipment loan?'; retrieval = $true; reach = $false } | ConvertTo-Json
$reply = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/chat' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
$reply.retrieval | ConvertTo-Json -Depth 8
```

With Wikipedia configured, make a deliberate lookup:

```powershell
$body = @{ message = 'Who is the current president of the Philippines?'; reach = $true; retrieval = $false } | ConvertTo-Json
$reply = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/chat' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
$reply.reach | ConvertTo-Json -Depth 8
$reply.text
```

Inspect `supplied_entry_ids` separately from `admitted_entry_ids` and source links. Public
Reach receipts do not contain full WEB passage text; there is no saved-packet/history
inspection endpoint. A fresh lookup cannot reconstruct an old packet exactly.
The receipt proves which entries Core put in the packet, not that those entries contain
the answer or that generated prose is correct. To diagnose correctness, inspect answer-bearing
source material separately where available; do not infer it solely from a `supplied` flag.

### Streaming and custom browser clients

Set `stream:true` for `text/event-stream`. SSE event names are:

| Event | Meaning |
|---|---|
| `started` | Conversation ID, dropped turns and actual prepared evidence/capability metadata |
| `delta` | Final-answer text fragment in `data.text` |
| `completed` | Successful completion metadata; durable storage has committed when enabled |
| `error` | Failed/incomplete turn; no successful completion acknowledgement |

Do not treat `started` or a stream of deltas as a committed turn. Parse SSE incrementally
across network chunks/UTF-8 boundaries, handle HTTP errors before parsing, and require
`completed`. Stop aborts transport but cannot instantly kill native inference; commit can
race with disconnect. Never automatically retry an uncertain turn. Error bodies use
`{"error":{"code":"...","message":"..."}}`; meaningful errors include authentication,
origin denial, context/body limits, inference busy and storage/receipt-delivery uncertainty.

A minimal custom same-origin non-streaming client, using your own UI:

```javascript
let conversationId = null;
async function sendMessage(message) {
  const response = await fetch('/v1/chat', {
    method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message, conversation_id: conversationId, stream: false})
  });
  const reply = await response.json();
  if (!response.ok) throw new Error(reply.error?.message || `HTTP ${response.status}`);
  conversationId = reply.conversation_id;
  return reply; // Render reply.text as textContent; render receipts separately.
}
```

Add authorized token handling/CORS configuration for your deployment. A custom frontend
must implement its own UI, ID retention/reset, authentication, errors/busy state,
cancellation semantics, SSE parsing if used, source/status presentation and accessibility.
Do not parse generated prose to determine source/tool state. Only `/v1/retrieve` exposes
local passage ranking scores; they are not generated-answer confidence. There is no public
semantic-similarity score. `/openapi.json` supplies the local contract under normal security
controls; interactive/CDN documentation is disabled.

### In-process Python use

The HTTP frontend is optional; Core can borrow a backend directly:

```python
from contextlib import closing
from dwindy.backend import TextDelta
from dwindy.config import load_config
from dwindy.core import DwindyCore
from dwindy.identity import runtime_system_prompt
from dwindy.llama_backend import LlamaBackend

config = load_config("config.local.toml")
backend = LlamaBackend(config)
try:
    core = DwindyCore(backend, options=config.options(),
                      system_prompt=runtime_system_prompt(config.system_prompt))
    with closing(core.chat("Hello")) as stream:
        for event in stream:
            if isinstance(event, TextDelta):
                print(event.text, end="", flush=True)
    core.reset()
finally:
    backend.close()
```

This explicitly adds application identity like API/terminal wiring. Bare Core does not
automatically create the API's tools, retrieval, provider, storage or scheduler. Applications
own that wiring and backend lifetime; serialize backend access and exhaust/close streams.
See [architecture](ARCHITECTURE.md) for the library boundaries.

## 15. Customize the frontend

| Current source file | Responsibility |
|---|---|
| `web/index.html` | Standalone outer header/logo, connection form, page text and inline component |
| `web/standalone.js` | Standalone API-base initialization and connection form behavior |
| `web/standalone.css` | Outer page colors/layout/connection form |
| `web/dwindy-chat.js` | Web Component markup, labels, assets, modal/inline lifecycle and deterministic receipts |
| `web/dwindy-chat.css` | Component's Shadow DOM layout, colors, message/receipt styling and responsive styles |
| `web/api-client.js` | HTTP/SSE, authentication, IDs, cancellation and reset transport; not a styling file |
| `web/assets/branding/dwindy-lockup.png` | Standalone header artwork |
| `web/assets/branding/dwindy-wordmark.png` | Component branding footer artwork |
| `web/assets/chatheads/dwindy-idle.png` | Idle avatar/launcher |
| `web/assets/chatheads/dwindy-working.png` | Active-request avatar/launcher |
| `web/examples/embedded.html` | Sample independent host page; not required runtime bundle |

Use `display-name`, `placeholder`, `position`, `hide-branding`, `hide-avatar` and optional
same-origin `avatar-src` for supported presentation changes. Boolean `hide-branding` hides
the component footer; it does not hide avatars or the standalone outer header. An `avatar-src`
is reused across states; it does not create a custom state-map feature.

The four supported host CSS color variables are:

```css
dwindy-chat {
  --dwindy-primary: #304a52;
  --dwindy-on-primary: #ffffff;
  --dwindy-accent: #d7b86b;
  --dwindy-on-accent: #171a10;
}
```

Host CSS does not generally style Shadow DOM internals. Edit `dwindy-chat.css` for internal
background/layout changes; edit `standalone.css` for the outer page. Keep contrast, focus,
mobile layout, status regions and reduced-motion behavior intact. Replacing PNG contents
at the existing paths retains built-in serving support. Renaming files would also require
updating references and, for built-in hosting, its fixed asset allowlist; it is not merely
a presentation-only edit.

### Generic/unbranded recipe

For an embedded neutral local-AI interface without editing component behavior:

```html
<script type="module" src="/vendor/dwindy/web/dwindy-chat.js"></script>
<dwindy-chat display-name="Local Assistant" hide-branding hide-avatar
             placeholder="Type a message"
             api-base="http://127.0.0.1:8000"></dwindy-chat>
```

For the standalone page, additionally edit `web/index.html`: replace its page title and
outer `page-header` image/tagline with plain neutral text; add `display-name="Local
Assistant" hide-branding hide-avatar` to the existing inline element. Keep the connection
form IDs and scripts intact. Adjust the two CSS files as needed. If keeping artwork,
replace the four bundled PNGs at the same filenames instead. Retain the complete required
bundle even when images are hidden: `--chat-root` validates those files.

This changes presentation, **not** runtime identity: the assistant remains Dwindy. Do not
change system identity or legal notices to achieve frontend branding. Preserve applicable
source/model distribution licenses separately. Labels, artwork and CSS are presentation;
request fields, receipt derivation, token handling, SSE parsing and reset/cancellation code
affect protocol/runtime behavior. Build an entirely custom frontend via section 14 if the
component's supported visual contract is insufficient.

## 16. Operation, troubleshooting and validation

Keep the server terminal visible during startup. Use `/v1/health` from another terminal
to confirm readiness/configuration; it does not test Wikipedia availability. Ctrl+C stops
the process after active work drains. Restart with the same explicit arguments; relative
config paths and `--chat-root .` require the intended working directory.

### Common problems

| Symptom | Check/fix |
|---|---|
| `.venv\Scripts\python.exe` not found | Run `py -3.13 -m venv .venv` in the source root; confirm Python 3.13 is installed. A `.cache` review environment is not the normal `.venv`. |
| PyPI/setuptools timeout | Retry with section 4's `--timeout 120 --retries 5`; preserve the chosen extras and CPU-wheel options. |
| No llama-cpp-python wheel / compiler errors | Check Python version/platform against available CPU wheels. Binary-only installation deliberately fails instead of compiling; use the runtime's documented toolchain instructions only if choosing a source build. |
| Invalid Windows TOML path | Use forward slashes, single quotes or doubled backslashes; section 5 shows each. |
| TOML rejects a file produced by PowerShell | Check for Windows PowerShell 5.1's UTF-8 BOM. Copy/edit examples and save without BOM. |
| Model file not found | Confirm actual file/extension and path relative to the model TOML. `--model` uses the shell directory instead. |
| `context_limit` or truncated answer | Context includes template/identity/history/facts/evidence and output reservation. Shorten the turn or adjust supported model settings, then restart; memory/resource costs change. |
| Missing retrieval index / startup fails | Build the index before pointing the API at it. Index and conversation DB must differ; do not create an empty file as a substitute. |
| Unknown `retrieval_enabled` / `retrieval_root` | Remove invented keys; use `retrieval_index_path`, optional allowance/default, in API TOML. |
| `retrieval_enabled:false` | API has no opened index. Confirm you passed `--api-config api.local.toml`; files are not discovered automatically. |
| Reach checkbox missing | Health has no configured provider, health failed, or you connected to another server. Installing the extra alone does not enable Reach. |
| Reach unavailable | Inspect structured reason (TLS, timeout, busy, HTTP/provider error). Install the Reach extra for OS-native verified TLS; do not disable verification. Local chat remains available. |
| Port already in use | Stop the old process or change API `port`; open the matching URL and adjust an independent frontend's API base. |
| Browser 404 / wrong API port | Use one-server `/chat/` for the demo. An independently served frontend needs an API destination, not its static server origin. |
| API 401 / origin denied | Supply the server's token and allow the exact host-page origin. `localhost` differs from `127.0.0.1`; no `file://`. |
| Changes seem ignored | Stop the stale server, verify the venv/source/config paths and restart. Editable installation does not reload running code. |
| `<think>` appears / no final answer | Check compatible Qwen3 template settings and current decoder code; literal answer/user tags are not reasoning. A reasoning-only generation fails rather than saving hidden text. Do not strip arbitrary user content in the UI. |
| Current world facts wrong with Reach off | The model's knowledge can be stale. The clock supplies server time, not current officeholders or other external facts. |
| Unsupported answer despite no supplied evidence | Inspect receipts; generated confidence cannot establish evidence. `not_supplied` can be correct infrastructure behavior even when the model invents an answer. |
| Wrong answer despite `supplied` | Supply is not verification. Check whether material is answer-bearing and whether the model misused it; source titles/links alone do not establish correctness. |
| Follow-up ID fails after restart | Ephemeral IDs are lost. Persistent IDs must be saved manually; deleted/unknown IDs are not silently recreated. |

Source receipts and tool metadata are deterministic infrastructure records. No amount of
confident model wording proves retrieval happened. Conversely, an incorrect answer does not
alone prove acquisition failed. Full source/packet inspection is needed to distinguish missing
answer-bearing material from generation error; public WEB receipts intentionally omit text.
Model memory, identity and answer quality are useful manual observations, not guarantees.

### Final smoke checklist

Use features only after configuring them. These are ordinary setup checks, not a new
evaluation or a reason to run preserved historical holdouts.

- [ ] **Standalone:** `/chat/` loads from the API process, with no asset 404s or second server.
- [ ] **Identity:** ask `Who are you?`; expect Dwindy, with a generic local-language-model backend description.
- [ ] **Conversation:** send `Remember the number 418 for this conversation.`, then ask for it in the same conversation; inspect the reused ID.
- [ ] **Calculator:** send `924 * 17`; inspect calculator metadata for `15708` separately from prose.
- [ ] **Clock:** ask `What's the current year?`; inspect the current server-clock capability value.
- [ ] **Reasoning:** ordinary answers show no recognized leading reasoning channel; literal user text remains intact.
- [ ] **Reach:** with provider enabled, use the deliberate section 14 request; inspect attempted query, reason, actual supplied IDs and source metadata. Failure falls back locally; sources do not certify prose.
- [ ] **Documents:** `/v1/retrieve` finds the Amber passage; chat `retrieval:true` has actual-supply metadata if it fits the budget.
- [ ] **Reset:** New conversation removes ephemeral context; on persistent servers, explicit deletion removes saved turns while New preserves them.
- [ ] **Persistence, if enabled:** save an ID, restart and resume it; do not expect old transcript messages to reload in the browser.
- [ ] **Embedded modal:** open/close the launcher, chat, check allowed origin and confirm host styling does not break controls.
- [ ] **Custom API:** non-streaming request and same-ID follow-up succeed; a streaming client requires `completed` and handles errors/cancellation.
- [ ] **Stop/restart:** Ctrl+C exits cleanly; the same launch/config paths work again.

For project development rather than normal installation, the existing model-free checks are:

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e '.[api,api-test,project,reach]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests
$browser = Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe tests\browser_checks.py --browser $browser
```

The browser command uses an already installed Chromium executable; adjust that path for
your installation. These checks do not download models or run the sealed experimental
holdouts. Historical validation reports remain records of their original tested conditions.
