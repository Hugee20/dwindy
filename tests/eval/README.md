# M1 baseline evaluation

The dataset contains 30 synthetic cases: five each for casual conversation, instruction
following, basic reasoning, summarization/transformation, unknown-answer behavior, and
context following. No private user conversation is used. This measures model-only behavior;
it does not implement retrieval, arithmetic tools, or any later capability.

From the repository root with Dwindy installed and a local GGUF configured:

```powershell
New-Item -ItemType Directory -Force eval-results | Out-Null
.\.venv\Scripts\python.exe tests\eval\run.py --config config.local.toml --output eval-results\baseline-01.jsonl
```

Alternatively supply `--model 'D:\Models\your-model.gguf'`. No model is chosen or downloaded.
The output parent must exist and the output file must be new. The explicit runner saves
benchmark responses, not terminal chat history. It returns nonzero on execution errors;
zero means cases ran, not that response quality passed. Interrupted/failed runs may leave
partial output: only a file ending with a summary represents a completed run.

## Review procedure

Each case provides a rubric. Review its answer against that rubric, then assign
`human_score`: **0** = incorrect/unsupported or fails the central instruction;
**1** = partly correct with omissions or minor instruction violations;
**2** = satisfies the rubric without unsupported additions.
Record `unsupported_claims` as true/false and retain reviewer notes separately in an ignored
artifact. Missing scores remain null; do not treat them as zero or automatically passing.

Report mean score and unsupported-claim rate separately for each category, together with
the number reviewed, number unscored, and execution-error count. Treat instruction following
as the instruction category's rubric results; use the context category to inspect supplied
context fidelity. Retrieval success is not applicable at M1. No calibrated confidence,
automated model judge, or pass threshold is invented. Establish the baseline before choosing
thresholds. For comparisons, use the same dataset hash, settings, and review procedure.

## Recorded measurements

- Model SHA-256 and size identify the supplied artifact without exposing its absolute path.
  Record its public model identity, origin, quantization, and license separately when selected.
- Dataset SHA-256, Dwindy/runtime versions, configured settings, and effective context size
  identify the software/input conditions. Fixed seed does not guarantee identical output
  across hardware, runtime versions, or thread settings.
- Machine OS, architecture, CPU identifier, logical CPU count, Python version, and optional
  total RAM describe the **actual measured machine**. These results do not establish the
  8 GB reference target's performance.
- `model_load_seconds` covers backend construction, including runtime import, model load,
  and formatter creation. It excludes interpreter startup and model hashing. Hashing warms
  the filesystem cache: this is not a cold-start measurement.
- `first_text_seconds` measures request start (including template/count work) to the first
  nonempty text delta. Stream buffering can make this differ from raw first-token latency.
- `elapsed_seconds` includes input preparation and complete response consumption.
- `prompt_tokens` includes the rendered template. `text_tokens` is retokenized visible
  output, excluding hidden/stop tokens; it is not an exact sampled-token count.
- `visible_text_tokens_per_second` divides that text-token count by total request time,
  including prefill. Do not compare it directly with decode-only tokens/second reports.
- `sampled_peak_process_rss_bytes` covers loading and all requests at 50 ms intervals when
  psutil is installed. It includes native allocations, may miss short peaks, is not total
  system memory, and does not isolate core overhead from model memory. Without psutil it is
  null. There is no claim of exact peak memory measurement.

There is no hidden warm-up; the first case is the first generation after loading. The backend
resets logical inference state between cases. Repeat full runs with new output filenames and
record power mode, background workload, and any custom runtime build separately. To verify
offline behavior with a real model, repeat terminal chat and evaluation with networking
disabled. A successful ordinary run alone does not establish OS-level network isolation.

## Raw-stream timing and the original Qwen3 baseline

The original Qwen3-1.7B Q4_K_M baseline used the embedded template defaults. All 30 cases
ran without execution errors, but all 30 responses contained an opening `<think>` tag,
only 14 contained a closing tag, and 20 ended at the output-token limit. Execution success
is not a claim that a complete final answer was delivered.

`first_text_seconds` starts at the first nonempty **raw streamed text**, including a thinking
tag or reasoning text. It does not identify the first final-answer text. Retokenized visible
throughput includes any generated reasoning and tags, over total request time. Thus the
original approximately 0.95 s mean first-text time and 6.52 visible tokens/s describe that
raw stream. Keep the original artifact unchanged; do not strip or retroactively rescore its
text to make these timing figures appear to measure final answers.

For an embedded template that supports it, set `[chat_template_kwargs]` with
`enable_thinking = false` at the end of the local TOML file. On the tested Qwen3 template,
this inserts an empty completed thinking block into the input, selecting non-thinking
behavior before generation. No generated text is removed. This behavior is defined by
that template, not by a model-name branch in Dwindy. Other templates may ignore the variable.
The effective mapping is saved as `settings.chat_template_kwargs`; older baselines without
that field used no supplied template kwargs.

Rerun with a new output filename, holding model, dataset, sampling, context, and output
budget fixed. Compare raw reasoning-tag occurrence, token-limit finishes, per-case answer
quality, and timing. A change in mode can affect accuracy as well as latency. Raw-stream
metric definitions remain identical in both runs.

### Correction validation (2026-10-01)

A second run used the same GGUF hash, dataset hash, and existing settings, adding only
`chat_template_kwargs = {enable_thinking = false}`. It completed all 30 cases without
execution errors. No generated opening or closing thinking tags appeared. Token-limit
finishes fell from 20 to 3: `instruction_5`, `reasoning_3`, and `reasoning_5`.
The original baseline's SHA-256 remained
`1effc84bcaf1d7354ca90053201ed593300f74ddac828a4df2fc414c4514a8e2`.

The new run measured 8.13 s backend load, 0.95 s mean first raw text, 5.35 mean visible
text tokens/s, and 1,323,036,672 bytes sampled peak process RSS. These are individual-run
observations, not evidence of an across-the-board speed or memory improvement. Load time
and throughput differed from the original run; no controlled explanation is established.

Qualitative inspection still found Markdown fences around JSON-only output, repetition in
the sorting case, and verbose explanations that hit the output limit. Absence of thinking
tags does not imply concise output or perfect instruction following. The full human rubric
remains unscored. Raw responses were preserved without filtering, and no sampling parameters
or dataset cases were changed to improve this comparison.
