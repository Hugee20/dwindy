# M8 validation report

M8 adds a deterministic context-selection policy. When a retrieval or project index is
configured, the policy decides per turn whether local evidence deserves model context.

- **No model call:** ordinary generation remains the only model call per turn.
- **No new dependency** and no change to M6 ranking or chunking.
- **No change** to M7 Project Awareness behavior or to any historical evaluation artifact.
- **No M9 work** was started.

## Frozen evaluation

The evaluation was frozen before any policy code existed: `tests/context/FREEZE.json` SHA-256
`9f5a67d31fc4d0a4f90845c86e18806cc6c05c7458c3534935323becb14e5f82`. It holds 56 cases in 14
categories with four cases each, split 28 development and 28 holdout (two of each category per
split). The Filipino/Taglish category is reported only. The frozen files are unchanged.

**Process:**
1. The policy was written and run once against the development split. All 26 English
   development cases were correct with the initial thresholds, so **no threshold or cue was
   tuned**.
2. Two cue edits were made before that first evaluation run, on design grounds:
   - bare "earlier" and "so far" were replaced by unambiguous history phrases, because they
     occur in project questions;
   - the source-path pattern was tightened so "TCP/IP", "and/or" and "node.js" no longer count.
3. The policy (`context_policy.py` SHA-256 `670deade…35dcb5`) was then frozen, and the holdout
   was scored once.
4. No change followed the holdout.

The same person wrote both the cases and the policy, which is a limitation of this evaluation.

| Group | English cases | Accuracy | Missed context | Strict false supply | General false supply | Overlap false supply | Honest path |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 26 | 100% | 0 | 0 | 0 | 0 | 2/2 |
| Holdout | 26 | 92.3% | 1 | 0 | 0 | 1 | 2/2 |
| **All 56** | 52 | **96.2%** | **1/16** | **0/16** | **0/8** | 1/4 | **4/4** |

Other figures:

- **Attempt recall:** 1.00.
- **Attempt precision:** 0.61. Searching is cheap by design.
- **Gold coverage:** 100% of correct context outcomes supplied a gold path.
- **Policy errors:** 0.

**Every frozen gate passes:**

| Gate | Threshold | Result |
| --- | --- | --- |
| Accuracy | ≥ 0.85 | 0.962 |
| Missed context | ≤ 1 | 1 |
| Strict false supply | 0 | 0 |
| General false supply | ≤ 2 | 0 |
| Honest path | ≥ 3 | 4 |
| Policy errors | 0 | 0 |
| Failure-injection rows | 10/10 | 10/10 |

**Every miss** (both English misses are in the holdout):

- **implicit_project_4**, "What do I need to cancel a reservation?": outcome direct
  (`weak_match`). The documentation says "cancellations", the question says "cancel", and there
  is no stemming. Only "reservation" of three terms matched. This is a word-form miss, reported
  rather than repaired.
- **accidental_overlap_2**, "What is the capital of France?": outcome context (`relevant_match`).
  The glossary's "Capital equipment" matched one of two content terms, reaching the 50%
  threshold. A known weakness of coverage on very short questions.
- **multilingual_1–4** (reported only): all four went to ordinary chat (`no_candidates` or
  `weak_match`). The English cue table never fires on Filipino, Filipino function words count as
  query terms and dilute coverage, and "system/ito" has no English match. Four cases support no
  multilingual claim either way. They mark a limitation worth a later experiment.

Every case's outcome, reason and supplied paths are printed by `tests/context_run.py --split all`.

**Cue table:** 58 entries against the frozen cap of 60, enforced by a test.

| Category | Entries |
| --- | ---: |
| Pleasantries | 12 |
| History references | 8 |
| Creative verbs | 4 |
| Creative nouns | 6 |
| Transformation verbs | 9 |
| System determiners and nouns | 2 + 8 |
| Documentation references | 6 |
| Shape patterns (snake case, camelCase, source path) | 3 |

**Final internal thresholds:**
- `MIN_COVERAGE = 0.5`: one ordinary passage among the top three must contain at least half of
  the query's search terms.
- `TOP_PASSAGES = 3`.
- Generated overview and metadata passages never count toward coverage.
- Transformation fast paths need at least three words of supplied text after a colon or line
  break.

## Failure injection (all 10 correct)

These run through the real HTTP API with `RetrievalIndex.search` raising the stated error. The
outcome is judged from what the model actually received.

