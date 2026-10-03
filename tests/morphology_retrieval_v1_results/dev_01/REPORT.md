# morphology_retrieval_v1 development report

**Recommendation: stop morphology. Neither B nor C passes all frozen development gates.**

Freeze SHA-256: `6c1b8a9e252a55a878987082dc0f0e599ac8175486819d6b2697a988072d2bca`. Forty-eight development cases per arm; no fresh morphology holdout, either M11 holdout, model inference, network calls, dependency installation, production modification, staging or commit. Historical M6–M8 panels include their already-spent historical splits only. No tuning and no discarded trials.

Machine: Windows-11-10.0.26200-SP0; Python 3.13.0; SQLite 3.45.3.

## Fresh results

Thirty positive cases include 18 acceptance positives (12 morphological, six exact) and 12 diagnostic-only synonym/language cases. Eighteen negative controls are evaluated separately. Candidate recall includes explicitly marked post-hoc availability probes where context policy bypassed retrieval; those probes do not imply production admission or contribute timed selection. Admission null means bypassed, not rejected.

| Metric | A | B | C |
| --- | --- | --- | --- |
| candidate_recall12 | 9/30 | 21/30 | 21/30 |
| relevant_recall3 | 9/30 | 21/30 | 21/30 |
| final_selection_recall | 9/30 | 9/30 | 21/30 |
| answer_hit1 | 9/30 | 21/30 | 21/30 |
| answer_hit3 | 9/30 | 21/30 | 21/30 |
| final_answer_recall | 9/30 | 9/30 | 21/30 |
| answer_mrr3 | 0.300 | 0.700 | 0.700 |
| usefulness applied / admitted | 41 / 9 | 41 / 9 | 41 / 21 |
| irrelevant supply (18 controls) | 2/18 | 2/18 | 2/18 |

Acceptance positives only: candidate@12 / relevant@3 / Hit@1 / Hit@3 = A 6/18, B 18/18, C 18/18; final relevant and final answer = A 6/18, B 6/18, C 18/18. MRR@3 = A 0.333, B 1.000, C 1.000. These are retrieval metrics, not generated-answer accuracy.

| Category (six each) | A candidate/final | B candidate/final | C candidate/final | A/B/C false supply |
| --- | --- | --- | --- | --- |
| inflection | 0/6 / 0/6 | 6/6 / 0/6 | 6/6 / 6/6 | 0 / 0 / 0 |
| derivation | 0/6 / 0/6 | 6/6 / 0/6 | 6/6 / 6/6 | 0 / 0 / 0 |
| exact_identifier | 6/6 / 6/6 | 6/6 / 6/6 | 6/6 / 6/6 | 0 / 0 / 0 |
| collision | — / — | — / — | — / — | 0 / 0 / 0 |
| accidental_overlap | — / — | — / — | — / — | 0 / 0 / 0 |
| ordinary_control | — / — | — / — | — / — | 2 / 2 / 2 |
| synonym | 0/6 / 0/6 | 0/6 / 0/6 | 0/6 / 0/6 | 0 / 0 / 0 |
| filipino_taglish | 3/6 / 3/6 | 3/6 / 3/6 | 3/6 / 3/6 | 0 / 0 / 0 |

Within every positive category, answer Hit@1, Hit@3 and relevant@3 equal candidate@12; final answer recall equals final relevance. Synonym recall stays 0/6 and Filipino/Taglish stays 3/6 in all arms. English anchors explain the latter matches; neither result establishes semantic or multilingual matching.

## Frozen gates, independently assessed

| Gate | B | C |
| --- | --- | --- |
| candidate_recall | PASS | PASS |
| relevant_top3 | PASS | PASS |
| final_selection | FAIL | PASS |
| gain | FAIL | PASS |
| exact_retention | PASS | PASS |
| zero_false_supply | FAIL | FAIL |
| no_exact_loss | PASS | PASS |
| historical | PASS | PASS |
| mechanical | PASS | PASS |
| warm_absolute | FAIL | FAIL |
| warm_relative | PASS | PASS |
| build | PASS | PASS |
| size | PASS | PASS |
| rss | PASS | PASS |

B: morphology candidate/top-three 12/12, but final 0/12 and net gain zero. C: 12/12 at all three stages, net gain +12 with zero losses. Exact final retention 6/6 in every arm, no A successes lost. All 24 mechanical probes pass; historical false-positive gate passes both arms. Both fail zero irrelevant supply (2/18) and absolute warm p95 <=25 ms. Relative limit is 37.086 ms; both pass. Neither is eligible; the simpler-arm tie-break does not apply.

## Individual failures and changes

Both negative failures occur unchanged in A/B/C:

| ID | Request | Unrelated supplied text | Mechanism |
| --- | --- | --- | --- |
| ordinary_control_dev_3 | Thanks, that helps. | Thanks cards are stored beside the gift shelf. | thanks covers 1/2 retained terms: threshold met |
| ordinary_control_dev_5 | Why is the sky blue? | Blue receipt books are issued monthly. | blue covers 1/2 retained terms: threshold met |

Every inflection_dev_1–6 and derivation_dev_1–6 is a final-context miss in A and B and a success in C. In A no morphological candidate is found; B finds answer-bearing candidates but original usefulness rejects all 12. Every synonym_dev_1–6 remains a gold retrieval miss in all arms. The individual positive/negative failures, exact supplied passages, gold scores, and bypasses are enumerated below and in development-report.json / development-observations.json.

