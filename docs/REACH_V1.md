# Practical Reach for v1

Reach is optional Wikipedia acquisition, disabled by default. Dwindy owns detection,
minimization, acquisition, admission, budgeting and source/status reporting. Qwen uses bounded
supplied information in its ordinary single generation. Its wording does not establish
retrieval success, actual supply, provenance or factual correctness.

## Configuration

From the repository root:

```powershell
.venv\Scripts\python.exe -m pip install -e '.[api,reach]'
```

In the API TOML passed to `dwindy-api --api-config`:

```toml
reach_provider = "wikipedia"
reach_default = "off"
```

A provider only permits Reach. `reach_default = "auto"` opts in to the existing closed
freshness/explicit-search cues. Per-request `reach` is `false`, `"auto"`, or `true` (deliberate
lookup); omission uses the default. Requests cannot grant an unconfigured provider. The browser
shows **Use Wikipedia** only when configured; checking it selects `auto`, unchecking it selects
`false`. Health reports the configured provider/default; transport failure preserves local chat.

`truststore==0.10.4` belongs only to the optional `reach` extra. The reference Windows/Python
3.13 standard TLS context failed certificate verification; OS-native verification successfully
established HTTPS. Verification is never disabled. Missing certificate support yields
`unavailable / tls_unavailable`, with local operation preserved.

## Deterministic state and sources

JSON replies and SSE `started` carry a Reach record when relevant. Core's final prepared model
packet determines supply. A cancelled/failed generation is still an incomplete turn even if its
prepared packet contained WEB information.

| State | Meaning / reasons |
| --- | --- |
| `disabled` | Unconfigured or off: `reach_disabled`, `reach_off` |
| `not_attempted` | No request: `not_fresh`, `project_directed`, `local_context`, `query_unusable` |
| `unavailable` | Failure: `http_429`, `http_403`, `reach_timeout`, `transport_busy`, `provider_error`, `tls_unavailable` |
| `not_supplied` | Nothing reached the packet: `no_results`, `not_useful`, `budget_exhausted` |
| `supplied` | At least one admitted WEB entry survived Core budgeting |

Records include `attempted`, `reason`, `candidate_count`, `admitted_entry_ids`,
`supplied_entry_ids`, `supplied`, and `sources`. The exact minimized `query` appears only after
transport was attempted. Sources contain provider/title/validated HTTPS article URL derived
from actually supplied entries, never rejected candidates or Qwen-written citations. No public
similarity/confidence score is exposed. Distinct entry IDs may collapse into one article link.

**Referenced from Wikipedia — &lt;article&gt;** is rendered separately from the answer. It means
material from that article was supplied to Qwen. It does not mean Wikipedia verifies every
generated statement, that Qwen used every entry, or that the answer is current/correct.

## Bounds and privacy

- One MediaWiki request per selected turn; no retries, redirects, crawling, cookies or cache.
- Verified HTTPS, five-second caller deadline, 512 KiB response ceiling, at most three results
  of 1,600 characters each. Existing Core allowance is 768 evidence tokens by default, with exact
  backend counting, history trimming and at most three supplied entries. Excluded entries are
  never advertised as sources. Local retrieval/ranking is unchanged.
- Only the current message contributes to the query. History, local material, computed facts
  and host data are never appended. URLs, emails, credential/value patterns, key-shaped tokens,
  IPs, long numeric identifiers and host-context words are removed before usability checks.
  Project-directed requests and turns already carrying local evidence suppress Reach.
- At most 12 query terms / 200 characters. Minimization does not detect every private name or
  sensitive sentence. Keep Reach off for material that must stay entirely local. Wikipedia and
  network operators receive the minimized query.
- WEB evidence/receipts are transient; saved conversations retain original user text and raw
  model answers only. Answers may repeat supplied material; persistence is not secret scrubbing.
- A timed-out native transport can outlive the caller deadline. It retains its single worker
  slot until completion; further turns report `transport_busy` and continue locally instead of
  queuing work. Shutdown prevents new submissions. Native DNS/socket cancellation is not promised.

## Limitations and historical findings

The single request acquires complete plain-text introductions within the response ceiling.
Paragraph boundaries are preserved for selection. Dwindy ranks bounded verbatim paragraph
or sentence windows by literal query-word coverage, with source order breaking ties, before
applying the character limit. An article title whose informative words exactly match the query
subject provides context during selection, so an incumbent paragraph need not repeat its
country. Snippets are used only when an introduction is absent. Exact subject articles are
preferred during admission; their passages must mention the title's leading subject word.
Titles containing all subject words plus extra informative qualifiers (such as **Vice**
President of Brazil) are not equivalent to the requested subject. Otherwise admission requires
all informative subject words in the selected text; URLs do not provide coverage. Local
usefulness and ranking are unchanged. IDs and content hashes describe the exact selected
text; Core's actual supplied entries determine the public receipt.

Wikipedia intros/snippets can be incomplete, outdated or inconsistent. Long sentences may
require word-boundary windows. Conservative exact-word admission can miss relevant variants.
Abbreviations such as `UN` and `United Nations` are not expanded or treated as interchangeable;
including both forms can prevent full literal subject coverage.
Lexical admission is coverage, not truth, answerability or freshness verification. Ambiguous questions
may not trigger automatic acquisition. Outages/rate limits produce local fallback. No infobox
expansion, semantic retrieval, extra provider, verifier or second generation is introduced.

The adopted M10 offline-honesty notice remains best-effort guidance when Reach is off, separate
from deterministic status. [Historical Reach](REACH.md) and [M10 validation](M10_VALIDATION.md)
retain rejected policy findings. H2's frozen design/four paired captures remain deferred; practical
Reach does not resume, redefine or retroactively pass H2. Original M11, Foundation, morphology
and semantic holdouts remain sealed/unspent. Historical tests load checkpoint `228f023` and
the existing candidate archives, not the new production implementation.

Acceptance uses ordinary mechanical/integration/browser tests and five live checks; Qwen's
provenance/status wording is not an acceptance gate.
