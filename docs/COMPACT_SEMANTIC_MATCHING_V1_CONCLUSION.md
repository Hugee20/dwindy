# Compact semantic matching v1: bounded development conclusion

2026-10-03. **Do not adopt the tested automatic semantic-selection candidate.**
Continue with existing lexical retrieval for v1. No production code or dependency
declaration changed; no follow-up semantic candidate or holdout run is authorized.
This decision rejects an experiment, not Dwindy v1. Failed experimental gates do
not create new product requirements.

## Freeze and scope

`tests/compact_semantic_matching_v1/FREEZE.json` SHA-256:
`8b61db931e3382e47edb1f1a36a9c1eb17262ebd971f829b970ec1ac4f95138a`.
Exactly the four human-approved corrections were applied before freeze. All 49
required language-review items were approved. Language-fixture work is finished.
The suite has 160 cases, split 80/80, and 144 permitted source documents per split.
The development half has 64 positive cases and 16 no-supply controls. Its positive
categories are English semantic/Filipino/Taglish (12 each), lexical/identifier/
morphology (8 each), and short local requests (4).

Hypothesis, unchanged:

> A small local encoder improves Dwindy's discovery and admission of relevant information while preserving source identity, compact evidence, offline operation and bounded resource use.

Only development retrieval was run. The semantic holdout and the historical M11,
Foundation and morphology holdouts remain sealed/unspent. Reach/H2 was untouched.
The frozen fixtures, labels, split, rubric, gates and evaluator were not changed
after outputs. Original model/evaluation alternatives remain historical proposals;
they are not silently substituted or treated as tested.

## Smallest practical stack tested