| Row | Request | Result |
| --- | --- | --- |
| 1–4 | Project-directed `auto` (2 unavailable, 2 busy) | HTTP 200, constrained fallback, status `unavailable`, reason `retrieval_unavailable` / `retrieval_busy` |
| 5–6 | Opportunistic `auto` | HTTP 200, ordinary chat, status `unavailable` with the true reason |
| 7 | "Hello!" | Search never called; `not_used` / `conversational` |
| 8–9 | `on` | 503 `retrieval_unavailable` / `retrieval_busy` |
| 10 | `/v1/retrieve` | 503 `retrieval_busy` |

The same ten rows also pass under the rejected-fallback expectations: rows 1–4 then return a
503. Separately, a busy shared storage worker is treated as `retrieval_busy`.

## Benchmark reproduction

Both frozen benchmarks reproduce exactly, and their freeze hashes are unchanged.

| Benchmark | Hit@1 | Hit@3 | MRR |
| --- | ---: | ---: | ---: |
| M6, overall | 0.75 | 0.95 | 0.850 |
| M6, development | 0.80 | 1.00 | 0.900 |
| M6, holdout | 0.70 | 0.90 | 0.800 |
| M7, overall | 0.818 | 0.955 | 0.886 |

A test proves `match_query` produces identical expressions to the M6/M7 implementation for
every M6, M7 and M8 query. The M1 dataset and both historical Qwen result files are untouched.

## Regression tests

**188 Python tests pass:** the 160 from M1–M7 plus 28 for M8.

| Module | Tests | Covers |
| --- | ---: | --- |
| `test_context_fixtures` | 5 | Frozen hashes, composition, labels, the evaluator, gold paths in a real index |
| `test_context_policy` | 15 | The policy itself, Core fallbacks, the terminal |
| `test_api_context` | 8 | Default and migration, explicit values, no-index behavior, configuration, startup notice, the frozen failure table, busy storage, persistence |

`pip check` is clean.

**41 browser tests** pass in Chrome 154.0.8037.93 and Edge 154.0.4258.37: the M7 40 plus one for
the `auto` default, the opt-out and the status text. The end-to-end UI checks pass in both.

Three existing assertions changed, each an intended, documented compatibility change:

| Test | Change |
| --- | --- |
| `test_api_project` | M6-index health now includes `retrieval_default` |
| `test_api_project`, `test_api_retrieval` | The "old response shape" checks now send an explicit `retrieval: false`, the M8 opt-out |
| `test_api_retrieval` | The OpenAPI status enum gained `not_used` and `unavailable` |

One web assertion also changed: a checked box now sends `"auto"`.

These are byte-identical to M7, as tests show: no index, `false`, `true` (same M6 metadata shape),
and an omitted field with `retrieval_default = "off"`.

## Performance

Measured on the reference machine (i3-1215U, Windows 11, Python 3.13.0, SQLite 3.45.3) with
`tests/context_perf.py`. Each index ran in a fresh process with a warm OS cache.

| Measurement | Fixture (20 chunks) | M7 scale (30,278 chunks) | Target |
| --- | ---: | ---: | ---: |
| `auto` with search, p95 | 0.30 ms | 22.4 ms | ≤ 25 / ≤ 100 ms |
| Search alone, p95 | 0.12 ms | 21.9 ms | — |
| Fast paths, p95 | 0.08 ms | 0.08 ms | < 1 ms |
| `off`, p95 | < 0.001 ms | < 0.001 ms | < 1 ms |
| RSS increase over 2,800+ decisions | 0.6 MiB | 1.7 MiB | ≤ 5 MiB |

The usefulness check adds about 0.5 ms over the search itself. No model calls are made, and the
tests assert at most one backend request per turn.

## Real-Qwen comparison

**Setup:** `tests/eval_context_e2e.py` ran the frozen 22-case e2e set under all four conditions,
plus the four failure cases: 92 generations. It used the unchanged Qwen3-1.7B Q4_K_M non-thinking
configuration (seed 42). Identical model input produced identical text across conditions.

**Outputs:** `results.jsonl`, `sheet.md` and `key.json` are in the ignored
`eval-results/m8-e2e-01/` directory.

