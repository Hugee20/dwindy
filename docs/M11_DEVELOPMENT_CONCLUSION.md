# M11 development conclusion: Evidence-aware response policy

Qualification: **bounded source framing and runtime boundaries**.

Development is concluded with retained framework infrastructure and negative experimental
findings. Neither the original broad M11 hypothesis nor the separate narrower Foundation
hypothesis was adopted as a complete response policy. This is not a successful semantic-policy
adoption, nor a claim that the experiments produced no useful work. Both holdouts remain
sealed/unspent: neither was generated, inspected or scored. No Foundation v3 or further tuning.

## Experimental disposition

Original v1/v2/v3 development screens failed. Narrowing followed development evidence, never
holdout outcomes. The separately versioned Foundation evaluation was authored after those
experiments and did not supersede them. Foundation v1 and v2 each reached 19/24 fully correct
development episodes versus paired M10's 17/24, but both still failed the frozen 2/2 host-action
requirement with **0/2**. Evidence-independence and strict continuity screens also failed.
Historical semantic scores are disclosed provisional non-blind assistant judgments, not sealed
blind human acceptance. No failed gate is weakened, replaced or reinterpreted.

Foundation v2 replaced only the trusted capability sentence with:

`DWINDY/action-capability: Dwindy (this assistant) cannot perform actions in the host application.`

The exact sentence appeared in both actual system inputs, under the existing nonempty-HOST
trigger. One output offered renewal advice; the other asked whether the user wanted another
address. Neither explicitly stated Dwindy's execution boundary. Informational HOST cases
retained their values without new disclaimers, refusals, denial or invented host incapability.
This is evidence of a model-output limitation despite correct runtime information, not evidence
that Dwindy can execute actions or that the host lacks them. No classifier, refusal template,
verifier, second generation, repeated stronger instruction or factual rewriting was added.

## What is retained, and what it guarantees

| Mechanism | Deterministic boundary | What it does not establish |
|---|---|---|
| Typed PROJECT/DOCUMENT/HOST/TOOL entries | Explicit input origins and metadata-derived project subtypes | Truth, verification, priority, actual model use or perfect attribution |
| Escaping and ordered records | Lossless source text/names, structural quoting, unchanged selected-entry order | Semantic injection immunity or correct interpretation |
| Compact conditional framing / scoped project warning | Supplies information/origin and selected-file observation boundaries | Conflict resolution, absence/contradiction reasoning or factual consistency |
| Dwindy capability record | Represents a runtime fact about Dwindy itself under the existing HOST trigger | Reliable verbal refusal or knowledge of host-application capabilities |
| Native history and transient evidence | Exact retained utterances; evidence/capability framing excluded from ordinary history/persistence | Repair of earlier unsupported assistant claims |
| Budgeting/lifecycle/public boundaries | Actual backend count, existing reserves/allowances, whole-turn trim, commit/rollback, stream cleanup, one generation | Identical admission for every possible input after framing text changes |

All ten requested Foundation output components were retained in both development runs. That is
sampled model evidence, not a mechanically enforceable answer guarantee. Data retention in the
input and factual consistency in the answer are separate questions. The absence of an action
executor is an execution boundary; explaining it correctly remains best-effort generation.

Evidence-aware does not mean evidence-dependent. Ordinary knowledge, reasoning, conversation
and writing remain available. No global policy is added to fresh context-free or history-only
requests. Native history remains context rather than authenticated evidence.

## Production cleanup actually performed

- Kept independent typed records, metadata subtypes, lossless escaping/order, compact
  information/origin framing, the scoped project warning and direct Dwindy capability fact.
- Removed experiment-only `_render_messages` / `_bounded_turn` indirection and unused
  representation parameters. No quoted-history demotion or procedural conflict/support/premise
  scaffolding remains in production. M2/M5 native-history and transaction behavior stay intact.
- Restored dormant WEB/facts guidance to pinned M10. WEB and WEB_SENTENCE instructions,
  quoted records, notice composition and native history match M10 in model-free comparisons.
  Reach remains disabled; H2 design/manifests/partial captures are unchanged.
- Restored direct legacy Core/API/history assertions; moved quoted-history decoding to
  historical support. Production tests inspect actual backend messages without decoding away
  role changes. The fake backend's 400-character default accommodates typed fixtures; explicit
  near-limit tests still assert trimming/rejection. Runtime budgets did not change.
- Preserved the independent standalone connection fix and all its files byte-for-byte.
- No dependency, setting, public provenance/confidence field, model setting, retrieval/ranking,
  freshness, tool, persistence or API/SSE change. No real-model inference during cleanup.

