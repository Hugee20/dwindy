# Dwindy 1.0.0 release candidate verification

2026-10-03. Practical Reach infrastructure and final release closure are complete.
Recommend releasing v1. This is an ordinary release record, not a new frozen evaluation.
Version `1.0.0` is prepared; the final commits/tag await review. Nothing is staged.

## Installation and regression

Reference platform: Windows x86-64, Python 3.13.0, Intel i3-1215U, 7.68 GiB usable RAM.
Chrome 154.0.8037.95. Reference model: Qwen3-1.7B Q4_K_M, context 4096, output allowance
256, temperature 0.7, seed 42, `enable_thinking=false`; existing reference TOML unchanged.
GGUF SHA-256: `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5`.

- Clean base environment: documented editable CPU-wheel installation succeeded; version/import
  metadata `1.0.0`, `pip check` passed, 8 terminal checks passed. FastAPI, pathspec, truststore,
  ONNX Runtime and FastEmbed are absent. Base operation requires none of those optional packages.
- Separate clean full environment: API/project/Reach installation succeeded, using
  llama-cpp-python 0.3.35 CPU wheel without source compilation. API-test/psutil extras were
  installed for verification only. `pip check` passed. No model was downloaded.
- Full final Python suite: **385 passed** (including 15 practical Reach tests and historical
  mechanics). No real-model frozen benchmark or holdout inference was run.
- Browser suite: **47 passed**; same-origin and approved cross-origin HTTP, rejected origins,
  independent standalone connection fix, mobile/zoom/accessibility, reset and cleanup passed.
- `git diff --check` passed. Frozen experiments/results/archives remain unchanged. Historical
  baseline checks recover exact recorded bytes from immutable checkpoint `228f023`, allowing
  ordinary production code to evolve without rewriting a historical evaluation.

## Five bounded live Reach checks

The first setup request established a real certificate requirement: standard TLS verification
failed with `CERTIFICATE_VERIFY_FAILED`; OS-native verification succeeded. One siteinfo request
then returned HTTP 403. The subsequent deliberate search requests returned material normally.
No TLS bypass, retries or provider changes were introduced.

An initial model-free pass exposed the test backend's character-as-token budget artifact:
it acquired/admitted material but supplied none. Receipts correctly reported budget exhaustion
and no source links. The five checks were repeated with the actual reference GGUF token counter
and one generation per turn. The reference-model observations below are the acceptance record.

| Check | Exact attempted query | State | Candidates / admitted / supplied entries | Prompt tokens |
| --- | --- | --- | --- | --- |
| Latest stable Python | `latest stable version python` | `supplied` | 3 / 3 / 2 | 624 |
| Current Philippine president | `current president philippines` | `supplied` | 3 / 3 / 3 | 663 |
| Latest Android version | `latest version android` | `supplied` | 3 / 3 / 3 | 707 |
| Ordinary photosynthesis chat | none | `not_attempted / not_fresh` | 0 / 0 / 0 | 17 |
| Python question, Reach OFF | none | `disabled / reach_off` | 0 / 0 / 0 | 62 |

Every displayed source title/URL was independently checked against the captured final model
packet. Python's third admitted entry did not fit and was absent from source metadata. Actual
supplied article links were:

- Python: **Python (programming language)** and **History of Python**.
- President: **List of presidents of the Philippines**, **President of the Philippines**,
  **List of current senators of the Philippines**.
- Android: **Android version history**, **Android-x86**, **Android Kunjappan Version 5.25**.

These observations expose a known lexical limitation: overlapping words can admit a wrong-scope
article, such as the Android film or senators list. The receipt accurately reports supply, not
semantic relevance or answer verification. No threshold/cue/ranking tuning was performed to
repair individual outputs. No Qwen provenance/status wording was graded.

Initial acquisition plus test preparation took 1.21 / 2.53 / 1.23 seconds for the three lookups.
Reference-GGUF total turn times were 41.43 / 54.55 / 48.72 / 44.55 / 30.30 seconds in check order,
including generation and concurrent mechanical verification. These are observations, not a
latency baseline or a transport-only benchmark. A five-second timeout is exercised mechanically;
an unfinished transport keeps its single slot and later turns cannot queue behind it.

Conditional optional dependency: `truststore==0.10.4`; base unchanged. One isolated import plus
SSL context observation was 96.44 ms, +7.27 MiB RSS, 112,833 installed package bytes. Context
required certificate verification and hostname checking. No verifier, extra generation,
embedding stack or new provider was installed for Reach.

## Final assembled runtime

Ran from the clean environment with the actual reference GGUF in two server processes, an
isolated synthetic project/document index, temporary conversation database, bearer authentication
and a real Chrome frontend. External socket access was blocked during this offline smoke.

