# Dwindy architecture through M2

Status: M1 runtime and template-kwargs correction, plus the M2 Core extraction.
The project proposal remains the specification. This document records implemented decisions.

## Execution and ownership

One Python process contains the terminal client and a CPU-only llama.cpp runtime accessed
through llama-cpp-python. No listener, service process, database, or outbound-network client
is created. Dependencies and model files are installed/supplied separately from execution.

`core.py` owns an in-memory list of completed user/assistant turns for each `DwindyCore`.
It selects recent complete turns within context, reserving `max_tokens` for generation.
It keeps a configured system message, rejects a current request that cannot fit, and commits
history only after successful backend exhaustion, stream cleanup, and a nonempty completed
answer. Nonempty output-limit responses are retained, preserving M1 behavior. Failed or
cancelled requests do not alter retained history, even when candidate preparation trimmed
old turns. No transcript is persisted.

`__main__.py` contains application wiring and terminal rendering. `main()` loads configuration,
constructs the model backend, gives Core its generation options and system prompt, and closes
the backend on exit. The terminal receives Core; it handles input, slash commands, rendering,
and interruption. `/reset` calls Core's reset operation. No model messages, token budgeting,
history storage, or response-commit decisions remain in terminal rendering.

`config.py` reads explicitly selected TOML using `tomllib`, validates settings, and resolves
local model paths. CLI model paths override the file setting. No automatic config search or
environment-based runtime settings are implemented. CPU execution is fixed, not a toggle.

## Core boundary and lifecycle

`DwindyCore(backend, *, options, system_prompt="")` represents one ephemeral conversation.
Its public operations are synchronous `chat(user_text)` and `reset()`. It borrows a
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
serialize their calls. There is no registry, session addressing, or concurrency scheduling.
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

## Evaluation and validation

`tests/eval/core_v0.jsonl` holds 30 synthetic cases across six categories. The explicit
runner evaluates each independently, without importing terminal history. It writes answers,
case rubrics, execution failures, settings, hashes, machine information, and measurements
only to a user-selected new output file. Human quality fields begin unscored.

The frozen M1 runner continues calling the backend directly, bypassing Core. M2 tests cover
Core state ownership, trimming and rollback, stream cleanup, overlap rejection, backend
ownership, and terminal behavior. Historical evaluation artifacts and rubrics are unchanged.

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
