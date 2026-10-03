# Frozen acceptance rubric

This is a separate narrower retrieval/morphology hypothesis, not a semantic
response-policy adoption. Gold is authored before retrieval outputs. Known M6-M8
patterns informed construction; historical benchmarks remain unchanged.

## Gold and judgments

Offsets are Unicode codepoints in exact LF-normalized UTF-8 source. A relevance
hit contains a full annotated relevant span from a permitted source. An answer
hit contains a full answer span. Overview spans in morphology documents can be
relevant while containing no answer. Identical statements in other permitted
same-split sources are valid alternative gold; the original file gets no priority.
Gold spans are alternative sources, not multiple independent required facts.
Unknown rationale, absence or arbitrary generated factual accuracy is not scored.

All fresh acceptance positives ask for explicitly stated local information. All
18 negative controls per split ask an unrelated or self-contained task, rather
than merely an answer missing from otherwise related material. Morphological
collision meanings are fixture-author judgments; tokens/stems are logged so
those judgments are reviewable. Related-but-unanswerable material is not
universally classified as irrelevant. Origin labels convey no truth/priority.

No-answer rows are excluded from positive-recall denominators. Diagnostic-only
synonym and Filipino/Taglish rows are excluded from all fresh adoption credit.
They still appear individually, by category, and in every pairwise change report.
Unnecessary supplied local context for a negative is false supply regardless of
whether the language model might ignore it. This evaluation generates no answers.

## Unchanged proposed gates (per 48-case split)

* Morphology candidate relevant recall@12: >=11/12.
* Morphology relevant recall@3: >=10/12.
* Morphology final supplied relevant recall: >=10/12.
* Net additional final relevant morphology selections over A: >=3/12.
  Report gains and losses separately; losses cannot be hidden in the net count.
* Exact/identifier final relevant selection: 6/6; no A exact success lost.
* Irrelevant supply on collision/accidental/ordinary controls: 0/18.
* Historical M8 direct/acceptable-control panel: no new false supply over paired
  A. Existing failures need not be repaired and are never acceptance positives.
* All 24 structural/mechanical probes pass, with unchanged text, ordering, source
  spans, query bounds, duplicate suppression, generation exclusion and lifecycle.
* Warm full-selection p95 <=25 ms AND <=1.25*A p95 +2 ms.
* Build time <=1.20*A; index bytes <=1.20*A.
* Incremental isolated RSS no more than 8 MiB above A.

Hit@1, answer Hit@3/MRR@3/final answer recall, candidate ranking changes, coverage,
Unicode normalization differences and every individual failure are reported but
have no invented additional gates. A selected arm must pass **all** applicable
fresh, historical, mechanical and performance gates. Prefer B over C if both pass;
otherwise select C only if justified by its complete results. Neither eligible:
reject morphology adoption, no automatic stemmer/dependency/semantic expansion.

Development first; implementation and allowed decisions frozen before requesting
holdout authorization. Holdout runs once only after explicit approval, against
paired A with identical corpus/settings. No tuning after holdout. No baseline
inference, no verifier/network/model call and no Reach/H2 change.

## Timing and resource judgments

Use the independent scale workload, five trials per arm and 200 warm queries per
trial. The same deterministic query permutation is paired across arms each trial.
Nearest-rank p95 = sorted[ceil(.95*N)-1], not interpolated. Pool 1,000 warm
selection measurements per arm; use median of five build times/index sizes/peak
incremental RSS values for relative resource gates. Report every trial and maxima.
No trials/outliers removed. Errors are failures, not discarded samples. The
reference machine must be idle; environmental interruption invalidates the whole
paired trial before comparing arm results, retained with the reason.

Measure search, query construction/normalization, usefulness and Core packet
construction separately and full selection as a whole. Audit-only extra stemming,
candidate probes for bypasses, JSON serialization and IPC are outside timing; C's
normalization needed for actual admission is inside. Performance execution must
avoid the A/B post-hoc audit cost; no timed baseline is artificially burdened by
normalization it does not use. Reference timing is model-free, not Qwen TTFT.

Include fresh connection/schema-validation/normalizer setup, first query, and
steady-state timings separately. First query after indexing has a warm OS cache;
never describe it as cold-disk latency. No OS cache flushing or reboot is required.
Build includes ingestion/chunking/insertion/commit, including tokenizer work;
fixture source generation is outside. Build each arm directly with its tokenizer,
not unicode61 followed by a second rebuild. File size is after closing handles.
Isolated process RSS sampled every 10 ms from the same pre-index baseline, using
the already-existing optional evaluation psutil tooling; install nothing for this
phase. Peak includes model-free construction/index/query work, with any missed
short-lived peaks disclosed. No model is loaded. Windows rename/delete checks
follow explicit handle closure.
