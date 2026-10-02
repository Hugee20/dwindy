# M11 evidence-aware response-policy evaluation

Status: fixtures/reference interface frozen before any M11 runtime policy implementation,
inference, baseline response inspection or development tuning. The baseline is commit
25ea503202ba9b8030a78c2ac59df117aac7d0b9. See baseline.json for settings and prior freeze anchors.

**Design invariant: evidence-aware does not mean evidence-dependent.** Supplied evidence
should improve supported answers and constrain evidence-specific claims without suppressing
ordinary model knowledge, reasoning, writing, or conversation when evidence is unnecessary.
Origins describe information availability, not truth, confidence or actual model attribution.

## Boundaries

This is a response-policy evaluation, not a retrieval/answerability/verifier implementation.
No production policy, inference runner, model download, new dependency or developer setting
is added. Reach/H2 stays disabled/deferred. No capture, provider call or H2 artifact is changed.
The original M1-M10 evaluations remain unchanged. No live WEB capability is validated.

All material, paths, names, records and dates in cases.jsonl are synthetic. Fixture paths are
provenance labels; adapters must not read them. Host addresses are invented fixture text.
Only the API authenticates host context; independent Core fixtures use trusted test wiring.
PROJECT, DOCUMENT, TOOL, HOST, MODEL and MIXED are evaluation distinctions. HOST is explicit
because host information is not an executed tool. Runtime public provenance enums are not added.
WEB is used only in synthetic plumbing rows and is excluded from response-adoption gains.

## Composition and input

80 response episodes: 40 development and 40 holdout. Counts by primary category are in
split.json; odd category ordinals are dev, even ordinals holdout. Facets overlap. Each case
supplies exactly the existing Core inputs: message, alternating completed history, Evidence
or null, Facts or null, and notice or null. Evidence has at most three passages, 768-token
allowance; host allowance is 1024. These are candidate inputs, not assertions they fit a real
tokenizer. Confirm admission for both conditions and report all dropped items. Do not score
an annotated span as available if that item did not reach the model.

Gold components contain ref, span and exact start/end offsets into passage/computed/host text.
Gold absent/forbidden/behavior checks are for scorers only; never supply them to the model.
No answerability/support flag is passed to Core. A correct inferred date comparison or
ordinary explanation is allowed where correct_if says so. Data does not gain instruction status.
Conflict cases have no presumption that source order, host authentication, a filename or
project membership establishes authority. Distinct conflict values are deliberately not
annotated as a single authoritative answer. The history cases seed prior assistant claims;
model-only controls also include legitimate user-provided history that must remain useful.
Two ordinary controls include irrelevant evidence. Mixed cases require general explanation,
advice or writing alongside supplied facts; absence of a supplied explanation is not a reason
to refuse those general tasks. The recorded known host-action failure is development input;
holdout uses distinct tasks. This corpus is authored by the implementation author, not an
independently authored holdout; this limitation must accompany results.

## Plumbing interface

contract.jsonl has 48 rows, 24 dev/24 holdout, four per family. evaluate_contract(run_fn, split)
passes each row to an externally implemented probe and checks expected keys exactly. A probe
must observe actual inputs, events, generation counters, store state or configuration behavior,
not echo expected values. run_fn is intentionally NOT implemented in this fixture-only phase.
No passing production plumbing result is claimed. Runtime model-free probes belong to the
subsequent implementation phase after fixture review.

Each setup.profile names the following normative setup; scenarios/expected spell out the
variation. Use an existing fake backend and current API/Core contracts; never invoke a GGUF.

| Family | Four profiles in order |
| --- | --- |
| admission | Two small distinct passages c1/c2 fit; c1 fits and c2 does not; no candidate fits with plain fallback; explicit guidance/question cannot fit. Record actual admitted/reported IDs and generation calls. |
| origins | An ordinary document; project documentation with project_id; one of each; generated project_structure overview. Record supplied origin labels, never inferred support/runtime truth. |
| computed | Calculator result; undefined result; patched server-local clock; clock plus calculator. Observe framing and supplied fact names, no semantic answer judging. |
| host_auth | Valid configured bearer; configured token/no bearer; host data without configured token; a host block over its tokenizer allowance. Check API rejection and generation counters. |
| transience | Evidence turn then snapshot; host turn then transcript inspection; notice turn then snapshot; persistence restart after trimming. Compare supplied payloads against state, not assistant paraphrases. |
| history | Seed an assistant-only assertion with no current evidence; seed user preference; add current passage named current; restore a completed pair. Inspect roles/source metadata and boundary framing. |
| notice | Frozen offline notice without provider; same notice plus facts; unavailable project fallback plus facts; plain opportunistic fallback with notice absent. No provider requests. |
| generation | Success; mixed inputs; rejected invalid request; nonempty length completion. Count backend.generate invocations and verify completed-turn semantics. |
| plain | Fresh ordinary chat compared with M10; empty Facts vs none; no renderer requirement for origin prose; no implementation requirement for evidence to admit general work. These are construction/contract observations, not model-quality scores. |
| failure | Backend exception; started stream cancellation; empty response; failed persistent append. Verify no partial commit, close ordering and rollback/quarantine. |
| transport | JSON source reporting; SSE source reporting; database commit before success; disconnect/native cleanup exclusion. SSE normal vocabulary remains started/delta/completed/error. |
| synthetic_web | Build synthetic Evidence(origin=web) directly without enabling provider; inspect WEB framing; quote role/instruction data; assert release configuration still rejects online Reach. Synthetic only, zero network. |

