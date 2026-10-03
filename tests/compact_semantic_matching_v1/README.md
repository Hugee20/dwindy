# Compact semantic matching v1 — reviewed and frozen

User language review completed on 2026-10-03. All 45 unchanged review items were
approved; exactly four requested fixture/gold corrections were applied. Finalization
was approved by the user's Dwindy completion directive on 2026-10-03. All 49 review
items are approved. No language expansion or optimization occurred.

Hypothesis, unchanged:

> A small local encoder improves Dwindy’s discovery and admission of relevant information while preserving source identity, compact evidence, offline operation and bounded resource use.

This evaluates Dwindy's information pipeline, not Qwen's semantic-policy behavior.
Source framing, operational status and supply receipts are infrastructure facts;
no generated explanation is required to communicate them. Similarity is neither
truth nor support nor a public confidence score. Answer-span success means the
annotated material was located/supplied, not that a model answered correctly.

These fixtures were authored after M6–M11 and rejected morphology development
findings were known. They are a separate hypothesis, not a replacement evaluation
or a retroactive pass. Original M11, Foundation and morphology holdouts remain
sealed/unspent. Reach/H2 artifacts and partial captures are untouched. A revised
infrastructure-oriented Reach concept will need its own future versioned evaluation.

## Composition

160 fresh cases, 80 development and 80 initial holdout, with separate corpus
manifests and indexes. Each split contains:

| Category | Cases |
| --- | ---: |
| English meaning-equivalent questions | 12 |
| Filipino, including English-source cross-language requests | 12 |
| Taglish meaning-equivalent questions | 12 |
| Ordinary lexical requests | 8 |
| Exact identifiers/paths | 8 |
| English morphology | 8 |
| Short legitimate local-information requests | 4 |
| No-supply challenges | 16 |

64 positives and 16 negatives per split. Every positive has a paired related
distractor. Negative cases add wrong entities, wrong procedures, different scope,
identifier near-misses, conversational utterances, text transformations, creative
writing, general knowledge and reasoning. There are 288 UTF-8/LF documents: 144
per split, including 64 target records, 64 distractors and 16 negative bait records.
Source types alternate PROJECT documentation and DOCUMENT text; filenames/names
carry no gold labels. No query/gold annotations enter encoded source views.

Gold relevance and answer-bearing spans are independent fields with exact
document/source identities, Unicode codepoint offsets and original strings.
`rubric.md` explains judgment calls; `language_review.json` has 49 review records:
the 48 Filipino/Taglish positives plus the negative control containing a Filipino
quotation. All records are approved, including the four specified corrections.
Composition and quality gates are unchanged. Language-fixture work is concluded.
`LANGUAGE_REVIEW.md` gives the user the exact language queries, source text,
distractors, spans and canonical case hashes. Fluent review must cover meaning,
naturalness/code-switching and labels, not just spelling. No language-specific
repair rule may be inferred from this review. Corrections are construction edits
only, before freeze, and require refreshed review bindings and draft hashes.

The fluent reviewer can approve all listed case IDs or report corrections by ID.
Only a real approval is entered with reviewer/date; authoring never signs itself
off. Construction review necessarily sees initial holdout fixtures before sealing;
it does not execute retrieval or expose holdout outputs. After freeze, initial
holdout fixture access is limited to integrity checks; evaluation cannot load it.

## Arms, accounting and bounded choices

`protocol.json` is the exact implementation hypothesis. A retains unicode61 and
existing usefulness. R reranks/adopts only FTS candidates. S performs exact dense
search over permitted split-local chunks. H unions FTS and dense candidates with
fixed RRF k=60. Candidate packets remain at most 12, supplied packets at most 3,
with unchanged 768 evidence allowance, deduplication and context-selection fast
paths. The encoder does not execute on ordinary model-only turns. Existing
directed retrieval opt-in is separately reported and not reclassified.

R/S/H use a predeclared global similarity-threshold grid, never language/topic
rules. Every supplied entry must be independently admitted; high similarity of
one entry does not authorize the rest. Library/model recipes and acquisition
identities are in `models.json`. Static English, small English transformer and
small multilingual transformer are alternatives, not presumed winners. The
FastEmbed/direct ONNX comparison must use identical graph/tokenizer/recipe.
Resources are adoption gates, not reporting-only observations.

This construction includes no encoder adapter/search runner: those are later
authorized experimental machinery. It installs/downloads nothing. Model metadata
pins are obtained from publisher metadata, not downloaded weights. All eventual
model acquisition is explicit and separate from the offline evaluation. Missing,
corrupt or incompatible models and stale semantic indexes produce operational
unavailability, never a claim that no relevant information exists. No silent
library, model or artifact substitution is permitted after outputs.

`contract.py` tests a minimal result/receipt concept, not a production abstraction
or new API. Internal entries preserve exact source and entry IDs, original text
and order. Public projection groups only actually supplied entries by source and
does not expose similarity. A future UI can show one indicator per source, e.g.
an article, without confusing it with a factual-verification claim. No UI or Reach
source acquisition is implemented here.

Accounting uses the explicitly named **model-free utf8_quarters_v1 oracle** from
the morphology experiment: 4 + sum(8 + ceil(content UTF-8 bytes/4)), context 8192,
generation allowance 256, evidence allowance 768. Existing Core actually prepares
the packet, then its lazy stream closes at TurnStarted before generate. This is
not Qwen tokenization and not an inference-quality claim. A later real-token
comparison, if authorized, is separate and must report any changed supply/trimming.
Encoder-token truncation is independently audited; text supplied to Core always
remains original. Missed gold beyond the encoded view stays in denominators.

## Mechanics, scoring and freeze

32 deterministic probes cover evaluation receipt invariants and existing Core
packet/transience/native-history/rollback behavior. Synthetic evaluator tests
exercise metrics/gates without retrieving either case split. Probes do not claim
an absent production semantic backend has already implemented operational handling.
`evaluate.py` scores supplied observations only; it imports no encoder and cannot
run a retrieval split. Separate acquisition, admission and supply fields prevent
budget exhaustion and failed acquisition from becoming misleading supply claims.
All six A/R/S/H pairwise changes include complete before/after records.

The frozen resource protocol covers 10,000 independently generated chunks and
1,000 warm query samples per candidate across five isolated processes. Source and
query input hashes are recorded without building indexes or timing retrieval.
Historical M6–M8 and morphology development panels are diagnostic only, except the
unchanged no-new-historical-false-supply control specified in `diagnostics.json`.

`prepare.py` validates mechanics/bindings and writes DRAFT_MANIFEST.json for review.
Its --freeze path refuses pending, incomplete or stale human review. FREEZE.json
must not exist before fluent approval. Its SHA-256, once produced, is the evaluation
version identity. Frozen bytes/gates/evaluator/split never change after observations.
Result artifacts go outside this directory. Any holdout scoring requires separate
user approval, candidate freeze and a separately versioned execution adapter.
No development retrieval, encoder inference, Qwen inference or performance run has
occurred during construction. No production code has changed.