| Case | A candidate/admission/final | B candidate/admission/final | C candidate/admission/final |
| --- | --- | --- | --- |
| inflection_dev_1 | False / False / False | True / False / False | True / True / True |
| inflection_dev_2 | False / False / False | True / False / False | True / True / True |
| inflection_dev_3 | False / False / False | True / False / False | True / True / True |
| inflection_dev_4 | False / False / False | True / False / False | True / True / True |
| inflection_dev_5 | False / False / False | True / False / False | True / True / True |
| inflection_dev_6 | False / False / False | True / False / False | True / True / True |
| derivation_dev_1 | False / False / False | True / False / False | True / True / True |
| derivation_dev_2 | False / False / False | True / False / False | True / True / True |
| derivation_dev_3 | False / False / False | True / False / False | True / True / True |
| derivation_dev_4 | False / False / False | True / False / False | True / True / True |
| derivation_dev_5 | False / False / False | True / False / False | True / True / True |
| derivation_dev_6 | False / False / False | True / False / False | True / True / True |
| exact_identifier_dev_1 | True / True / True | True / True / True | True / True / True |
| exact_identifier_dev_2 | True / None / True | True / None / True | True / None / True |
| exact_identifier_dev_3 | True / None / True | True / None / True | True / None / True |
| exact_identifier_dev_4 | True / True / True | True / True / True | True / True / True |
| exact_identifier_dev_5 | True / None / True | True / None / True | True / None / True |
| exact_identifier_dev_6 | True / True / True | True / True / True | True / True / True |
| synonym_dev_1 | False / False / False | False / False / False | False / False / False |
| synonym_dev_2 | False / False / False | False / False / False | False / False / False |
| synonym_dev_3 | False / False / False | False / False / False | False / False / False |
| synonym_dev_4 | False / False / False | False / False / False | False / False / False |
| synonym_dev_5 | False / True / False | False / True / False | False / True / False |
| synonym_dev_6 | False / False / False | False / False / False | False / False / False |
| filipino_taglish_dev_1 | False / False / False | False / False / False | False / False / False |
| filipino_taglish_dev_2 | False / False / False | False / False / False | False / False / False |
| filipino_taglish_dev_3 | False / False / False | False / False / False | False / False / False |
| filipino_taglish_dev_4 | True / True / True | True / True / True | True / True / True |
| filipino_taglish_dev_5 | True / True / True | True / True / True | True / True / True |
| filipino_taglish_dev_6 | True / True / True | True / True / True | True / True / True |
| collision_dev_1 | False / False / False | False / False / False | False / False / False |
| collision_dev_2 | False / False / False | False / False / False | False / False / False |
| collision_dev_3 | False / False / False | False / False / False | False / False / False |
| collision_dev_4 | False / False / False | False / False / False | False / False / False |
| collision_dev_5 | False / False / False | False / False / False | False / False / False |
| collision_dev_6 | False / False / False | False / False / False | False / False / False |
| accidental_overlap_dev_1 | False / False / False | False / False / False | False / False / False |
| accidental_overlap_dev_2 | False / False / False | False / False / False | False / False / False |
| accidental_overlap_dev_3 | False / False / False | False / False / False | False / False / False |
| accidental_overlap_dev_4 | False / False / False | False / False / False | False / False / False |
| accidental_overlap_dev_5 | False / False / False | False / False / False | False / False / False |
| accidental_overlap_dev_6 | False / False / False | False / False / False | False / False / False |
| ordinary_control_dev_1 | False / None / False | False / None / False | False / None / False |
| ordinary_control_dev_2 | False / None / False | False / None / False | False / None / False |
| ordinary_control_dev_3 | False / True / False | False / True / False | False / True / False |
| ordinary_control_dev_4 | False / None / False | False / None / False | False / None / False |
| ordinary_control_dev_5 | False / True / False | False / True / False | False / True / False |
| ordinary_control_dev_6 | False / None / False | False / None / False | False / None / False |

### Every selection/decision change

#### A->B (17 changes)

| Case | Decision before → after | Admission before → after | Supplied before → after |
| --- | --- | --- | --- |
| inflection_dev_1 | no_candidates → weak_match | False → False | none → none |
| inflection_dev_2 | no_candidates → weak_match | False → False | none → none |
| inflection_dev_3 | no_candidates → weak_match | False → False | none → none |
| inflection_dev_4 | no_candidates → weak_match | False → False | none → none |
| inflection_dev_5 | no_candidates → weak_match | False → False | none → none |
| inflection_dev_6 | no_candidates → weak_match | False → False | none → none |
| derivation_dev_1 | no_candidates → weak_match | False → False | none → none |
| derivation_dev_2 | no_candidates → weak_match | False → False | none → none |
| derivation_dev_3 | no_candidates → weak_match | False → False | none → none |
| derivation_dev_4 | no_candidates → weak_match | False → False | none → none |
| derivation_dev_5 | no_candidates → weak_match | False → False | none → none |
| derivation_dev_6 | no_candidates → weak_match | False → False | none → none |
| collision_dev_1 | no_candidates → weak_match | False → False | none → none |
| collision_dev_3 | no_candidates → weak_match | False → False | none → none |
| collision_dev_4 | no_candidates → weak_match | False → False | none → none |
| collision_dev_5 | no_candidates → weak_match | False → False | none → none |
| collision_dev_6 | no_candidates → weak_match | False → False | none → none |

#### A->C (17 changes)

| Case | Decision before → after | Admission before → after | Supplied before → after |
| --- | --- | --- | --- |
| inflection_dev_1 | no_candidates → relevant_match | False → True | none → d000:e963667d, d051:e92373c0 |
| inflection_dev_2 | no_candidates → relevant_match | False → True | none → d001:dcb8ca1c, d085:4add69c3 |
| inflection_dev_3 | no_candidates → relevant_match | False → True | none → d002:efcc2e3f |
| inflection_dev_4 | no_candidates → relevant_match | False → True | none → d003:0d06a86a, d084:8e78e456 |
| inflection_dev_5 | no_candidates → relevant_match | False → True | none → d004:1a12b291 |
| inflection_dev_6 | no_candidates → relevant_match | False → True | none → d005:b6f992fb |
| derivation_dev_1 | no_candidates → relevant_match | False → True | none → d012:9a4fb2f0 |
| derivation_dev_2 | no_candidates → relevant_match | False → True | none → d013:08467068 |
| derivation_dev_3 | no_candidates → relevant_match | False → True | none → d014:bba28aa9 |
| derivation_dev_4 | no_candidates → relevant_match | False → True | none → d015:c1ca306f |
| derivation_dev_5 | no_candidates → relevant_match | False → True | none → d016:8edb2529, d089:818fa0ae |
| derivation_dev_6 | no_candidates → relevant_match | False → True | none → d017:917d31b8 |
| collision_dev_1 | no_candidates → weak_match | False → False | none → none |
| collision_dev_3 | no_candidates → weak_match | False → False | none → none |
| collision_dev_4 | no_candidates → weak_match | False → False | none → none |
| collision_dev_5 | no_candidates → weak_match | False → False | none → none |
| collision_dev_6 | no_candidates → weak_match | False → False | none → none |

#### B->C (12 changes)

| Case | Decision before → after | Admission before → after | Supplied before → after |
| --- | --- | --- | --- |
| inflection_dev_1 | weak_match → relevant_match | False → True | none → d000:e963667d, d051:e92373c0 |
| inflection_dev_2 | weak_match → relevant_match | False → True | none → d001:dcb8ca1c, d085:4add69c3 |
| inflection_dev_3 | weak_match → relevant_match | False → True | none → d002:efcc2e3f |
| inflection_dev_4 | weak_match → relevant_match | False → True | none → d003:0d06a86a, d084:8e78e456 |
| inflection_dev_5 | weak_match → relevant_match | False → True | none → d004:1a12b291 |
| inflection_dev_6 | weak_match → relevant_match | False → True | none → d005:b6f992fb |
| derivation_dev_1 | weak_match → relevant_match | False → True | none → d012:9a4fb2f0 |
| derivation_dev_2 | weak_match → relevant_match | False → True | none → d013:08467068 |
| derivation_dev_3 | weak_match → relevant_match | False → True | none → d014:bba28aa9 |
| derivation_dev_4 | weak_match → relevant_match | False → True | none → d015:c1ca306f |
| derivation_dev_5 | weak_match → relevant_match | False → True | none → d016:8edb2529, d089:818fa0ae |
| derivation_dev_6 | weak_match → relevant_match | False → True | none → d017:917d31b8 |