Passed: ordinary conversation; exact local-document/project source identity against actual model
packets; Core token accounting; one generation per turn; transient evidence/native history;
unauthenticated request rejection; browser authenticated completion/reset; cancellation after
first text with unchanged stored history; graceful worker drain; process exit/model cleanup;
fresh process restoring exact saved user/assistant text; deletion/unknown-ID handling; project
dry-run, manual update and deleted-document removal. Persistence-OFF remains covered by existing
mechanical/browser checks and the separate reference Reach smoke's ephemeral conversations.

The first assembled run completed functional checks but its inspection-only test database
connection remained open during temporary-directory cleanup. The harness was corrected to close
it explicitly; the complete rerun passed. No production defect or architecture change was needed.

| Completed API turn | TTFT (s) | Completion (s) | Prompt / generated-text tokens |
| --- | --- | --- | --- |
| Offline conversation | 3.11 | 4.02 | 24 / 7 |
| Local document | 2.02 | 3.47 | 81 / 11 |
| Local project | 4.64 | 6.20 | 196 / 11 |
| Restored conversation | 2.64 | 3.13 | 54 / 3 |

Cold startup 7.91 seconds; restart startup 5.35 seconds. Peak observed model-process RSS during
the first smoke process: **1,583 MiB**. This is sampled process RSS, not total browser/OS memory
or an isolated inference benchmark. All four listed completions ended normally rather than
at the output limit. Browser and cancelled turns were checked for lifecycle, not response quality.

## Remaining limitations and disposition

Lexical matching, wrong-scope admission, incomplete Wikipedia extracts/snippets and freshness
misses remain documented limitations. Reach is optional, Wikipedia-only, disabled by default;
private names/arbitrary sensitive prose are not reliably removed. Native transport cancellation
is not guaranteed, but outstanding work is bounded. Qwen may hallucinate, ignore supplied facts,
misattribute information, mishandle conflicts/history or verbally imply unsupported host actions.
Dwindy performs no host actions. Source indicators are deterministic supply metadata, not factual
verification. Persistence is opt-in plaintext and can contain facts repeated in model answers.

Semantic retrieval and both broad/narrow M11 response-policy hypotheses remain unadopted. Their
original failed gates are unchanged. H2 remains deferred with exactly four paired captures;
no H2 completion/scoring, M11/Foundation/morphology/semantic holdout, or historical M1 rerun occurred.
No research/optional capability is promoted into another v1 blocker. No demonstrated v1 blocker
remains. Recommend **release Dwindy 1.0.0**, tag `v1.0.0`, following review of the pending checkpoints.

## Proposed checkpoints and changed files

Already separate/local: `228f023e6e651f1c21c2c7014ca2a11b855d7aad`,
`test: conclude bounded compact semantic matching experiment`. No further commit/push/tag was
performed during practical Reach/release closure.

Proposed next commits:

1. `feat: add bounded Wikipedia Reach with deterministic supply receipts` — Reach/API/Core/WEB
   integration, optional dependency, widget controls/status, ordinary tests and explicit historical
   bindings. Include only the Reach-extra hunk of pyproject; version bump belongs to checkpoint 2.
2. `chore: prepare Dwindy 1.0.0 release` — version metadata, living documentation reconciliation,
   assembled-runtime smoke and this verification record; then tag `v1.0.0` after approval.

Exact pending file inventory (no frozen fixture/result files):

```text
README.md
api.example.toml
docs/ARCHITECTURE.md
docs/CAPABILITIES.md
docs/REACH.md
docs/REACH_V1.md
docs/V1_COMPLETION_PATH.md
docs/V1_RELEASE_VERIFICATION.md
pyproject.toml
src/dwindy/__init__.py
src/dwindy/api.py
src/dwindy/core.py
src/dwindy/evidence.py
src/dwindy/reach.py
src/dwindy/server.py
tests/eval_reach_e2e.py
tests/eval_reach_v2_e2e.py
tests/reach_history_support.py
tests/smoke_reach_v1.py
tests/smoke_release_v1.py
tests/test_api_reach.py
tests/test_compact_semantic_matching_fixtures.py
tests/test_evidence_framing.py
tests/test_foundation_capability_adapter.py
tests/test_morphology_retrieval_fixtures.py
tests/test_policy_contract.py
tests/test_policy_foundation_runner.py
tests/test_practical_reach.py
tests/test_reach.py
tests/test_reach_v2.py
web/api-client.js
web/dwindy-chat.css
web/dwindy-chat.js
web/tests/api-client.test.js
web/tests/dwindy-chat.test.js
```

Raw ordinary-check logs/packet audits remain outside version control under `.cache/`:
`v1_final_tests.log`, `v1_final_browser.log`, `v1_clean_install.log`, `v1_base_install.log`,
`reach_v1_reference_live.jsonl`, `v1_release_smoke.json`. Temporary server databases/audits were
cleaned up successfully; historical model/evaluation artifacts are unchanged.
