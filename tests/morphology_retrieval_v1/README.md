# Morphology retrieval v1: separate, evaluation-first hypothesis

Status: constructed/frozen for fixture review only. No relevance split or scale
performance run has been executed. No production change or dependency is adopted.
The corpus was authored after M6-M8 development/holdout failure reports were known.
Historical cases are diagnostics, not new acceptance credit. Nothing supersedes
their frozen datasets, algorithms, gates or reported results.

Hypothesis: English morphology-aware matching can improve final useful-context
recall without increasing accidental supply. Stemming is not semantic matching,
answerability detection, translation, factual verification or generation correctness.
Original M11 and Foundation holdouts remain sealed/unspent. Reach/H2 is untouched.

## Arms and boundaries

* A: current unicode61 FTS + unmodified exact-word usefulness.
* B: porter unicode61 FTS + unmodified exact-word usefulness.
* C: porter unicode61 FTS + equivalent SQLite-derived Porter usefulness coverage.

All arms share documents, chunking, source metadata, weights (2/2/1), quoted OR
queries, 32 original unique non-stopword query terms, 12 candidates, duplicate and
overlap suppression, top-three usefulness window, 50% threshold, generated-summary
exclusions and Core's existing evidence handling. No cue, synonym, threshold,
ranking, budget or prompt tuning. Tokenization changes may change BM25 lengths and
ties; those are measured consequences, not manually adjusted rankings.

Only reference.py changes evaluation-owned namespaces. The original writer is
hash-pinned and cloned into an isolated namespace with only the FTS declaration
changed; existing databases are refused. Production globals are not patched.
The production search method and decision function are reused. C substitutes
only the usefulness callback in a cloned decision function's isolated globals.
This is reference machinery, never an application import. Corpus source_type
alternates project_document/local_text; no project scanning is part of this study.

PorterTokens owns a separate in-memory FTS5/fts5vocab(instance) connection. Bound:
128 input strings and 32,768 UTF-8 bytes per batch, with no retained scratch rows.
Only body, heading and path tokens enter usefulness, matching M8. Query stopwords,
order and original distinct-term denominator are unchanged. Different original
terms with one stem remain separately counted; repeated passage tokens do not add
credit. Empty normalized terms do not match. Native unicode61 diacritic handling
is disclosed: C also differs from Python word matching there; non-English changes
never count toward English morphology gain.

## Fresh composition and sealing

96 cases, 48 development + 48 holdout: six per category per split. Categories:
inflection, derivation, exact_identifier, collision, accidental_overlap,
ordinary_control, synonym, filipino_taglish. There are 96 small UTF-8 Markdown/text
documents, 48 per split, with separate manifests/index inputs. Development searches
only development sources. No candidate obtains holdout passages through a shared
index. Each split has 36 acceptance rows (12 morphology, 6 exact, 18 controls)
and 12 diagnostic-only rows (6 synonym/paraphrase, 6 Filipino/Taglish).

Morphology topics/word families differ across splits. Corpus bait overlaps on
purpose. Collision labels are human-authored differences in meaning, not runtime
classification. Ordinary controls include rewriting supplied text, creative work,
general knowledge and conversation. Exact controls include identifier/path-directed
requests and implicit requests. Directed requests may bypass useful(): null means
not applied, not rejection. Synonyms and multilingual questions have actual gold
answers but may fail lexically; failures there cannot trigger tuning or count as a
morphology improvement. Taglish English anchors are not a translation capability.

author.py is one-time construction code and refuses to run after FREEZE.json exists.
Fixture authoring sees questions/gold, not model or retriever outputs. No arm was
scored to choose, replace or simplify cases. Before any future timed development
run, review the freeze and reference implementation. No automatic holdout runner
exists: evaluate() refuses holdout scoring. A separately approved, versioned
holdout execution adapter would require the reviewed candidate hash and explicit
authorization; it cannot edit this evaluator or its frozen gates. An arm failing
development gates never earns holdout merely by overall improvement.

## Four distinct stages

1. Candidate recall@12: a relevant gold source span exists in retrieved candidates.
   Candidates are probed even for fast-path ordinary requests; probe_only clearly
   distinguishes that availability diagnostic from an actual policy search.
2. Admission: report whether useful() was invoked, admitted or rejected. Directed
   bypasses and conversational bypasses are distinct from measured rejection.
3. Final supplied packet: real Core preparation returns source metadata; close the
   lazy stream after TurnStarted, before any generate call. Report top-three supply,
   final relevant recall, no_match/not_used/budget_exhausted, and dropped turns.
4. Answer spans: Hit@1/Hit@3/MRR@3 on candidates, plus final answer-span recall.
   A related overview need not contain the answer. Neither relevance nor supplying
   an answer span establishes generation correctness.

PacketBackend is a frozen **model-free accounting stub**: 4 + sum(8 + ceil(UTF-8
content bytes/4)), context 8192, output reserve 256, evidence allowance 768, no
custom system prompt. This is not the Qwen tokenizer or a guarantee of actual-model
admission. Any later real-token verification is a separately reported check. No
real model is loaded and generate() raises if touched. Core/history storage and
production settings are unchanged. All future packet losses under this oracle
must be reported, never discarded from selection denominators.

Each observation retains effective query, original terms, candidate/source spans,
lexical and Porter audits, each token/stem mapping, denominator/coverage, policy
attempt/reason, admission, final packet/status and timings. Every A->B, A->C and
B->C admission, decision/status or final-packet change is returned with complete
before/after records, including diagnostic cases. Candidate ranking-only changes
are also reported separately. Collisions include both original tokens and stems;
origin/stem similarity never implies semantic relevance.

## Mechanics, performance and historical diagnostics

24 contract probes use independent miniature documents, not relevance fixtures.
They cover native tokenizer semantics, bounds, escaping, original text, coverage,
generated exclusion, top-three behavior, A parity, B/C candidate equality, double
lexical bottleneck, read-only schemas, duplicates and Core packet lifecycle.
All must pass before any development evaluation. Evaluator tests use synthetic
observations; they do not run/score the fresh development or holdout retrieval.

performance.json and workload.py freeze an independent 1,000-document, 10-block
per document workload, exact source/query identities and measurement protocol.
No performance indexing/timing has occurred at freeze. See rubric.md for gates.
historical.json pins earlier artifacts; diagnostics.json identifies the complete
24 M6 + 32 M7 + 56 M8 case panels, including spent historical holdouts. They are
not either sealed M11 holdout. Existing builders/labels are reused unchanged,
with original project identity where applicable. No new accidental supply versus
paired A on M8 direct controls (respecting existing acceptable outcomes) is allowed.
Previously observed failures are highlighted, never used to award fresh credit.

Freeze covers every file below this directory except FREEZE.json and __pycache__.
The manifest's own SHA-256 is the version identity. Outputs belong outside this
directory, e.g. eval-results/morphology_retrieval_v1/, never in the frozen corpus.