Final supplied evidence changes only on the 12 morphology cases for A→C/B→C; A→B changes candidate availability/weak-match reason but never supplies new evidence. Ranking changes include cases with no selection change:

A->B (20): inflection_dev_1, inflection_dev_2, inflection_dev_3, inflection_dev_4, inflection_dev_5, inflection_dev_6, derivation_dev_1, derivation_dev_2, derivation_dev_3, derivation_dev_4, derivation_dev_5, derivation_dev_6, collision_dev_1, collision_dev_2, collision_dev_3, collision_dev_4, collision_dev_5, collision_dev_6, accidental_overlap_dev_6, ordinary_control_dev_1.

A->C (20): inflection_dev_1, inflection_dev_2, inflection_dev_3, inflection_dev_4, inflection_dev_5, inflection_dev_6, derivation_dev_1, derivation_dev_2, derivation_dev_3, derivation_dev_4, derivation_dev_5, derivation_dev_6, collision_dev_1, collision_dev_2, collision_dev_3, collision_dev_4, collision_dev_5, collision_dev_6, accidental_overlap_dev_6, ordinary_control_dev_1.

B->C (0): .

Exact old/new candidate ranking, text, offsets and source identities for every ranking change are retained in development-report.json; full token audits are in development-observations.json.

### Every annotated Porter collision

| Case | Original query / source tokens | Porter stems | Maximum C coverage | Admission A/B/C |
| --- | --- | --- | --- | --- |
| collision_dev_1 | university / universe | univers / univers | 0.333 | False / False / False |
| collision_dev_2 | general / generation | gener / gener | 0.250 | False / False / False |
| collision_dev_3 | customs / custom | custom / custom | 0.333 | False / False / False |
| collision_dev_4 | arms / arm | arm / arm | 0.250 | False / False / False |
| collision_dev_5 | organic / organ | organ / organ | 0.250 | False / False / False |
| collision_dev_6 | console / consolation | consol / consol | 0.250 | False / False / False |

These collisions introduce misleading candidates; none changes admission to true. collision_dev_2 already has an unrelated exact counted match in A. Full original passage tokens, resulting stems, query-to-stem maps and original-term denominator are retained for every observed candidate, including incidental stem overlaps outside the annotated collision category. This is token correspondence, not semantic collision detection.

## Historical diagnostics (no fresh acceptance credit)

### M6

| Arm | Original evaluator overall results |
| --- | --- |
| A | {"answerable": 20, "cases": 24, "duplicate_slots": 0, "hit1": 0.75, "hit3": 0.95, "negative_nonempty": 2, "rr3": 0.85} |
| B | {"answerable": 20, "cases": 24, "duplicate_slots": 0, "hit1": 0.85, "hit3": 0.95, "negative_nonempty": 3, "rr3": 0.9} |
| C | {"answerable": 20, "cases": 24, "duplicate_slots": 0, "hit1": 0.85, "hit3": 0.95, "negative_nonempty": 3, "rr3": 0.9} |

Every A->B change (4):

| Case | Before | After |
| --- | --- | --- |
| C3 | {"answerable": true, "category": "competition", "documents": ["E", "D"], "duplicates": 0, "hit1": 1, "hit3": 1, "id": "C3", "negative_kind": null, "returned": 2, "rr3": 1.0, "split": "dev"} | {"answerable": true, "category": "competition", "documents": ["D", "E"], "duplicates": 0, "hit1": 1, "hit3": 1, "id": "C3", "negative_kind": null, "returned": 2, "rr3": 1.0, "split": "dev"} |
| I1 | {"answerable": true, "category": "distractors", "documents": ["H", "A", "B"], "duplicates": 0, "hit1": 0, "hit3": 1, "id": "I1", "negative_kind": null, "returned": 3, "rr3": 0.5, "split": "dev"} | {"answerable": true, "category": "distractors", "documents": ["A", "H", "B"], "duplicates": 0, "hit1": 1, "hit3": 1, "id": "I1", "negative_kind": null, "returned": 3, "rr3": 1.0, "split": "dev"} |
| N1 | {"answerable": false, "category": "no_answer", "documents": [], "duplicates": 0, "hit1": 0, "hit3": 0, "id": "N1", "negative_kind": "lexical_absence", "returned": 0, "rr3": 0, "split": "dev"} | {"answerable": false, "category": "no_answer", "documents": ["F"], "duplicates": 0, "hit1": 0, "hit3": 0, "id": "N1", "negative_kind": "lexical_absence", "returned": 1, "rr3": 0, "split": "dev"} |
| A2 | {"answerable": true, "category": "adversarial", "documents": ["I", "J", "A"], "duplicates": 0, "hit1": 0, "hit3": 1, "id": "A2", "negative_kind": null, "returned": 3, "rr3": 0.5, "split": "holdout"} | {"answerable": true, "category": "adversarial", "documents": ["J", "I", "A"], "duplicates": 0, "hit1": 1, "hit3": 1, "id": "A2", "negative_kind": null, "returned": 3, "rr3": 1.0, "split": "holdout"} |

Every A->C change (4):

| Case | Before | After |
| --- | --- | --- |
| C3 | {"answerable": true, "category": "competition", "documents": ["E", "D"], "duplicates": 0, "hit1": 1, "hit3": 1, "id": "C3", "negative_kind": null, "returned": 2, "rr3": 1.0, "split": "dev"} | {"answerable": true, "category": "competition", "documents": ["D", "E"], "duplicates": 0, "hit1": 1, "hit3": 1, "id": "C3", "negative_kind": null, "returned": 2, "rr3": 1.0, "split": "dev"} |
| I1 | {"answerable": true, "category": "distractors", "documents": ["H", "A", "B"], "duplicates": 0, "hit1": 0, "hit3": 1, "id": "I1", "negative_kind": null, "returned": 3, "rr3": 0.5, "split": "dev"} | {"answerable": true, "category": "distractors", "documents": ["A", "H", "B"], "duplicates": 0, "hit1": 1, "hit3": 1, "id": "I1", "negative_kind": null, "returned": 3, "rr3": 1.0, "split": "dev"} |
| N1 | {"answerable": false, "category": "no_answer", "documents": [], "duplicates": 0, "hit1": 0, "hit3": 0, "id": "N1", "negative_kind": "lexical_absence", "returned": 0, "rr3": 0, "split": "dev"} | {"answerable": false, "category": "no_answer", "documents": ["F"], "duplicates": 0, "hit1": 0, "hit3": 0, "id": "N1", "negative_kind": "lexical_absence", "returned": 1, "rr3": 0, "split": "dev"} |
| A2 | {"answerable": true, "category": "adversarial", "documents": ["I", "J", "A"], "duplicates": 0, "hit1": 0, "hit3": 1, "id": "A2", "negative_kind": null, "returned": 3, "rr3": 0.5, "split": "holdout"} | {"answerable": true, "category": "adversarial", "documents": ["J", "I", "A"], "duplicates": 0, "hit1": 1, "hit3": 1, "id": "A2", "negative_kind": null, "returned": 3, "rr3": 1.0, "split": "holdout"} |

