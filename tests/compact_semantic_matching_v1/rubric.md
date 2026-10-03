# Label rules, metrics and conjunctive gates

## Gold judgment calls

Relevance is usefulness for the user's actual local-information request, including
entity, procedure, scope and exact identifier. A source contradicting a user's
premise can still be relevant; absence of a requested fact is not falsity. Merely
topical prose about another entity/procedure/scope is not authorized context for
that question. These are authored evaluation judgments, not an implemented runtime
answerability classifier. Any high-similarity wrong material is a counted failure.

Each positive has an exact relevance span and a smaller answer-bearing span.
They may be covered by the same chunk, but the evaluator must not conflate them.
Finding a value string in the wrong source does not earn credit. Hits require full
span containment, exact original text, matching source/document IDs. Relevance
does not imply verified correctness; these synthetic sources define a test world.
Gold data never enters encoder inputs, ranking, admission or public presentation.

Negative conversational, transformation, creative-writing and ordinary-knowledge
requests must not acquire/supply local material simply because its terminology
overlaps. Wrong-entity/procedure/scope/identifier requests have no permitted target
answer in the split-local corpus. Do not replace a failed case after seeing output.
Record nongold supplied entries in positives too, not only binary negative errors.

Fluent human review of all 48 Filipino/Taglish positives and the quoted-text
Filipino negative control is mandatory before freeze.
Cross-language gold labels concern information retrieval, not a claimed translation
capability of Dwindy or Qwen. No language-specific repairs or lowered language gates.

## Required independent observations

1. Acquisition: actual versus diagnostic-only search, permitted corpus, candidate
   entry identities/order, relevance recall@12 and @3, answer Hit@1/Hit@3/MRR@3.
2. Admission: existing baseline usefulness invocation/bypass, semantic per-entry
   scores/threshold outcomes in audit only, admitted relevance and answer coverage.
3. Final supply: original entries actually present in the Core packet, public
   source presentation, dropped turns, status and budget loss. Final relevance and
   answer-span recall use this actual packet, never retrieval success as a proxy.
4. Operational result: no_match, not_used, unavailable, budget_exhausted, supplied
   remain distinct. No verifier, network call or model generation is allowed.

Answer metrics measure located/supplied annotated material only. Report acquisition
ceilings of R and all six arm-pair changes, including pure ranking/admission/status
changes. For every collision or near-match, retain original query, candidate text,
source identities, scores and outcome; do not invent semantic explanations as facts.

## Quality gates per split, unchanged

All apply independently to each candidate. A provides paired baseline, not a
semantic candidate. R, S and H receive no automatic preference.

| Gate | Required |
| --- | ---: |
| Semantic relevant candidate recall@12, pooled 36 | at least 33/36 |
| Semantic final relevant supply, pooled 36 | at least 30/36 |
| Semantic final relevant supply per English/Filipino/Taglish | at least 9/12 each |
| Semantic final answer-span supply | at least 27/36 |
| Net semantic final relevant supply gain vs A | at least +9/36 |
| Lexical + identifier final relevant retention | 16/16; no A success lost |
| Morphology final relevant supply | at least 7/8 |
| Short local-information final relevant supply | at least 3/4 |
| Irrelevant supply on no-supply controls | 0/16 |
| New supply on historical M8 direct false-positive controls vs A | 0 |
| Deterministic mechanical probes | 32/32 |

Failed central, negative or resource gates cannot be rescued by overall recall,
historical improvements or easy categories. Do not reinterpret a false-positive
gate based on whether its baseline already fails. No holdout inference here.

## Resource gates, unchanged

| Quantity | Ceiling |
| --- | ---: |
| Additional compressed dependency closure | 50 MiB |
| Additional installed dependency closure | 150 MiB |
| Required model/tokenizer/configuration artifacts | 160 MiB |
| Loaded incremental steady RSS, encoder/tokenizer/vectors | 384 MiB |
| Peak incremental RSS | 512 MiB |
| Fresh-process initialization/import/load/validation | 4 s |
| First query after initialization | 250 ms |
| Warm query encoding p95 | 100 ms |
| Complete selection p95 | 150 ms and no more than A +125 ms |
| Build/encode/write/validate 10,000 chunks | 300 s |
| Additional semantic index at 10,000 chunks | 32 MiB |

Five isolated trials on reference i3-1215U/8 GiB/Windows/Python 3.13. No network or
generation. Report complete latency components, startup and first query separately,
raw samples, total and incremental RSS, peak allocation, build/storage footprint.
Dependency closure is compared with clean base Dwindy, even if a package happens
to be installed on the reference machine. Required artifacts include tokenizer,
configuration and licenses; no uncounted model caches or duplicated vector copies.
`performance.json` fixes statistic definitions, threads, queries, seeds and costs.

## Selection and stopping

The predeclared global threshold grid is the only admission tuning dimension.
No question/language rule, synonym table, model swap, cue repair or gate adjustment
after outputs. Preserve every threshold/profile result, including failed trials.
Select the highest threshold passing all quality gates per profile; then require
all resource/mechanical/historical-control gates. Prefer the smallest eligible
footprint; break ties by selection p95, then semantic final-answer count.
If none passes, stop the line. If one passes, report and seek review before freezing
the implementation or authorizing the untouched holdout. No automatic holdout run.