The retained local representation matches archived Foundation v2 in the focused model-free
scenarios. Actual-token accounting remains authoritative: framing changes relative to M10 may
change admission/retained context near a limit; no universal token/admission identity is claimed.

## Historical preservation and reproducibility boundary

Original freeze: `e098fe14666bd43a6ee797d8fc7e94585d169c9e4b9ac0633943590be731cc26`.
Foundation freeze: `59190f0dd49f5cd6721bdabf97472a9d69ec4829b1bce21c6a3fad74bb3e5a8f`.
Frozen fixtures, rubrics, gates, probes, splits and freeze files remain byte-for-byte unchanged.
All historical reports, scores, results and H2 artifacts are preserved.

Foundation v1/v2 Core/evidence snapshots match their original recorded runtime hashes.
Their exact runners/tests are preserved under `tests/policy_experiments/`, with PRESERVED.json.
The existing broad v3 archive is unchanged and its runtime matches its original run manifest.
A new HISTORY.json records original run-manifest hashes and source-hash anchors, including the
historical aborted v2 preparation. Available original source snapshots and raw results remain
local; unavailable original source is not reconstructed. Source snapshots are archival data,
not direct inference commands. Top-level historical inference commands now fail closed.

`archive.py` loads version-specific historical framing/Core/probes/tests, not cleaned production.
Shared immutable fixture data types are allowed only after their definition source is checked
identical. No production module is replaced. Historical v3 assertions remain bound to its
preserved implementation. Raw old results are never recalculated or relabeled from cleanup.

Foundation v1's historical frozen probes remain **32/32**. Foundation v2's frozen probes remain
**30/32**, with `capability_1` and `capability_2` requiring the old sentence; its separately
versioned compatibility adapter remains **32/32**, not frozen acceptance. Production infrastructure
has its own explicit tests. Historical compatibility is not presented as policy adoption.

Git attributes preserve the original mixed LF/CRLF bytes for both M11 freezes and source
archives; no normalization was applied to frozen content. Local ignored artifacts are preserved,
not force-added with machine-specific run-manifest paths.

## Validation

- **331/331 Python tests**, zero failures/errors/skips. All previous 317 checks remain passing;
  14 new production/archive tests cover retained boundaries and historical bindings.
- **48/48 original model-free plumbing probes**.
- **64 paired dormant WEB-path scenarios** against pinned M10 (two origins, four fact
  combinations, empty/nonempty passages, two fallbacks, notice absent/present), with exact
  backend messages and retained state equality. All use fake backends; zero real inference.
- **45/45 browser tests**, Chrome 154.0.8037.95. Fake-backend same/cross-origin conversation,
  standalone destination/token switching, wrong-token rejection, deletion/reset, unapproved
  origin blocking, accessibility, host-style isolation and clean shutdown passed.
- Both freeze hashes and archive hashes/bindings checked; protected history and frontend hashes
  unchanged. No holdout execution, verifier, external-provider call or Reach/H2 capture.
- Git whitespace check passed. No staged files and no commit.

Mechanical validation does not imply successful model-policy acceptance. No new performance
claim is made: cleanup ran no real-model generations or new timed model comparison.

## Limits and roadmap

Arbitrary semantic conflicts, conflict resolution, earlier-assistant correction, complete partial
support, absent-versus-contradicted prose, perfect mixed attribution, factual self-consistency
and reliable verbal host-action boundaries remain best-effort model limitations/future research.
They do not silently disappear or automatically move into M12. Any future experiment needs
separate approval and an evaluation. M12 remains optimization and V1 hardening; it has not begun.
No dependency review was undertaken during this cleanup.

## Proposed checkpoint contents and review boundary

Checkpoint M11's retained infrastructure, frozen original/Foundation evaluations, unchanged
historical development reports, new conclusion/status documentation, source archives/bindings,
mechanical tests and line-ending preservation. Suggested message:

`chore: conclude M11 experiments and retain source-framing infrastructure`

The accepted frontend connection fix is independent and should be a separate bugfix checkpoint:
`fix: apply standalone connection settings before starting fresh`.
It includes web/dwindy-chat.js, web/standalone.js, web/tests/dwindy-chat.test.js,
tests/browser_checks.py and docs/CHAT_INTERFACES.md. Those files were not changed by cleanup.
The pre-existing untracked H2 capture manifest/four paired development captures remain untouched
and outside the M11 cleanup; their checkpoint treatment requires review, not an automatic add.

The repository has cleaned production boundaries but a deliberately uncommitted working tree.
No staging/commit or automatic milestone advancement. See the local cleanup inventory/status
under `eval-results/m11-cleanup-preparation/` for every changed/new file and regression log.
Stop for review.
