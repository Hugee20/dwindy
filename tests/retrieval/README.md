# Frozen M6 lexical retrieval benchmark, version 1

Created before indexing/ranking implementation. Twelve synthetic UTF-8 documents (A-L),
24 queries: four each exact, paraphrase, competition, distractors, no-answer, adversarial.
K intentionally duplicates D. Display names are neutral Document A ... Document L.
Queries ending 1 or 3 are development; 2 or 4 are holdout: 12 each, ten answerable each.
Do not inspect holdout results for tuning. Any future changed benchmark is a new version.

Gold spans use half-open Unicode character offsets into LF-normalized source text. Each
positive query has one required fact with alternative acceptable spans where appropriate.
A passage is relevant only when it contains a full gold span from the correct document.
Chunk identifiers and model outputs play no part in the labels. Instructions themselves
are answer-bearing for A3/A4 because those queries ask what the documents say, not execution.

The evaluator accepts search(query) returning ranked mappings with document_id/start/end/text.
Hit@1 and Hit@3 are the fractions of positive queries with a gold hit at those ranks;
MRR@3 averages reciprocal first-hit rank, with zero on a miss. For this single-fact set,
fact Recall@3 equals Hit@3; alternative sources are not independent required facts.
Report overall, category, split, and every failed query. No-answer queries are excluded
from those denominators, not assigned artificial successes. N1/N2 require empty results;
N3/N4 measure non-answer-bearing returns and do not require a lexical ranker to infer
answerability. Duplicate slots count repeated exact passage text among the first three.

Provisional quality gates: positive Hit@3 >= .85; MRR@3 >= .70; both lexical-absence
queries empty; no duplicate slots. Report paraphrase misses without rewriting fixtures.
Retrieval relevance, answerability and generation correctness are separate measurements.
Adversarial retrieval metrics do not establish prompt-injection resistance.

FREEZE.json contains SHA-256 of this specification, evaluator, manifest, queries and corpus.
The fixture-validation suite checks hashes and all spans without importing a model/retriever.
No frozen M1 artifact is used or modified.