Each profile pair can be repeated with different IDs/bounds for a robust later probe, but its
expected policy must not be changed to accommodate a result. A generic fake tokenizer may be
used for admission tests; include non-additive template cost in later probes. Semantic model
behavior is measured only by the separate blind response evaluation.

## Sequence

1. Validate fixtures, gold spans, split, evaluator logic and freeze coverage. Report composition
   and FREEZE.json hash; STOP for fixture review before runtime work.
2. After authorization, implement plumbing probes and the policy against dev only. Run M10
   and candidate on the same dev cases. Any reviewed pre-output fixture correction requires
   explicit re-freeze; never silently rewrite a frozen file.
3. Freeze candidate implementation and record dependency/model/configuration hashes.
4. Run holdout once, paired/counterbalanced by frozen case ordinal (odd M10-first, even
   candidate-first). Do not inspect holdout answers before this checkpoint. No candidate
   retuning after inspection; failed adoption is a result, not a license to repair the holdout.
5. Blind score, seal scores, reveal key, apply the gates in rubric.md/evaluate.py.

160 target generations for the full 80-case paired comparison. Seeded histories are restored,
not generated, in both conditions. There is one backend generation per target turn and no
verifier. Use the same GGUF hash/runtime/configuration and matched reset seed/cache state in
both conditions. If context reset cannot be established through supported runtime interfaces,
use a freshly constructed backend per measured episode outside the timer; never pretend
model state is matched. Record load time separately. Evidence selection inputs are identical;
compare admitted IDs and fail/report admission divergence rather than crediting a missing
hard source as an improvement. The database lifecycle is covered by model-free probes.

The evaluator accepts frozen human scores plus separately recorded observations. It never
judges arbitrary text mechanically, guesses missing scores, performs inference, or calls a
network. No observations exist yet. Reading schemas/hashes is fixture validation, not a
holdout outcome evaluation. Do not run the existing naked-model baseline.

## Evaluator/observation protocol

- validate_fixtures() checks schema, composition, actual support/conflict spans and conversion
  to existing immutable Core inputs; it does not claim model behavior.
- verify_freeze() checks exact byte hashes/coverage and prior manifest anchors.
- core_inputs(case) yields user_text/history/evidence/facts/notice only. A runner restores
  history and calls chat with the remaining arguments; never pass gold to the model.
- evaluate_contract(probe, split) records actual probe observations and exact-key mismatches.
- summarize(scores, split) reports overall/category dimensions with explicit denominators.
- assess_quality(M10_scores, candidate_scores) checks the frozen holdout quality gates.
- assess_performance(observations, contract_results) checks runtime/admission/performance gates.
- adoption(quality, performance, blind_scores_sealed=True, regressions_passed=True) requires
  both complete assessments and explicit scoring/regression confirmation. Defaults never adopt.

A human score uses the fields in rubric.md. Observations have id, condition (M10 or
M11_candidate), prompt_tokens, matched_input_tokens, history_turns, admitted_ids, model_calls,
verifier_calls, network_calls, ttft_s, end_to_end_s, policy_build_ms, execution_error (null or
error text), and finish_reason (stop/length/error). matched_input_tokens is the actual backend
count of a counterfactual rendered input with exactly the SAME admitted source text and retained
history in both conditions, isolating instruction/framing cost without dropping payloads.
It is not an arbitrary supplied overhead estimate. Record the counted messages as an audit
artifact. prompt_tokens is the actual generation input count. Raw output and metadata also
belong in the later runner's audit artifacts; the interface does not itself capture them.

On inference error, retain the raw failure record, score the delivered answer appropriately,
and fail adoption; do not omit that episode. Performance assessment rejects missing/non-finite
TTFT rather than silently shrinking a denominator. End-to-end/prompt counts/history divergence
are diagnostic, not additional retrospectively selected quality gates. Counterfactual counting
makes no model generation. No performance or production-probe observations exist in this phase.

Golden conflict_spans list exact opposing source statements; they are NOT authoritative answer
components and do not establish a truth hierarchy. Synthetic unit tests of evaluator arithmetic
are not model scores or production contract results. No hidden scoring regex decides semantic
support or truth. Model/metadata input differences, reviewer judgments and small English-only
coverage remain evaluation limitations.
