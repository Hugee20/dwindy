# Frozen Project Awareness evaluation v1

Freeze before scanner, project chunking or ranking implementation. files.json is a map
of logical host paths to synthetic UTF-8 contents; it includes excluded canaries safely
as JSON values, not live credential files. Tests materialize it into a temporary root.
policy.json defines explicit permission, discovery.json exact expected content selections,
policy/metadata reads and forbidden output. lifecycle.json defines snapshot B relative to A.

32 queries: four each identity, workflow, location, configuration, rationale, adversarial,
excluded, unavailable. Odd cases development, even holdout: 16/16. 22 answerable (11/11).
Rationale 3/4 and excluded/unavailable cases have no answer-bearing material. Misleading
instruction questions ask about quoted text, never executing it.

Gold spans are half-open Unicode offsets in LF-normalized original files. A hit must cover
an entire gold span at its correct project-relative path. Hit@1/Hit@3 and MRR@3 count only
answerable cases. Missing fields may produce related matches and are reported separately.
unavailable_3/4 require empty lexical results. Duplicate slots repeat exact passage text.
The evaluator takes search(query) -> ranked mappings with source_path,start,end,text.
It never calls a model and makes no generation-correctness claim.

Discovery precision and recall compare selected original-content paths against the exact
allowlist; metadata inputs and policy inputs are separately authorized reads. Excluded
contents must never be opened or appear in index/overview/evidence. All forbidden canaries
must be absent from persisted/generated/retrieved text. Policy and file references cannot
expand permission. Expected overview contains only observational selected structure.

Snapshot B: update policy eight to nine days, delete calibration README, add silver-register
procedure, newly ignore tasks, retain unchanged source chunk IDs. Failed sync must preserve
all snapshot A content/metadata. Source spans must identify exact original substrings.

Gates: 100% fixture discovery precision/recall and span accuracy; zero excluded content
reads/leaks; Hit@3 >= .85; MRR@3 >= .70; unavailable_3/4 empty; zero duplicate slots.
Report every rank-1 miss, category, split and negative nonempty result. Do not tune ranking
on either split: preserve M6 ranking. Source chunking changes may use development only;
holdout is evaluated after design stabilizes. Future benchmark changes require a new version.

Resource targets: separate bounded scale fixture, sync <30 s, warm p95 retrieval <100 ms,
isolated added RSS <64 MiB on the reference-class machine. Report actual measurements,
OS-cache conditions, index size and model timings separately. These are provisional targets.

FREEZE.json hashes all files in this directory except itself. Historical M1/M6 are untouched.