Every B->C change (0):

| Case | Before | After |
| --- | --- | --- |

### M7

| Arm | Original evaluator overall results |
| --- | --- |
| A | {"answerable": 22, "cases": 32, "duplicate_slots": 0, "hit1": 0.8181818181818182, "hit3": 0.9545454545454546, "mrr3": 0.8863636363636364, "negative_nonempty": 5} |
| B | {"answerable": 22, "cases": 32, "duplicate_slots": 0, "hit1": 0.7272727272727273, "hit3": 0.9545454545454546, "mrr3": 0.8333333333333333, "negative_nonempty": 6} |
| C | {"answerable": 22, "cases": 32, "duplicate_slots": 0, "hit1": 0.7272727272727273, "hit3": 0.9545454545454546, "mrr3": 0.8333333333333333, "negative_nonempty": 6} |

Every A->B change (19):

| Case | Before | After |
| --- | --- | --- |
| identity_1 | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_1", "paths": ["src/loans.py", "DWINDY.md", "README.md"], "rank": 2, "returned": 3, "split": "dev"} | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_1", "paths": ["DWINDY.md", "src/loans.py", "README.md"], "rank": 1, "returned": 3, "split": "dev"} |
| identity_3 | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_3", "paths": ["README.md", "config/reference.toml", "@project/overview"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_3", "paths": ["README.md", "config/reference.toml", "DWINDY.md"], "rank": 1, "returned": 3, "split": "dev"} |
| identity_4 | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_4", "paths": ["README.md", "docs/tasks/reservations.md", "config/reference.toml"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_4", "paths": ["README.md", "docs/tasks/reservations.md", "src/loans.py"], "rank": 1, "returned": 3, "split": "holdout"} |
| workflow_2 | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_2", "paths": ["docs/tasks/reservations.md", "docs/policy.md", "DWINDY.md"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_2", "paths": ["docs/tasks/reservations.md", "@project/metadata", "docs/policy.md"], "rank": 1, "returned": 3, "split": "holdout"} |
| workflow_3 | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_3", "paths": ["docs/nested/README.md"], "rank": 1, "returned": 1, "split": "dev"} | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_3", "paths": ["docs/nested/README.md", "src/loans.py", "DWINDY.md"], "rank": 1, "returned": 3, "split": "dev"} |
| workflow_4 | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_4", "paths": ["web/returns.ts", "README.md", "web/returns.ts"], "rank": 2, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_4", "paths": ["docs/nested/README.md", "src/loans.py", "web/returns.ts"], "rank": null, "returned": 3, "split": "holdout"} |
| location_1 | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_1", "paths": ["@project/metadata", "src/loans.py", "README.md"], "rank": 2, "returned": 3, "split": "dev"} | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_1", "paths": ["@project/metadata", "web/returns.ts", "src/loans.py"], "rank": 3, "returned": 3, "split": "dev"} |
| location_2 | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_2", "paths": ["src/admin/settings.py", "src/admin/settings.py", "@project/metadata"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_2", "paths": ["src/admin/settings.py", "src/admin/settings.py", "web/returns.ts"], "rank": 2, "returned": 3, "split": "holdout"} |
| location_3 | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_3", "paths": ["src/public/settings.py", "src/public/settings.py", "@project/metadata"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_3", "paths": ["src/public/settings.py", "src/public/settings.py", "web/returns.ts"], "rank": 2, "returned": 3, "split": "dev"} |
| location_4 | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_4", "paths": ["web/returns.ts", "@project/metadata"], "rank": 1, "returned": 2, "split": "holdout"} | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_4", "paths": ["web/returns.ts", "web/returns.ts", "@project/metadata"], "rank": 1, "returned": 3, "split": "holdout"} |
| configuration_1 | {"answerable": true, "category": "configuration", "duplicates": 0, "id": "configuration_1", "paths": ["config/reference.toml", "docs/tasks/reservations.md", "src/public/settings.py"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "configuration", "duplicates": 0, "id": "configuration_1", "paths": ["config/reference.toml", "src/public/settings.py", "src/admin/settings.py"], "rank": 1, "returned": 3, "split": "dev"} |
| configuration_3 | {"answerable": true, "category": "configuration", "duplicates": 0, "id": "configuration_3", "paths": ["docs/policy.md", "src/loans.py"], "rank": 1, "returned": 2, "split": "dev"} | {"answerable": true, "category": "configuration", "duplicates": 0, "id": "configuration_3", "paths": ["docs/policy.md", "src/loans.py", "src/loans.py"], "rank": 1, "returned": 3, "split": "dev"} |
| rationale_1 | {"answerable": true, "category": "rationale", "duplicates": 0, "id": "rationale_1", "paths": ["DWINDY.md", "src/admin/settings.py", "src/admin/settings.py"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "rationale", "duplicates": 0, "id": "rationale_1", "paths": ["DWINDY.md", "src/admin/settings.py", "docs/tasks/reservations.md"], "rank": 1, "returned": 3, "split": "dev"} |
| rationale_2 | {"answerable": true, "category": "rationale", "duplicates": 0, "id": "rationale_2", "paths": ["docs/policy.md", "src/loans.py", "README.md"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "rationale", "duplicates": 0, "id": "rationale_2", "paths": ["src/loans.py", "docs/policy.md", "README.md"], "rank": 2, "returned": 3, "split": "holdout"} |
| adversarial_1 | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_1", "paths": ["docs/tasks/reservations.md"], "rank": null, "returned": 1, "split": "dev"} | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_1", "paths": ["DWINDY.md", "src/loans.py", "docs/tasks/reservations.md"], "rank": 1, "returned": 3, "split": "dev"} |
| adversarial_2 | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_2", "paths": ["DWINDY.md", "@project/overview", "config/reference.toml"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_2", "paths": ["@project/overview", "DWINDY.md", "config/reference.toml"], "rank": 2, "returned": 3, "split": "holdout"} |
| adversarial_3 | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_3", "paths": ["src/admin/settings.py", "src/admin/settings.py", "src/public/settings.py"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_3", "paths": ["src/admin/settings.py", "src/admin/settings.py", "docs/nested/README.md"], "rank": 1, "returned": 3, "split": "dev"} |
| adversarial_4 | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_4", "paths": ["docs/nested/README.md", "README.md"], "rank": 1, "returned": 2, "split": "holdout"} | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_4", "paths": ["docs/nested/README.md", "DWINDY.md", "README.md"], "rank": 1, "returned": 3, "split": "holdout"} |
| excluded_3 | {"answerable": false, "category": "excluded", "duplicates": 0, "id": "excluded_3", "paths": [], "rank": null, "returned": 0, "split": "dev"} | {"answerable": false, "category": "excluded", "duplicates": 0, "id": "excluded_3", "paths": ["DWINDY.md"], "rank": null, "returned": 1, "split": "dev"} |

