# Dwindy

A small, local-first, CPU-first conversational runtime. **V0.1 implements Milestone 1:**
ephemeral terminal chat with a user-supplied GGUF and a 30-case baseline evaluation.
The [project proposal](docs/PROJECT_PROPOSAL.md) is the specification;
[architecture](docs/ARCHITECTURE.md) describes what M1 actually implements.

There is no HTTP API, browser client, persistent chat, retrieval, tool execution, or web access
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

## Tests and evaluation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Tests use fake runtimes; no model or network is required. To test the source without
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
| NumPy (runtime transitive) | Runtime arrays and native inference integration. |
| Jinja2 and MarkupSafe (runtime transitive) | Runtime chat-template rendering and its string support. |
| typing-extensions (runtime transitive) | Runtime typing compatibility. |
| diskcache (runtime transitive) | Upstream runtime dependency; Dwindy does not enable a disk cache. |

Configuration, terminal interaction, tests, JSONL, hashing, and timing use Python's standard
library. Installed during initial validation: llama-cpp-python 0.3.35, NumPy 2.5.3,
Jinja2 3.1.6, MarkupSafe 3.0.3, typing-extensions 4.16.0, diskcache 5.6.3, psutil 7.2.2.
These are an observed environment, not a cross-platform lockfile.

The first real-model baseline used Qwen3-1.7B Q4_K_M on an i3-1215U Windows 11 machine
with 7.7 GB usable RAM. All 30 cases executed, but default thinking consumed output budgets.
See the evaluation README for raw-stream metric interpretation and the template-kwargs
correction. These measurements apply to that machine and configuration, not every 8 GB PC.