Model2Vec 0.9.0 with the MIT-licensed `minishlab/potion-base-8M`, revision
`bf8b056651a2c21b8d2565580b8569da283cab23`, native normalized 256-dimensional
static embeddings. It is the small English static-encoder option in the frozen
shortlist, not an English transformer or a claimed multilingual encoder. Publisher
references: [Model2Vec](https://github.com/MinishLab/model2vec),
[model card](https://huggingface.co/minishlab/potion-base-8M),
[pinned package](https://pypi.org/project/model2vec/0.9.0/).

Packages and pinned public model artifacts were acquired explicitly in an ignored,
isolated Python 3.13 environment under `.cache/compact_semantic_matching_v1/`.
Base Dwindy was not changed. Evaluation then blocked network connections/DNS,
loaded only local SHA-verified artifacts and encoded only development sources.
Network attempts: **0**. Qwen/model-generation calls: **0**. No vector database,
orchestration framework, hand-written stemmer or language-specific repair was added.

A uses unchanged FTS and usefulness; R reorders/adopts only FTS candidates; S
searches the permitted corpus with exact cosine; H combines FTS and dense top-12
with fixed RRF 60. Every arm uses existing context classifications, directed-query
bypass, deduplication, native history and Core packet preparation. Candidate limit
12, actual supplied limit 3, evidence allowance 768, output reserve 256. Accounting
uses the explicitly frozen model-free oracle, **not the Qwen tokenizer**. Original
source text/IDs survive acquisition, admission and actual supply. Similarity stays
in the internal audit, outside the evaluation's public source projection.

## Development results

At threshold 0.35, the predeclared setting with greatest final recall:

| Observation | A lexical | R rerank | S dense | H hybrid |
| --- | ---: | ---: | ---: | ---: |
| Relevant candidates @12, all positives /64 | 55 | 55 | 52 | 53 |
| Relevant candidates @3, all positives /64 | 51 | 49 | 48 | 51 |
| Admitted relevance, all positives /64 | 26 | 49 | 48 | 49 |
| Actual final relevance, all positives /64 | 26 | 46 | 46 | 48 |
| Actual final answer spans, all positives /64 | 26 | 46 | 46 | 48 |
| Candidate answer Hit@1 /64 | 35 | 35 | 35 | 39 |
| Candidate answer Hit@3 /64 | 51 | 49 | 48 | 51 |
| Candidate answer MRR@3 | .6615 | .6563 | .6458 | .6979 |
| Semantic candidate recall @12 /36 | 27 | 27 | 24 | 25 |
| Semantic final relevance and answer spans /36 | 6 | 18 | 18 | 20 |
| English semantic final /12 | 0 | 9 | 9 | 9 |
| Filipino final /12 | 6 | 6 | 6 | 6 |
| Taglish final /12 | 0 | 3 | 3 | 5 |
| Lexical + identifier final /16 | 16 | 16 | 16 | 16 |
| Morphology final /8 | 1 | 8 | 8 | 8 |
| Short local final /4 | 3 | 4 | 4 | 4 |
| Negative cases receiving evidence /16 | 4 | 6 | 6 | 6 |
| Nongold entries supplied on positives | 51 | 114 | 119 | 117 |

No baseline positive success was lost at 0.35. R/S gained 20 positive successes;
H gained 22. These are information-flow gains, not generated-answer correctness.
Nongold entry counts describe supplied material outside the annotated relevance
spans; they are recorded separately from binary negative-case supply failures.

All seven frozen thresholds were evaluated, without further tuning:

| Threshold | R semantic final /36 | S /36 | H /36 | R/S/H negative supply /16 |
| --- | ---: | ---: | ---: | ---: |
| .35 | 18 | 18 | 20 | 6 |
| .45 | 14 | 14 | 14 | 5 |
| .55 | 6 | 6 | 6 | 1 |
| .65 | 6 | 6 | 6 | 1 |
| .75 | 2 | 2 | 2 | 1 |
| .85 | 0 | 0 | 0 | 1 |
| .95 | 0 | 0 | 0 | 1 |

At .35 each candidate passes net semantic gain, lexical/identifier retention,
morphology and short-local gates. Each fails semantic candidate recall (33/36),
final recall (30/36), per-language recall (9/12 each), final answer spans (27/36)
and zero negative supply. No threshold/profile passes every quality gate.
Those gates remain failed; overall gains do not retroactively pass them.

At .35 A supplies negative cases `dev_no_supply_01`, `_02`, `_04`, `_15`.
R/S/H supply `_01`, `_02`, `_03`, `_04`, `_11`, `_14`. New failures versus A are
wrong scope (`_03`), a text-shortening request (`_11`), and creative writing (`_14`);
the ordinary knowledge case `_15` stops receiving evidence. The identifier near
miss `_04` persists at every threshold because the existing directed-query path
bypasses usefulness/admission. This is inherited behavior, not a new semantic
failure or a reason to add an answerability classifier. Its frozen failure still
counts. Higher thresholds remove false supplies but also remove English gains.

The evidence supports a concrete precision/recall tradeoff, rather than a general
claim that all local encoders are unsuitable. The small static stack can materially
improve admission and morphology, but automatic admission admits more wrong-scope
and self-contained material. It does not establish the broader cross-language
hypothesis. No new language milestone, cue table or response-policy work follows.
Other shortlisted encoders were not installed/tested and are **not** rejected by
these results. Continuing that research is optional, not a v1 prerequisite.

## Cost measurements and limits

Full installed stack: 24 packages, 22,617,693 compressed wheel bytes and
93,837,016 installed RECORD bytes. Relative to clean base Dwindy dependency closure
(`llama-cpp-python`, diskcache, NumPy, typing-extensions, Jinja2, MarkupSafe): 20
additional packages, **9,861,945 compressed bytes (9.41 MiB)** and
**38,298,300 installed bytes (36.52 MiB)**. Optional API/project dependencies were
not credited as base. Model/tokenizer/configuration/card artifacts total
**30,927,674 bytes (29.50 MiB)**. Wheel hashes, versions and individual costs are
recorded, rather than counting only the small Model2Vec wheel.

The quality run imported/loaded/validated the encoder in **1,091.23 ms**. The
development index has 144 chunks, so its timings are descriptive diagnostics:

| Quality-run timing, ms | A | R | S | H |
| --- | ---: | ---: | ---: | ---: |
| Complete selection median | .525 | .793 | 1.119 | 1.568 |
| Complete selection p95 | 1.490 | 1.730 | 2.241 | 3.158 |
| Query encoding p95, including bypass zeroes | 0 | .535 | .409 | .518 |
| First observed selection | 1.094 | 1.662 | 2.145 | 1.320 |

These are 80 fixed-order queries per arm at .35, with no outlier removal. They
are not isolated startup trials, a cold-disk benchmark or 10,000-chunk timings.
The first observation follows corpus encoding, so it is **not** the frozen
first-query-after-initialization measurement. Full distributions/components are
in `diagnostics.json` and raw records. No development candidate view was truncated;
no development conversational unit was trimmed.

All profiles failed quality before resource eligibility. Following the frozen
stop rule, the five-trial 10,000-chunk benchmark and historical diagnostic retrieval
panel were not run. RAM, peak allocations, scale build/index costs, historical
false-positive comparison and full resource eligibility remain **unmeasured**, not
passes. The exact three disk-footprint measurements fit their individual ceilings;
that alone does not establish an acceptable complete resource profile.

## Records, validation and product impact

Outside the immutable suite:

- `tests/compact_semantic_matching_v1_run/`: acquisition and development-only runner.
- `tests/compact_semantic_matching_v1_results/dev_potion_01/`: all seven raw/scored
  profiles, all six arm-pair changes per profile, summaries, cost and acquisition
  provenance. `ARTIFACTS.json` binds these to runner/evaluator/runtime hashes.
- `tests/test_compact_semantic_runner.py`: synthetic implementation checks without
  installing the encoder into base Dwindy.

The frozen suite's 32 contract probes pass. These include acquisition/admission/
supply separation, exact source identity, budgets, history transience, model-only
bypass, operational failures and non-public similarity. Production regression
validation is reported separately; it does not turn failed recall/admission gates
into passes. No source-policy bypass, privacy leak, history mutation, generation
or production retrieval change was observed in this experiment.

The current v1 requirement is a working bounded local information pipeline, not
universal paraphrase understanding, perfect multilingual retrieval, zero model
errors, or passing every speculative experiment. Existing recall and relevance
limitations should be documented. A demonstrated exclusion leak, corrupt index,
incorrect supply receipt, broken reset/rollback or violated resource requirement
would still block release. A failed optional encoder experiment does not.

**Recommendation: stop this semantic candidate; retain lexical production behavior.
Return to ordinary integration/release checks in the existing v1-hardening scope.**