Every A->C change (19):

| Case | Before | After |
| --- | --- | --- |
| identity_1 | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_1", "paths": ["src/loans.py", "DWINDY.md", "README.md"], "rank": 2, "returned": 3, "split": "dev"} | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_1", "paths": ["DWINDY.md", "src/loans.py", "README.md"], "rank": 1, "returned": 3, "split": "dev"} |
| identity_3 | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_3", "paths": ["README.md", "config/reference.toml", "@project/overview"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_3", "paths": ["README.md", "config/reference.toml", "DWINDY.md"], "rank": 1, "returned": 3, "split": "dev"} |
| identity_4 | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_4", "paths": ["README.md", "docs/tasks/reservations.md", "config/reference.toml"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "identity", "duplicates": 0, "id": "identity_4", "paths": ["README.md", "docs/tasks/reservations.md", "src/loans.py"], "rank": 1, "returned": 3, "split": "holdout"} |
| workflow_2 | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_2", "paths": ["docs/tasks/reservations.md", "docs/policy.md", "DWINDY.md"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_2", "paths": ["docs/tasks/reservations.md", "@project/metadata", "docs/policy.md"], "rank": 1, "returned": 3, "split": "holdout"} |
| workflow_3 | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_3", "paths": ["docs/nested/README.md"], "rank": 1, "returned": 1, "split": "dev"} | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_3", "paths": ["docs/nested/README.md", "src/loans.py", "DWINDY.md"], "rank": 1, "returned": 3, "split": "dev"} |
| workflow_4 | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_4", "paths": ["web/returns.ts", "README.md", "web/returns.ts"], "rank": 2, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "workflow", "duplicates": 0, "id": "workflow_4", "paths": ["docs/nested/README.md", "src/loans.py", "web/returns.ts"], "rank": null, "returned": 3, "split": "holdout"} |
| location_1 | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_1", "paths": ["@project/metadata", "src/loans.py", "README.md"], "rank": 2, "returned": 3, "split": "dev"} | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_1", "paths": ["@project/metadata", "web/returns.ts", "src/loans.py"], "rank": 3, "returned": 3, "split": "dev"} |
| location_2 | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_2", "paths": ["src/admin/settings.py", "src/admin/settings.py", "@project/metadata"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_2", "paths": ["src/admin/settings.py", "src/admin/settings.py", "web/returns.ts"], "rank": 2, "returned": 3, "split": "holdout"} |
| location_3 | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_3", "paths": ["src/public/settings.py", "src/public/settings.py", "@project/metadata"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_3", "paths": ["src/public/settings.py", "src/public/settings.py", "web/returns.ts"], "rank": 2, "returned": 3, "split": "dev"} |
| location_4 | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_4", "paths": ["web/returns.ts", "@project/metadata"], "rank": 1, "returned": 2, "split": "holdout"} | {"answerable": true, "category": "location", "duplicates": 0, "id": "location_4", "paths": ["web/returns.ts", "web/returns.ts", "@project/metadata"], "rank": 1, "returned": 3, "split": "holdout"} |
| configuration_1 | {"answerable": true, "category": "configuration", "duplicates": 0, "id": "configuration_1", "paths": ["config/reference.toml", "docs/tasks/reservations.md", "src/public/settings.py"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "configuration", "duplicates": 0, "id": "configuration_1", "paths": ["config/reference.toml", "src/public/settings.py", "src/admin/settings.py"], "rank": 1, "returned": 3, "split": "dev"} |
| configuration_3 | {"answerable": true, "category": "configuration", "duplicates": 0, "id": "configuration_3", "paths": ["docs/policy.md", "src/loans.py"], "rank": 1, "returned": 2, "split": "dev"} | {"answerable": true, "category": "configuration", "duplicates": 0, "id": "configuration_3", "paths": ["docs/policy.md", "src/loans.py", "src/loans.py"], "rank": 1, "returned": 3, "split": "dev"} |
| rationale_1 | {"answerable": true, "category": "rationale", "duplicates": 0, "id": "rationale_1", "paths": ["DWINDY.md", "src/admin/settings.py", "src/admin/settings.py"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "rationale", "duplicates": 0, "id": "rationale_1", "paths": ["DWINDY.md", "src/admin/settings.py", "docs/tasks/reservations.md"], "rank": 1, "returned": 3, "split": "dev"} |
| rationale_2 | {"answerable": true, "category": "rationale", "duplicates": 0, "id": "rationale_2", "paths": ["docs/policy.md", "src/loans.py", "README.md"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "rationale", "duplicates": 0, "id": "rationale_2", "paths": ["src/loans.py", "docs/policy.md", "README.md"], "rank": 2, "returned": 3, "split": "holdout"} |
| adversarial_1 | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_1", "paths": ["docs/tasks/reservations.md"], "rank": null, "returned": 1, "split": "dev"} | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_1", "paths": ["DWINDY.md", "src/loans.py", "docs/tasks/reservations.md"], "rank": 1, "returned": 3, "split": "dev"} |
| adversarial_2 | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_2", "paths": ["DWINDY.md", "@project/overview", "config/reference.toml"], "rank": 1, "returned": 3, "split": "holdout"} | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_2", "paths": ["@project/overview", "DWINDY.md", "config/reference.toml"], "rank": 2, "returned": 3, "split": "holdout"} |
| adversarial_3 | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_3", "paths": ["src/admin/settings.py", "src/admin/settings.py", "src/public/settings.py"], "rank": 1, "returned": 3, "split": "dev"} | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_3", "paths": ["src/admin/settings.py", "src/admin/settings.py", "docs/nested/README.md"], "rank": 1, "returned": 3, "split": "dev"} |
| adversarial_4 | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_4", "paths": ["docs/nested/README.md", "README.md"], "rank": 1, "returned": 2, "split": "holdout"} | {"answerable": true, "category": "adversarial", "duplicates": 0, "id": "adversarial_4", "paths": ["docs/nested/README.md", "DWINDY.md", "README.md"], "rank": 1, "returned": 3, "split": "holdout"} |
| excluded_3 | {"answerable": false, "category": "excluded", "duplicates": 0, "id": "excluded_3", "paths": [], "rank": null, "returned": 0, "split": "dev"} | {"answerable": false, "category": "excluded", "duplicates": 0, "id": "excluded_3", "paths": ["DWINDY.md"], "rank": null, "returned": 1, "split": "dev"} |

Every B->C change (0):

| Case | Before | After |
| --- | --- | --- |

### M8

