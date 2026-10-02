# Frozen M10 Reach evaluation v1

This evaluation was frozen before any M10 runtime or network code existed. `FREEZE.json` hashes
every file in this directory, including `recorded/`, except itself. Any change needs a new
version. The historical M1, M6, M7, M8 and M9 benchmarks are untouched.

**Reach** is Dwindy's *external information* capability. It is not a promise of web browsing:
the M10 reference provider, Wikipedia via the MediaWiki API, has deliberately narrower coverage.

## M10 scope

| Part | Meaning |
| --- | --- |
| A. Freshness detection | A closed cue table, capped at **25 entries** (freshness cues plus explicit-search phrases). Ambiguous requests do **not** trigger Reach: attempt conservatively, supply conservatively. |
| B. Offline honesty | When a freshness question has no usable external results, a transient notice asks the model not to present possibly outdated knowledge as current. It ships only if its adoption rule passes. |
| C. Reach | Disabled by default. Wikipedia is the sole reference backend, subject to verification after this freeze. Snippets and extracts only. Results are untrusted, transient evidence, and there is one model call per turn. It ships only if its adoption rule passes. |
| **Out of scope** | SearXNG or any other provider, page fetching, HTML extraction beyond cleaning provider snippets, crawling, caching, multiple providers, model-written queries and additional model calls. |

## Deployment permission versus request policy

| Deployment | Request `reach` | Result |
| --- | --- | --- |
| No `reach_provider` | omitted, `false`, `"auto"` | No network, ever |
| No `reach_provider` | `true` | 503 `reach_disabled`, no network |
| `reach_provider = "wikipedia"`, default unset or `"off"` | omitted or `false` | No network. **Configuring a provider never implies auto.** |
| Same | `"auto"` | Network only for freshness questions |
| Same | `true` | Network for any message, except project-directed ones and unusable queries |
| `reach_default = "auto"` | omitted | Like `"auto"` above |

- **A request can only select behavior the deployment already permits.** It can never grant
  network capability.
- **Configuration errors:** `reach_default` without a provider, `reach_default = "on"`, and any
  provider other than `wikipedia`.
- **Strict request values:** `true`, `false` or `"auto"`, with `null` rejected.
- **Precedence:** project-directed messages never invoke Reach, even when forced. When M8 supplies
  local context, Reach is not used. The clock never needs Reach.

## Privacy: fail-closed minimization

1. The outbound query is derived **only from the current message**.
2. Protected material is removed **first**: emails, phone numbers, long digit sequences (cards,
   IDs), IP addresses, URLs, API-key-shaped tokens, values after credential words (password,
   PIN, token, key, secret), text matching host context, and the project name. A project-name
   mention blocks the request outright.
3. The remainder is reduced to at most 12 terms and 200 characters.
4. **Only then** is the query judged usable: at least one content term beyond freshness words. If
   it isn't usable, **no request is made**. History, host context, project material, retrieved
   passages and model-generated terms are never added.

The exact query that left the machine is reported in the response metadata (`reach.query`), and
the browser shows "Searched externally for: …" whenever Reach was used. The standard widget gets
no Reach checkbox.

**Documented limitation:** a private person's name typed into a freshness question
(`privacy_20`) is not detected.

## Files and composition

| File | Rows | Contents |
| --- | ---: | --- |
| `cases.jsonl` | 54 | Freshness detection, split 27 development / 27 holdout (odd/even within each category). 24 freshness questions (versions, officeholders, events, prices), 4 explicit searches, 26 no-trigger questions (clock, timeless, historical, non-temporal "current", self-contained). |
| `privacy.jsonl` | 20 | Minimization with context (host data, history, project name, passages): `sent`, `exclude` and `include` expectations |
| `permission.jsonl` | 20 | The deployment-by-request matrix, configuration errors and strict values, with network-call counts |
| `contract.jsonl` | 14 | Provider responses built from the recordings: normal extracts and snippets, empty, malformed, 503, timeout, oversized, redirect, bad URLs, injection, over-long text, captive-portal HTML, wrong shapes, TLS failure |
| `recorded/` | 13 | 12 real MediaWiki response pairs (intro extracts and search snippets) captured 2026-10-02, plus `injected_android.json`, a labeled synthetic copy with one injected sentence |
| `e2e.jsonl`, `rubric.md` | 21 | Blind real-Qwen comparison across three conditions, with both adoption rules |
| `live_smoke.md` | — | Optional live-provider smoke, not scored, plus observations from fixture capture |

## Bounds

All are internal, with no settings:

| Bound | Value |
| --- | --- |
| Timeout for the whole Reach step | 5 seconds |
| Response body | 512 KiB |
| Results supplied | At most 3 |
| Characters per result | 1,600 |
| Query | 12 terms, 200 characters |
| Protocol | HTTPS only, certificate verification always on |
| Redirects | Never followed |
| Accepted result URLs | `https://en.wikipedia.org/wiki/` only |
| Caching and cookies | None |

## Gates

The model-independent gates apply to the full set once the holdout has been scored:

| Gate | Threshold |
| --- | --- |
| Freshness recall | ≥ 90% (at least 22 of 24) |
| Explicit-search recall | 100% |
| Strict false triggers (clock, non-temporal "current", self-contained) | 0 |
| All false triggers (26 no-trigger cases) | ≤ 1 |
| Privacy rows | 20/20. Zero tolerance: any leaked item, missing subject term, over-long query or wrong send decision fails. |
| Permission rows | 20/20, including **zero network calls** wherever expected and the metadata query matching the sent query |
| Contract rows | 14/14 |

**Measured separately:**

- every OFF path is tested under a socket guard, and any connection attempt fails the test;
- one model call per turn;
- byte-identical model input when neither notice nor results apply;
- results and notices are never persisted.

## Labeling judgment calls

- **Detection:**
  - Explicit-search phrases ("search the web for", "look up online", "check Wikipedia for") are
    labeled `explicit_search`, not freshness.
  - "Currently learning", "current directory", "electric current" and "current account" are not
    freshness questions.
  - Creative or transformation requests containing "latest" do not trigger.
- **Privacy:**
  - Text matching host context is removed, and the remainder may still be sent (`privacy_8`).
  - Any project-name mention blocks Reach (`privacy_11`).
  - Taglish freshness questions are sent with their Filipino words kept (`privacy_19`).
  - Names are not detected (`privacy_20`).
- **Permission:**
  - Forced Reach without a deployment provider gives 503 `reach_disabled`.
  - Forced Reach searches non-freshness messages.
  - Project-directed messages are blocked even when forced.
  - `null` is rejected.
- **Contract:**
  - Over-long provider text is truncated to 1,600 characters rather than dropped.
  - Results whose URL is not on `https://en.wikipedia.org/wiki/` are dropped.
  - Unexpected item shapes are skipped, not fatal.
- **e2e:** for the project control, correctness accepts the declared metadata version (0.4.2) or
  "not stated".

## Tuning rules

- Tune against the development split only, and score the holdout once.
- Report holdout failures rather than repairing individual cases.
- Never relax a privacy expectation, add cues to rescue a case, or contact a live provider during
  scored evaluation.
- Provider verification (terms of use, stability, response format) happens after this freeze. If
  the real format differs from these recordings, a new evaluation version is required; these
  files are never edited.
