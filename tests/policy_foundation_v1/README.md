# Evidence-aware response policy: bounded source framing and runtime boundaries

Status: separate narrowed acceptance hypothesis, authored after M11 v1/v2/v3 development.
Fixtures/interfaces are frozen for review; no final production implementation or
response evaluation is claimed by this document. FREEZE.json is the byte-level authority.

**Evidence-aware does not mean evidence-dependent.** Origins describe supplied information,
not truth, priority, confidence, or proof that a generated answer used that source.

## Historical distinction

The original M11 semantic-reliability hypothesis failed its development screens. Its frozen
suite at tests/policy and all v1/v2/v3 development results remain unchanged. Its holdout was
never generated, inspected or scored. This suite does not replace/supersede that evaluation
or retroactively pass it. Narrowing followed development evidence, not holdout results.
The new suite is not an independently authored confirmation: it deliberately uses failure
patterns discovered in those experiments. Small synthetic English groups limit generalization.

## Composition

48 synthetic episodes: six families of eight, each four development/four holdout. The fixed
split uses odd ordinals for dev and even ordinals for holdout. No selection based on outputs.
Families: supplied PROJECT/DOCUMENT facts; computed results/clearly separated mixed entries;
HOST information/actions; fresh ordinary tasks; ordinary tasks with irrelevant evidence;
two-turn conversational continuity. 8 two-turn episodes give 56 turns, 112 paired generations
in total, 56 paired generations per split. One generation PER TURN, no verifier or continuation.

Regressions represented: quoted-then-denied export paths, stale assistant text next to current
explicitly requested evidence, source observations versus live behavior, TOOL/HOST/PROJECT
misattribution, contact information denial, invented action capability, irrelevant-evidence
refusal, unsolicited policy/provenance prose, injection/role markers, user preferences,
escaped-newline editing and references to an earlier answer. The clock tests request the
recorded clock fact, not arbitrary temporal reasoning; absent PIN/expiry policies are not
made answerability gates. Broad semantic conflict/history correction remains a known limitation.

All fixture material is synthetic. Paths are provenance labels, NEVER paths to ingest/read.
Gold is scorer-only. No support/contradiction annotations reach Core. PROJECT subtype is based
on metadata; HOST means application-reported information, not an executed action; TOOL means
a deterministic result. No MODEL/MIXED enum or public provenance/confidence field is added.
WEB is not an inference condition; Reach/H2 is deferred and unchanged.

32 mechanical probes: four per family in contract.jsonl. There is no semantic holdout for
mechanical probes; all 32 must eventually pass. probes.observe records actual requests/events,
counts/snapshots and existing API/store behavior with a fake backend. It never reads expected
values to produce observations. These probes target the future assembled implementation;
the current quoted-history v3 is NOT that implementation and must not be represented as
passing acceptance. Fixture/evaluator validation is distinct from framework acceptance.

## Interface

- validate_fixtures: composition, IDs, split, per-turn Core conversion, gold offsets/hashes.
- verify_freeze: exact file coverage and byte hashes plus historical anchors.
- turn_inputs(case,index): existing user_text/evidence/facts/notice and initial native history;
  history is None on follow-ups. Restore seeded history once, never replace live follow-up state.
- evaluate_contract(probe): actual observed mappings, strict typed expected-key matching.
- validate_scores/summarize: complete human scores and category/dimension denominators.
- assess_quality/assess_performance: holdout-only acceptance calculations; dev uses summaries.
- adoption: requires passing assessments, candidate frozen before holdout, sealed blind scores,
  passing regressions and explicit review. It never silently adopts from synthetic test values.

No inference runner is added in this fixture phase. A future runner writes raw answers,
actual counted/generated inputs, admitted source IDs, per-turn history, network/model counters,
load time and runtime/model/config hashes. No runtime option exposes evaluation distinctions.

## Frozen protocol

1. Validate/freeze this suite and report its manifest hash; STOP for fixture review.
2. After approval, assemble the selected implementation without modifying this suite. Run
   mechanical/regression checks and development only. Stop for implementation review.
3. Record implementation/model/configuration hashes before any new holdout responses. Obtain
   separate approval; the original semantic holdout remains unused regardless.
4. Run the new holdout once, paired M10/M11_foundation in fixed episode order, counterbalanced
   M10-first on odd episode ordinal and foundation-first on even ordinal. Keep each continuity
   episode's two turns together, preserving live history. Fresh backend per episode, identical
   initial model/cache/seed, no reset between its turns. Exclude loading from request timing.
5. Canonical admitted material/history and raw answers go to a randomized opaque-token sheet.
   Hide condition names, timing and rendered guidance. Human blind-score, seal judgments and
   disputes before revealing the key. Disclose residual blinding/fixture-author limitations.
6. Apply the gates; failed acceptance is a result, not permission to repair the holdout/suite.

Use the frozen M10 checkpoint and same reference Qwen model/hash, llama-cpp-python 0.3.35,
4096/256/0.7/42/non-thinking/empty-system settings in baseline.json. No downloads/network.
Do not rerun the naked-model M1 evaluation. No Reach/H2 capture or provider execution.

Observations (one per id/turn/condition): id, zero-based turn, condition, prompt_tokens,
matched_input_tokens, retained_turns, admitted_ids, ttft_s, end_to_end_s, construction_ms,
output_tokens, model_calls, verifier_calls, network_calls, execution_error, finish_reason,
budget_audit_pass. Record actual messages separately. matched_input_tokens counts a paired
counterfactual with identical admitted content AND canonical retained history, isolating
framing cost; prompt_tokens is the actual generation input. Counterfactuals tokenize only.
Do not overwrite conversation history to force a match. Audit any differing generated history,
selection/window or model payload; budget_audit_pass must be false for unexplained divergence
or understated costs. Current fixtures are bounded well within context; near-limit mechanics
are exercised by fake non-additive token probes and later actual-token checks. No missing
measurement may disappear from a denominator. Report load separately, completion time,
output length, truncation and input cost; raw TTFT includes every generated text/tag.

## Scope limits

Mechanical escaping/runtime exclusion is enforceable; semantic injection resistance in output
is a sampled release criterion, not universal immunity. Arbitrary conflict recognition/resolution,
historical hallucination repair, full partial-support reasoning, absence/contradiction interpretation,
perfect mixed attribution and self-consistency remain best-effort limitations/future research.
They are not automatically moved into M12. Passing this suite makes no original M11 pass claim.