| Arm | Original evaluator overall results |
| --- | --- |
| A | {"accuracy": 0.9615384615384616, "attempt_precision": 0.6052631578947368, "attempt_recall": 1.0, "cases": 56, "english_cases": 52, "general_false_supply": 0, "gold_coverage": 1.0, "honest_path": 4, "missed_context": 1, "multilingual_correct": 0, "overlap_false_supply": 1, "policy_errors": 0, "strict_false_supply": 0} |
| B | {"accuracy": 0.9615384615384616, "attempt_precision": 0.6052631578947368, "attempt_recall": 1.0, "cases": 56, "english_cases": 52, "general_false_supply": 0, "gold_coverage": 1.0, "honest_path": 4, "missed_context": 1, "multilingual_correct": 0, "overlap_false_supply": 1, "policy_errors": 0, "strict_false_supply": 0} |
| C | {"accuracy": 0.9807692307692307, "attempt_precision": 0.6052631578947368, "attempt_recall": 1.0, "cases": 56, "english_cases": 52, "general_false_supply": 0, "gold_coverage": 1.0, "honest_path": 4, "missed_context": 0, "multilingual_correct": 0, "overlap_false_supply": 1, "policy_errors": 0, "strict_false_supply": 0} |

Every A->B change (13):

| Case | Before | After |
| --- | --- | --- |
| explicit_project_1 | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_1", "outcome": "context", "reason": "project_directed", "source_paths": ["src/loans.py", "DWINDY.md", "README.md"], "split": "dev"} | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_1", "outcome": "context", "reason": "project_directed", "source_paths": ["DWINDY.md", "src/loans.py", "README.md"], "split": "dev"} |
| explicit_project_3 | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_3", "outcome": "context", "reason": "project_directed", "source_paths": ["docs/policy.md", "src/loans.py", "docs/nested/README.md"], "split": "dev"} | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_3", "outcome": "context", "reason": "project_directed", "source_paths": ["docs/policy.md", "DWINDY.md", "docs/nested/README.md"], "split": "dev"} |
| explicit_project_4 | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_4", "outcome": "context", "reason": "project_directed", "source_paths": ["README.md", "docs/tasks/reservations.md", "config/reference.toml"], "split": "holdout"} | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_4", "outcome": "context", "reason": "project_directed", "source_paths": ["README.md", "docs/tasks/reservations.md", "src/loans.py"], "split": "holdout"} |
| implicit_project_3 | {"attempted": true, "category": "implicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "implicit_project_3", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/nested/README.md", "weather.md", "notice.md"], "split": "dev"} | {"attempted": true, "category": "implicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "implicit_project_3", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/nested/README.md", "README.md", "weather.md"], "split": "dev"} |
| location_1 | {"attempted": true, "category": "location", "correct": true, "expected": "context", "gold_supplied": true, "id": "location_1", "outcome": "context", "reason": "relevant_match", "source_paths": ["web/returns.ts", "web/returns.ts", "README.md"], "split": "dev"} | {"attempted": true, "category": "location", "correct": true, "expected": "context", "gold_supplied": true, "id": "location_1", "outcome": "context", "reason": "relevant_match", "source_paths": ["web/returns.ts", "web/returns.ts", "src/public/settings.py"], "split": "dev"} |
| location_4 | {"attempted": true, "category": "location", "correct": true, "expected": "context", "gold_supplied": true, "id": "location_4", "outcome": "context", "reason": "relevant_match", "source_paths": ["config/reference.toml", "docs/tasks/reservations.md", "src/public/settings.py"], "split": "holdout"} | {"attempted": true, "category": "location", "correct": true, "expected": "context", "gold_supplied": true, "id": "location_4", "outcome": "context", "reason": "relevant_match", "source_paths": ["config/reference.toml", "src/public/settings.py", "src/admin/settings.py"], "split": "holdout"} |
| rationale_1 | {"attempted": true, "category": "rationale", "correct": true, "expected": "context", "gold_supplied": true, "id": "rationale_1", "outcome": "context", "reason": "relevant_match", "source_paths": ["DWINDY.md", "src/admin/settings.py", "docs/policy.md"], "split": "dev"} | {"attempted": true, "category": "rationale", "correct": true, "expected": "context", "gold_supplied": true, "id": "rationale_1", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/nested/README.md", "DWINDY.md", "docs/policy.md"], "split": "dev"} |
| rationale_2 | {"attempted": true, "category": "rationale", "correct": true, "expected": "context", "gold_supplied": true, "id": "rationale_2", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/policy.md", "src/loans.py", "glossary.md"], "split": "holdout"} | {"attempted": true, "category": "rationale", "correct": true, "expected": "context", "gold_supplied": true, "id": "rationale_2", "outcome": "context", "reason": "relevant_match", "source_paths": ["src/loans.py", "docs/policy.md", "glossary.md"], "split": "holdout"} |
| project_unavailable_2 | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_2", "outcome": "context", "reason": "project_directed", "source_paths": ["src/loans.py", "DWINDY.md", "README.md"], "split": "holdout"} | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_2", "outcome": "context", "reason": "project_directed", "source_paths": ["config/reference.toml", "src/loans.py", "DWINDY.md"], "split": "holdout"} |
| project_unavailable_3 | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_3", "outcome": "context", "reason": "project_directed", "source_paths": ["docs/nested/README.md", "notice.md", "src/loans.py"], "split": "dev"} | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_3", "outcome": "context", "reason": "project_directed", "source_paths": ["docs/nested/README.md", "notice.md", "README.md"], "split": "dev"} |
| project_unavailable_4 | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_4", "outcome": "context", "reason": "project_directed", "source_paths": ["src/public/settings.py", "src/admin/settings.py", "web/returns.ts"], "split": "holdout"} | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_4", "outcome": "context", "reason": "project_directed", "source_paths": ["web/returns.ts", "web/returns.ts", "README.md"], "split": "holdout"} |
| accidental_overlap_3 | {"attempted": true, "category": "accidental_overlap", "correct": true, "expected": "direct", "gold_supplied": null, "id": "accidental_overlap_3", "outcome": "direct", "reason": "no_candidates", "source_paths": [], "split": "dev"} | {"attempted": true, "category": "accidental_overlap", "correct": true, "expected": "direct", "gold_supplied": null, "id": "accidental_overlap_3", "outcome": "direct", "reason": "weak_match", "source_paths": [], "split": "dev"} |
| adversarial_3 | {"attempted": true, "category": "adversarial", "correct": true, "expected": "guided", "gold_supplied": null, "id": "adversarial_3", "outcome": "context", "reason": "project_directed", "source_paths": ["events.md", "@project/overview", "@project/metadata"], "split": "dev"} | {"attempted": true, "category": "adversarial", "correct": true, "expected": "guided", "gold_supplied": null, "id": "adversarial_3", "outcome": "context", "reason": "project_directed", "source_paths": ["events.md", "DWINDY.md", "@project/overview"], "split": "dev"} |

Every A->C change (14):