**Two scorings.** `scores-assistant.json` holds the assistant's rubric scores. **They are not
blind:** conditions are recognizable from the answers, and the scorer wrote the policy. A human
reviewer then scored all 92 answers in `sheet.md` blind and opened `key.json` only afterward (see
[Human blind scoring](#human-blind-scoring)). The assistant's scores follow.

| Condition | Project correct (of 10) | Non-project correct (of 10) | Taglish (of 2) | Total (of 22) | Unsupported project claims | Unnecessary refusals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A. Oracle explicit selection | 8.5 | 10 | 0.5 | 19.0 | 1 | 0 |
| **B. Automatic** | **9.5** | **10** | 0 | **19.5** | **1** | **0** |
| C. Forced `on` | 8.5 | 5 | 0.5 | 14.0 | 1 | 5 |
| D. Off | 0 | 10 | 0 | 10.0 | 6 | 0 |

Partial answers count 0.5. No forbidden string appeared, and no document instruction was
followed.

**Median time to first visible text:**

| Condition | Non-project | Project |
| --- | ---: | ---: |
| Automatic | 0.38 s | 4.45 s |
| Off | 0.39 s | 0.33 s |
| Forced `on` | 3.44 s | — |

**Success criteria (rubric):** all five hold under these scores.

1. B ≥ D on project correctness: 9.5 vs 0.
2. B has no more unsupported claims than D: 1 vs 6.
3. B has no more unnecessary refusals than C: 0 vs 5.
4. B is within one case of A: 19.5 vs 19.0.
5. B's non-project latency is within 10% of D's: 0.38 vs 0.39 s.

**Observations:**

- **Without context the model invents project facts.** With context off it described Lantern Desk
  as "a desktop application developed by Lantern Labs" and as "a collaborative writing platform".
- **Forced retrieval damages ordinary chat.** It turned "Hello!", photosynthesis and a
  conversation recall into "The supplied local material is insufficient."
- **Automatic beat the oracle on "What does this system do?"** Search-query normalization found
  the identity passages, whereas the oracle's forced retrieval of the raw message found none. The
  oracle chooses perfectly between retrieving or not, but it does not normalize the query. So the
  fair reading is "automatic matches the oracle's selection and adds a small normalization gain",
  not "automatic is better than an oracle". Both scorings trace the difference to this case.
- **rationale_3 is partial in every condition that retrieved.** The model said no rationale was
  stated and did not accept 25, but it did not mention the actual value, 12.
- **Taglish:** forced retrieval produced a garbled answer with an invented detail.

These are one-shot observations on n = 22. They show direction, not statistical significance.
Generation was deterministic (seed 42), so every difference between conditions comes from
differences in the model's input.

### Human blind scoring

A human reviewer scored all 92 answers from `sheet.md` against the per-item criteria without
`key.json`, then opened the key to map the scores back to conditions.

| Condition | Blind score | Accuracy | Assistant's non-blind score |
| --- | ---: | ---: | ---: |
| B. Automatic | 18 / 22 | 81.8% | 19.5 |
| A. Oracle explicit selection | 17 / 22 | 77.3% | 19.0 |
| C. Forced `on` | 14 / 22 | 63.6% | 14.0 |
| D. Off | 9 / 22 | 40.9% | 10.0 |
| Failure cases | 4 / 4 | 100% | 4 / 4 |

Across all 92 answers, the reviewer marked 59 fully correct, 6 partial and 27 incorrect, for a
weighted 62 / 92. They counted 11 unsupported project claims or accepted false premises, 7 clear
unnecessary refusals and 0 followed injections. That 62 / 92 mixes all conditions and is not a
score for any one of them.

The two scorings rank the conditions the same way and agree exactly on forced `on` and the
failure cases. The blind totals are lower because the reviewer applied stricter judgments, two
of which go beyond the frozen rubric's wording:

- **`current_information_2`:** answers calling Python 3.12 the latest version "as of April 2025"
  were scored incorrect as factually stale. The rubric's `correct_if` credits "answers from
  general knowledge". The answers appeared under several conditions, including the oracle, so
  this is a generation-quality and freshness issue for M10 (Reach), not a context-selection one.
- **`rationale_3`:** answers that refused to invent a reason for `DISPLAY_LIMIT = 25` but did not
  state the actual value, 12, got half credit. The reviewer also treated them as not challenging
  the false premise.

Under the rubric's wording, the reviewer's half credit on `location_4` (answers naming
`reference.toml` rather than `config/reference.toml`) is defensible.

The reviewer reported condition totals and qualitative notes rather than per-condition counts
of unsupported claims and refusals. Those notes place the invented "Lantern Labs desktop
application" and "collaborative writing platform" answers under off, and the "supplied local
material is insufficient" replies to greetings and general questions under forced `on`. That is
consistent with success criteria 1–3, and criterion 4 holds on the blind totals: automatic 18
versus oracle 17.

Reviewer's conclusion: the results cluster as the architecture predicts:

- no context → project hallucination;
- context everywhere → irrelevant refusals;
- appropriate project context → grounded answers;
- fast paths → normal chat.

They recommend no multilingual claim.

## Constrained fallback: adopted

All four injected project-directed failures disclosed that the project information was
unavailable, and none stated a project-specific fact. The median time to first visible text was
1.46 s.

`failure_3` first stated that project information was unavailable and that it could not give
project-specific details, then added generic guidance about who usually approves reservations.
The assistant judged it compliant. **The human blind review independently confirmed this before
seeing the key:** correct, disclosed unavailability, no project-specific claim. All four failure
cases passed in both scorings, so the frozen adoption rule is satisfied and
`CONSTRAINED_FALLBACK` stays `True`. Setting it to `False` would restore the M6 503 for
project-directed failures; the tests cover that path.

## Deviations from the approved architecture

1. **Real-Qwen scoring.** The rubric called for blind human scoring. The assistant first scored
   without blinding. The required human blind scoring was then completed and agrees on the
   ranking and on the fallback adoption (see [Human blind scoring](#human-blind-scoring)).
2. **`retrieval: null` is now rejected.** The request type is `true | false | "auto"`, with
   omission meaning the server default.
3. **Busy storage worker.** A busy storage worker in `auto` is handled as `retrieval_busy`
   instead of the M6 `storage_busy` 503. This applies the approved fallback semantics to the same
   underlying condition.
4. **Test assertions.** Beyond the one planned health-assertion change, the M6/M7 "old shape"
   checks now send explicit `retrieval: false`. This is the documented migration path.

No other deviation.

## Remaining limitations

- **Lexical usefulness only.** There is no stemming, synonym handling or translation. Word-form
  misses (cancel versus cancellations) and very short questions (one of two terms matching)
  remain. Filipino/Taglish questions do not benefit; this is measured, not claimed.
- **English-only cues.** The cue table is English and deliberately small. Phrasings outside it
  rely on the usefulness check.
- **Follow-up questions.** These are searched with their own words only. There is no
  history-based query expansion.
- **Supply is not grounding.** A `relevant_match` supply is not proof of an answer, and the model
  can still misread supplied passages.
- **Freshness.** Answers can be stale until the next manual sync (unchanged from M7).
- **Small evaluation.** The set is synthetic, written by the same author as the policy, and the
  real-model comparison is n = 22, one shot.
- **UI control.** The browser checkbox remains a transitional developer control.

**M8 READY TO CLOSE.** The human blind scoring is complete and confirms the constrained-fallback
adoption. Stop here; M9 is not started.

## File inventory

**Modified:**
- `.gitattributes`, `README.md`, `api.example.toml`
- `docs/ARCHITECTURE.md`, `docs/CHAT_INTERFACES.md`, `docs/PROJECT_PROPOSAL.md`, `docs/RETRIEVAL.md`
- `src/dwindy/__main__.py`, `src/dwindy/api.py`, `src/dwindy/core.py`, `src/dwindy/evidence.py`,
  `src/dwindy/retrieval.py`, `src/dwindy/server.py`
- `tests/test_api_project.py`, `tests/test_api_retrieval.py`
- `web/api-client.js`, `web/dwindy-chat.js`, `web/tests/api-client.test.js`,
  `web/tests/dwindy-chat.test.js`

**Created:**
- `docs/CONTEXT_SELECTION.md`, `docs/M8_VALIDATION.md`
- `src/dwindy/context_policy.py`
- `tests/context/`: `FREEZE.json`, `README.md`, `cases.jsonl`, `failures.jsonl`, `e2e.jsonl`,
  `rubric.md`, `evaluate.py`, `extra/collection.toml`, `extra/events.md`, `extra/glossary.md`,
  `extra/notice.md`, `extra/weather.md`
- `tests/test_context_fixtures.py`, `tests/test_context_policy.py`, `tests/test_api_context.py`
- `tests/context_run.py`, `tests/context_perf.py`, `tests/eval_context_e2e.py`

**Not touched:** `assets/chatheads/dwindy-blush.png` (unrelated and untracked).

## Validation commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe tests/context_run.py --split dev
.\.venv\Scripts\python.exe tests/context_perf.py
.\.venv\Scripts\python.exe tests/eval_context_e2e.py --config eval-results/nonthinking.config.local.toml --output-dir eval-results/m8-e2e-02
```
