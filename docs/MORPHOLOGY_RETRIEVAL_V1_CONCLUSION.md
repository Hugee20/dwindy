# Morphology retrieval v1: development-stage rejection

Status: concluded and rejected at development. No production morphology behavior is
adopted, no further morphology candidate is planned, and the 48-case holdout remains
sealed and unspent. This conclusion follows development results, not holdout results.
No gate, fixture, label, evaluator, split or performance protocol was changed.

The frozen evaluation remains byte-for-byte unchanged under SHA-256:

`6c1b8a9e252a55a878987082dc0f0e599ac8175486819d6b2697a988072d2bca`

Its README records the state at freeze, before execution. This separate conclusion
records the subsequent development disposition without rewriting that historical state.
The complete report, raw observations, evaluator results, timing trials and execution
scripts are archived in [the development record](../tests/morphology_retrieval_v1_results/README.md).

## What the experiment established

- Porter retrieval recovered all 12 fresh morphological targets in both B and C.
- Arm B's existing exact-word usefulness check eliminated all 12 retrieval gains:
  the targets appeared in candidates but none reached final context supply.
- Arm C's SQLite-derived Porter usefulness coverage recovered all 12 through final
  context supply. Equivalent normalization at both lexical stages mattered.
- Neither B nor C satisfied every frozen development gate. Improvement in positive
  recall is not adoption when negative controls or resource gates fail.
- The two irrelevant supplies out of 18 controls pre-existed in A and occurred
  unchanged in B/C. They were not introduced by Porter. The absolute zero-supply
  gate nevertheless remains failed; it was not reinterpreted as no regression.
- Synonym/paraphrase recall remained 0/6 and Filipino/Taglish remained 3/6 in every
  arm. Morphology did not improve those capabilities. Taglish matches with English
  anchors do not establish multilingual semantic matching.
- Historical ranking effects were mixed: M6 Hit@1 improved, M7 Hit@1 declined,
  and C fixed one M8 context-selection miss. Historical cases remain diagnostic
  apart from the explicitly frozen no-new-M8-false-supply gate, which both passed.

## Gates and resources

| Development result | A | B | C |
|---|---:|---:|---:|
| Morphological relevance candidate@12 | 0/12 | 12/12 | 12/12 |
| Morphological relevance top-three | 0/12 | 12/12 | 12/12 |
| Morphological final supplied relevance | 0/12 | 0/12 | 12/12 |
| Exact/identifier final retention | 6/6 | 6/6 | 6/6 |
| Irrelevant supply on controls | 2/18 | 2/18 | 2/18 |
| Warm complete-selection p95, ms | 28.069 | 31.253 | 33.986 |

B failed morphological final recall, net-gain, zero-irrelevant-supply and absolute
latency gates. C failed zero-irrelevant-supply and absolute latency gates. Both
passed exact retention/no-loss, historical false-positive, mechanical, relative
latency, build-time, index-size and incremental-RSS gates. The absolute warm p95
limit remains 25 ms even though A also exceeded it. No candidate was frozen for
holdout and no simpler-arm tie-break was applicable.

Performance used the frozen 1,000-document workload, five isolated trials per arm
and 200 warm queries per trial. No samples or trials were removed. Median builds
were approximately 0.434 s for every arm. Index sizes were 16,084,992 bytes for A
and 15,622,144 bytes for B/C. Median incremental RSS was 4.742/4.758/4.840 MiB.
All 15 Windows handle-close/rename/delete and temporary-folder checks passed.
First-query measurements followed indexing with a warm filesystem cache and are
not cold-disk measurements. These are model-free CPU measurements, not Qwen TTFT.
The frozen packet-accounting stub is not the actual Qwen tokenizer.

## Preservation and production boundary

The development record preserves all 144 fresh arm/case observations, every
A-to-B/A-to-C/B-to-C selection and ranking change, original-token/stem collision
traces, the 112-case spent M6-M8 diagnostic panel, all 15 performance trials, and
their original hashes. The original development report and scripts are archived
without editing or recomputing results. See the record README for hash validation
and the execution scripts' original working-directory assumptions.

No production code, FTS tokenizer, usefulness logic, query terms, thresholds,
stopwords, ranking, evidence limits, API or public behavior changed. No dependency
was installed. No real-model inference or network call was performed. Original
M11/Foundation holdouts remain sealed/unspent; Reach/H2 remains deferred and
unchanged. The historical M1 baseline was not rerun or altered.

The standalone checkpoint contains only this experiment's frozen evaluation,
fixture-validation harness, preserved development results/conclusion and Git
byte-preservation attributes. No semantic-matching implementation or evaluation
is included. A separate semantic-matching planning phase may begin only after
this checkpoint is reviewed and committed; it must not reinterpret this rejection.