| Case | Before | After |
| --- | --- | --- |
| explicit_project_1 | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_1", "outcome": "context", "reason": "project_directed", "source_paths": ["src/loans.py", "DWINDY.md", "README.md"], "split": "dev"} | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_1", "outcome": "context", "reason": "project_directed", "source_paths": ["DWINDY.md", "src/loans.py", "README.md"], "split": "dev"} |
| explicit_project_3 | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_3", "outcome": "context", "reason": "project_directed", "source_paths": ["docs/policy.md", "src/loans.py", "docs/nested/README.md"], "split": "dev"} | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_3", "outcome": "context", "reason": "project_directed", "source_paths": ["docs/policy.md", "DWINDY.md", "docs/nested/README.md"], "split": "dev"} |
| explicit_project_4 | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_4", "outcome": "context", "reason": "project_directed", "source_paths": ["README.md", "docs/tasks/reservations.md", "config/reference.toml"], "split": "holdout"} | {"attempted": true, "category": "explicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "explicit_project_4", "outcome": "context", "reason": "project_directed", "source_paths": ["README.md", "docs/tasks/reservations.md", "src/loans.py"], "split": "holdout"} |
| implicit_project_3 | {"attempted": true, "category": "implicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "implicit_project_3", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/nested/README.md", "weather.md", "notice.md"], "split": "dev"} | {"attempted": true, "category": "implicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "implicit_project_3", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/nested/README.md", "README.md", "weather.md"], "split": "dev"} |
| implicit_project_4 | {"attempted": true, "category": "implicit_project", "correct": false, "expected": "context", "gold_supplied": false, "id": "implicit_project_4", "outcome": "direct", "reason": "weak_match", "source_paths": [], "split": "holdout"} | {"attempted": true, "category": "implicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "implicit_project_4", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/tasks/reservations.md", "DWINDY.md", "src/loans.py"], "split": "holdout"} |
| location_1 | {"attempted": true, "category": "location", "correct": true, "expected": "context", "gold_supplied": true, "id": "location_1", "outcome": "context", "reason": "relevant_match", "source_paths": ["web/returns.ts", "web/returns.ts", "README.md"], "split": "dev"} | {"attempted": true, "category": "location", "correct": true, "expected": "context", "gold_supplied": true, "id": "location_1", "outcome": "context", "reason": "relevant_match", "source_paths": ["web/returns.ts", "web/returns.ts", "src/public/settings.py"], "split": "dev"} |
| location_4 | {"attempted": true, "category": "location", "correct": true, "expected": "context", "gold_supplied": true, "id": "location_4", "outcome": "context", "reason": "relevant_match", "source_paths": ["config/reference.toml", "docs/tasks/reservations.md", "src/public/settings.py"], "split": "holdout"} | {"attempted": true, "category": "location", "correct": true, "expected": "context", "gold_supplied": true, "id": "location_4", "outcome": "context", "reason": "relevant_match", "source_paths": ["config/reference.toml", "src/public/settings.py", "src/admin/settings.py"], "split": "holdout"} |
| rationale_1 | {"attempted": true, "category": "rationale", "correct": true, "expected": "context", "gold_supplied": true, "id": "rationale_1", "outcome": "context", "reason": "relevant_match", "source_paths": ["DWINDY.md", "src/admin/settings.py", "docs/policy.md"], "split": "dev"} | {"attempted": true, "category": "rationale", "correct": true, "expected": "context", "gold_supplied": true, "id": "rationale_1", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/nested/README.md", "DWINDY.md", "docs/policy.md"], "split": "dev"} |
| rationale_2 | {"attempted": true, "category": "rationale", "correct": true, "expected": "context", "gold_supplied": true, "id": "rationale_2", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/policy.md", "src/loans.py", "glossary.md"], "split": "holdout"} | {"attempted": true, "category": "rationale", "correct": true, "expected": "context", "gold_supplied": true, "id": "rationale_2", "outcome": "context", "reason": "relevant_match", "source_paths": ["src/loans.py", "docs/policy.md", "glossary.md"], "split": "holdout"} |
| project_unavailable_2 | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_2", "outcome": "context", "reason": "project_directed", "source_paths": ["src/loans.py", "DWINDY.md", "README.md"], "split": "holdout"} | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_2", "outcome": "context", "reason": "project_directed", "source_paths": ["config/reference.toml", "src/loans.py", "DWINDY.md"], "split": "holdout"} |
| project_unavailable_3 | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_3", "outcome": "context", "reason": "project_directed", "source_paths": ["docs/nested/README.md", "notice.md", "src/loans.py"], "split": "dev"} | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_3", "outcome": "context", "reason": "project_directed", "source_paths": ["docs/nested/README.md", "notice.md", "README.md"], "split": "dev"} |
| project_unavailable_4 | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_4", "outcome": "context", "reason": "project_directed", "source_paths": ["src/public/settings.py", "src/admin/settings.py", "web/returns.ts"], "split": "holdout"} | {"attempted": true, "category": "project_unavailable", "correct": true, "expected": "guided", "gold_supplied": null, "id": "project_unavailable_4", "outcome": "context", "reason": "project_directed", "source_paths": ["web/returns.ts", "web/returns.ts", "README.md"], "split": "holdout"} |
| accidental_overlap_3 | {"attempted": true, "category": "accidental_overlap", "correct": true, "expected": "direct", "gold_supplied": null, "id": "accidental_overlap_3", "outcome": "direct", "reason": "no_candidates", "source_paths": [], "split": "dev"} | {"attempted": true, "category": "accidental_overlap", "correct": true, "expected": "direct", "gold_supplied": null, "id": "accidental_overlap_3", "outcome": "direct", "reason": "weak_match", "source_paths": [], "split": "dev"} |
| adversarial_3 | {"attempted": true, "category": "adversarial", "correct": true, "expected": "guided", "gold_supplied": null, "id": "adversarial_3", "outcome": "context", "reason": "project_directed", "source_paths": ["events.md", "@project/overview", "@project/metadata"], "split": "dev"} | {"attempted": true, "category": "adversarial", "correct": true, "expected": "guided", "gold_supplied": null, "id": "adversarial_3", "outcome": "context", "reason": "project_directed", "source_paths": ["events.md", "DWINDY.md", "@project/overview"], "split": "dev"} |

Every B->C change (1):

| Case | Before | After |
| --- | --- | --- |
| implicit_project_4 | {"attempted": true, "category": "implicit_project", "correct": false, "expected": "context", "gold_supplied": false, "id": "implicit_project_4", "outcome": "direct", "reason": "weak_match", "source_paths": [], "split": "holdout"} | {"attempted": true, "category": "implicit_project", "correct": true, "expected": "context", "gold_supplied": true, "id": "implicit_project_4", "outcome": "context", "reason": "relevant_match", "source_paths": ["docs/tasks/reservations.md", "DWINDY.md", "src/loans.py"], "split": "holdout"} |

