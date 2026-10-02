# Frozen Reach v2 evaluation (H1: compact deterministic evidence selection)

Reach v1 failed its frozen adoption rule (`docs/M10_VALIDATION.md`). That result and every earlier
frozen artifact, including `tests/reach/`, stay unchanged. This directory freezes a **separate**
v2 experiment before any runtime change. `FREEZE.json` hashes every file here except itself.

## Hypothesis H1

The provider request and response handling stay those of v1 (`dwindy.reach.parse`). After
parsing, instead of supplying whole results, Reach supplies a few **sentences** chosen
deterministically:

| Rule | Value |
| --- | --- |
| Sentences in total | At most 3 |
| Sentences per article | At most 2 |
| Characters in total | At most 600 |

- Each sentence stays attached to its article title and URL.
- When no sentence qualifies, Reach **abstains**: no external evidence is supplied, and the
  offline-honesty path applies.
- The 600-character limit is the actual constraint: Python code points of sentence text.
  Tokenizer counts are reported separately.
- **Excluded:** stemming, embeddings, semantic similarity, another model, case-specific rules
  and new dependencies. H2 (richer provider text) stays deferred.

## The frozen algorithm (`evaluate.py: reference_select`)

The reference function is the specification. The runtime implementation must reproduce it
exactly for the chosen constants.

1. **Normalization.** Remove editor markers (`[update]`, `[citation needed]`,
   `[clarification needed]`, `[n]`, `[a]`). Tokens are case-folded Unicode alphanumeric runs,
   the frozen M6 tokenizer.
2. **Sentence split.** Split after `.`, `!` or `?` where whitespace is followed by `A–Z`, `0–9`,
   `"`, `“` or `(`. Version numbers like "3.14.6" are never split, because no whitespace follows
   the period. Splitter artifacts, such as a snippet fragment merged onto the previous sentence,
   are part of the frozen behavior.
3. **Candidates.** Every sentence of every parsed result, in provider order. Exact case- and
   whitespace-insensitive repeats are kept once, at their first occurrence.
4. **Eligibility.** A sentence is at most 600 characters, starts with an uppercase letter, a digit
   or an opening mark, and ends with `.`, `!` or `?` (optionally followed by a closing mark).
5. **Subject terms.** The distinct terms of the v1-minimized query, excluding M6 stopwords, v1
   freshness and filler words, single characters and pure digits, kept in query order. With no
   subject term, Reach abstains.
6. **Features.**
   - *hits:* the number of subject terms present in the **sentence itself** (the title does not
     count);
   - *predicate:* 1 if the sentence contains a current-state phrase (`latest`, `current`,
     `currently`, `most recent`, `newest`, `as of`, `incumbent`);
   - *recent:* 1 if it contains a four-digit year within one year of the server-local year (the
     capture year in replay).
7. **Score:** `hits + predicate_weight × predicate + year_weight × recent`. A sentence qualifies
   when it is eligible, has `hits ≥ 1` and has `score ≥ min_score`.
8. **Ranking:** score descending, then predicate, then recent, then provider rank, then position
   within the article (earlier first).
9. **Greedy selection** in rank order. A sentence is skipped if its article already has 2
   selected, or if it would push the total over 600 characters. **It is never truncated:** the
   next candidate is tried. Selection stops at 3 sentences.
10. **Order supplied:** rank order, strongest first, each as
    `Source n article=<title> url=<url> sentence=<sentence>`.

**Tunable on development only:**

| Constant | Initial value | Allowed values |
| --- | --- | --- |
| `predicate_weight` | 1.0 | 0, 0.5, 1, 1.5, 2 |
| `year_weight` | 1.0 | 0, 0.5, 1, 1.5, 2 |
| `min_score` | 2.0 | 1, 1.5, 2, 2.5, 3, 3.5, 4 |

Word lists, rules and limits are frozen. The chosen values and the development results that
justified them are reported before the holdout is scored once.

## Splits and labels (`labels.jsonl`)

- **Development:** Reach v1's 13 recorded snapshots, already inspected.
- **Holdout:** 14 new questions captured on 2026-10-02, with v1's exact single combined request
  and OS-native TLS verification. Each was checked beforehand to trigger frozen v1 detection and
  minimize to a usable query. They were not selected for answerability, and none was added after
  capture.

**Labeling rule.** A gold sentence must, **on its own together with its article title**, state the
expected current fact. Facts that need several sentences or date reasoning are labeled "no
answer" under H1. Each case also stores its v1-parsed `results`, so the selection input is frozen.

| Split | Answerable (expected fact) | No answer |
| --- | --- | --- |
| Development (13) | Android 17 (×2, one injected), Python 3.14.6, Linux 7.2, Andy Burnham, António Guterres, about 8.3 billion | Microsoft CEO, Nobel Peace Prize, World Cup, Ubuntu LTS, PH president, PH economy news |
| Holdout (14) | Emmanuel Macron, Sanae Takaichi, Mark Rutte, Leo XIV | Rust, Go, macOS, Ballon d'Or, Best Picture, Pixel, peso rate, weekly headlines, Apple stock, Leyte news |

**Distractor sentences** (other entities or editions) are labeled for diagnostics:

- the latest PIL version;
- the U-20 Women's World Cup final;
- Japan's Minister of Defense;
- the NATO Parliamentary Assembly's secretary general.

The world-population snapshot is answerable, but frozen detection never sends that question, so
it appears in the selection benchmark only and not in e2e.

## Gates (holdout, scored once)

| Gate | Threshold |
| --- | --- |
| Answer recall: a gold sentence among those supplied, over answerable cases | ≥ 0.8 (with 4 cases, all 4) |
| Abstention: nothing supplied, over no-answer cases | ≥ 0.75 (at least 8 of 10) |
| Limits respected | 100% |
| Attribution: each supplied sentence is a split sentence of the article it is labeled with | 100% |
| Selection time p95 (measured separately) | ≤ 5 ms |

Distractors supplied and maximum characters are reported.

**Regression requirements:**

- the frozen v1 suites must still pass unchanged (detection 54, privacy 20, permission 20,
  contract 14, and the zero-network guards);
- the notice rows below;
- the earlier benchmarks.

## Honesty-notice interaction (`notice.jsonl`, 8 rows)

The generic offline-freshness notice is suppressed **only** for:

- project-directed turns;
- turns where the M8 policy supplied relevant local evidence (`relevant_match` or
  `project_directed` with passages).

An index existing is not enough, and neither is a weak match or forced retrieval. Forced
retrieval does not establish relevance; that row is a judgment call.

The v1 result, in which a project question received the notice, stays recorded as observed.

## Metadata (existing vocabulary)

| Situation | `used` | `supplied` | `reason` |
| --- | --- | --- | --- |
| Network search occurred | `true` | — | — |
| Useful evidence supplied | — | `true` | `supplied` |
| Abstention | `true` | `false` | `not_useful` (existing code) |

`sources` lists only the articles whose sentences were supplied. Nothing reports, or implies,
that an answer was verified.

## Real-model comparison

See `rubric.md`: conditions B, C1 and C2. The original adoption rule is applied unchanged to C2
versus B on holdout, and C1 versus C2 is diagnostic only.
