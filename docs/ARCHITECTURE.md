# M1 architecture

Status: V0.1 implementation with an M1 template-kwargs compatibility correction.
The project proposal remains the specification. This document records M1 decisions only.

## Execution and ownership

One Python process contains the terminal client and a CPU-only llama.cpp runtime accessed
through llama-cpp-python. No listener, service process, database, or outbound-network client
is created. Dependencies and model files are installed/supplied separately from execution.

`__main__.py` owns terminal I/O and an in-memory list of completed user/assistant turns.
It selects recent complete turns within context, reserving `max_tokens` for generation.
It keeps a configured system message, rejects a current request that cannot fit, and commits
history only after a successful, nonempty completion. Failed/interrupted requests do not
alter retained history. `/reset` clears that list. No transcript is persisted.

`config.py` reads explicitly selected TOML using `tomllib`, validates settings, and resolves
local model paths. CLI model paths override the file setting. No automatic config search or
environment-based runtime settings are implemented. CPU execution is fixed, not a toggle.

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