M6 Porter improves Hit@1 15/20→17/20 but adds one negative nonempty retrieval; M7 Hit@1 declines 18/22→16/22 and adds one negative nonempty retrieval. Hit@3 stays 19/20 and 21/22 respectively. M8 C fixes implicit_project_4; B does not. Existing accidental_overlap_2 false supply and all four multilingual failures remain. The only historical acceptance gate is no NEW M8 direct/acceptable false supply: passed B/C. Other historical gains/regressions neither rescue nor reject the fresh acceptance result.

## Performance and resource measurements

Frozen workload: 1,000 documents, 9,829,000 logical UTF-8 bytes, 10,000 paragraph blocks; five isolated processes per arm, 200 identically permuted warm queries per trial (1,000 per arm). Build includes ingest/chunk/insert/commit; fixture generation precedes baseline/timing. RSS sampled every 10 ms; short peaks may be missed. No outliers/trials removed. All timings below are model-free. Actual C normalization is charged; audit-only replay/probes/serialization/IPC are excluded. Timing wrappers add small common instrumentation overhead. Inclusive columns nest normalization and must not be added together.

| Component | A p50/p95/max ms | B p50/p95/max ms | C p50/p95/max ms |
| --- | --- | --- | --- |
| complete_selection | 13.7782 / 28.0689 / 37.4321 | 15.1516 / 31.2527 / 39.8240 | 16.2126 / 33.9860 / 52.5711 |
| core_packet | 0.2397 / 0.5847 / 1.0759 | 0.2439 / 0.6492 / 1.1278 | 0.2409 / 0.6583 / 2.3511 |
| fts_query_construction | 0.0053 / 0.0131 / 0.0523 | 0.0053 / 0.0136 / 0.0408 | 0.0055 / 0.0158 / 0.1397 |
| policy_query_terms | 0.0053 / 0.0142 / 0.2541 | 0.0053 / 0.0137 / 0.2189 | 0.0049 / 0.0134 / 0.1043 |
| porter_normalization | 0.0000 / 0.0000 / 0.0000 | 0.0000 / 0.0000 / 0.0000 | 0.4467 / 1.2096 / 1.9989 |
| query_normalization | 0.0106 / 0.0266 / 0.2820 | 0.0107 / 0.0267 / 0.2360 | 0.0103 / 0.0287 / 0.1798 |
| search_exclusive | 13.3626 / 27.2533 / 36.8166 | 14.7427 / 30.5487 / 39.1903 | 15.2084 / 31.8945 / 47.3205 |
| search_inclusive | 13.3694 / 27.2624 / 36.8217 | 14.7476 / 30.5654 / 39.1954 | 15.2142 / 31.8997 / 47.3516 |
| usefulness_exclusive | 0.0609 / 0.1195 / 0.3162 | 0.0619 / 0.1323 / 0.5463 | 0.1842 / 0.4452 / 0.7323 |
| usefulness_inclusive | 0.0609 / 0.1195 / 0.3162 | 0.0619 / 0.1323 / 0.5463 | 0.6309 / 1.6404 / 2.6295 |

| Resource (median of five) | A | B | C |
| --- | --- | --- | --- |
| build_seconds | 0.4343 | 0.4343 | 0.4340 |
| index_bytes | 16084992.0000 | 15622144.0000 | 15622144.0000 |
| rss_increment_bytes | 4972544.0000 | 4988928.0000 | 5074944.0000 |
| startup_median_ms | 113.5680 | 139.6555 | 136.6791 |
| first_query_median_ms | 12.4829 | 11.7868 | 13.5917 |
| max_build_seconds | 0.4403 | 0.4483 | 0.4639 |
| max_rss_increment_bytes | 5025792.0000 | 5103616.0000 | 5271552.0000 |

Porter FTS normalization occurs inside SQLite search/indexing and cannot be separately timed here; query_normalization measures deterministic query-term/MATCH construction. C porter_normalization is additional scratch FTS/fts5vocab coverage work, already contained in usefulness_inclusive. Startup includes fresh connection/schema validation, quick/foreign-key checks and scratch setup; frozen ReferenceIndex initializes the scratch normalizer for all arms, including A/B. First query follows indexing with warm OS cache: it is not cold-disk latency. Isolated process startup before opening is outside startup_ms. No Qwen tokenizer, TTFT or generation measurement is claimed; the frozen UTF-8-quarter token oracle is used identically for all arms.

| Trial/arm | Build s | Bytes/chunks | Increment RSS bytes | Startup ms | First full selection ms |
| --- | --- | --- | --- | --- | --- |
| 1/A | 0.434302 | 16084992/10000 | 4993024 | 121.1236 | 14.7807 |
| 1/B | 0.428209 | 15622144/10000 | 5103616 | 144.2091 | 11.5654 |
| 1/C | 0.444600 | 15622144/10000 | 5271552 | 175.2628 | 14.6234 |
| 2/A | 0.440327 | 16084992/10000 | 4816896 | 113.5680 | 13.2878 |
| 2/B | 0.448291 | 15622144/10000 | 4980736 | 137.3126 | 11.4382 |
| 2/C | 0.463922 | 15622144/10000 | 5218304 | 136.6791 | 13.6373 |
| 3/A | 0.439477 | 16084992/10000 | 4861952 | 110.6244 | 12.1604 |
| 3/B | 0.428668 | 15622144/10000 | 4972544 | 140.0022 | 12.4131 |
| 3/C | 0.432853 | 15622144/10000 | 5074944 | 136.4410 | 12.6591 |
| 4/A | 0.407541 | 16084992/10000 | 4972544 | 114.7692 | 12.3190 |
| 4/B | 0.434296 | 15622144/10000 | 5058560 | 139.6555 | 14.2650 |
| 4/C | 0.433967 | 15622144/10000 | 4997120 | 137.1817 | 13.5917 |
| 5/A | 0.416188 | 16084992/10000 | 5025792 | 113.4885 | 12.4829 |
| 5/B | 0.437740 | 15622144/10000 | 4988928 | 138.6088 | 11.7868 |
| 5/C | 0.420202 | 15622144/10000 | 5046272 | 132.2846 | 13.0649 |

All 15 Windows trials closed connections and successfully renamed/deleted the index and removed temporary folders. Index is 16084992 bytes A versus 15622144 bytes B/C. Median incremental RSS C−A is 102400 bytes, well below +8 MiB.

## Integrity, artifacts and disposition

The frozen evaluator/fixtures/gates were used unchanged; production and 149 historical artifact hashes verified. No thresholds, term selection, stopwords, ranking, tokenizer parameters, language/synonym handling or fixtures were tuned. New artifacts exist only under ignored eval-results/morphology-dev-01/. Existing untracked frozen evaluation directory and sibling fixture-validation harness remain unstaged; no tracked changes. Artifact manifest lists hashes of every run output. Regression results are recorded separately in validation.json.

The experiment demonstrates both lexical bottlenecks, but fails adoption. Stop this morphology line, retain development evidence, and leave production unchanged. No candidate freeze or holdout request is recommended.
