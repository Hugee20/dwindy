# Historical M10 Reach: external information

This page preserves the experimental design and its historical findings. Current production
configuration and deterministic infrastructure behavior are documented in [Practical Reach for v1](REACH_V1.md).
H2 now has four partial paired captures; its execution/scoring remains deferred and unchanged.

> **Status (M10): not adopted.** Freshness detection and the offline-honesty notice ship. The Reach
> backend described below was implemented and evaluated against its frozen rule. It failed on
> latency (+9.3 s median to first text), misattributed sources and unsupported current claims, so it
> is dormant: configuring `reach_provider` is refused, `reach: true` returns 503
> `reach_disabled`, and no outbound request can occur. This page documents the evaluated design for
> a future re-evaluation. See [M10 validation](M10_VALIDATION.md).
>
> **Reach v2 (H1, deterministic sentence selection): rejected by its frozen holdout gate.** Evidence
> is now at most 3 selected sentences (2 per article, 600 characters, skipped rather than
> truncated), which cuts evidence tokens about 5× and time to first text by several seconds. H1
> failed its frozen holdout selection gate (answer recall 0.50 against 0.8 required). Reach stays
> dormant.
>
> **Reach H2: designed/prepared; execution deferred.** The reference network cannot currently
> satisfy the frozen connectivity requirements. H2 has not failed and has not been adopted.
> Its evaluation design/reference/question sets are frozen in `tests/reach_h2/FREEZE.json`;
> completed captures, frozen labels and scored results do not exist. Preserve the prepared
> evaluation and resume its existing sequence later without redesign or weakened gates.

The dormant Reach design would let Dwindy consult an external source for questions that depend on current information:
the latest versions, officeholders, recent events and prices. It is **not** web browsing. The
reference provider, Wikipedia via the MediaWiki API, has deliberately narrower coverage than a
search engine.

M10 has three parts:

- **Freshness detection:** a closed cue table of 24 entries, capped at 25. Ambiguous questions
  never trigger Reach.
- **Offline honesty:** when a freshness question cannot be grounded, a transient instruction
  asks the model not to present possibly outdated knowledge as current. This applies to every
  deployment, including those without Reach.
- **Reach itself:** disabled/not shipped. Provider configuration is rejected; a request cannot
  enable it. The permission design below is retained as an experimental record.

## Permission (dormant experimental design)

Current operation allows no online Reach: configuring `reach_provider` is rejected, and
`reach: true` returns 503 `reach_disabled`. Provider-configured rows below describe the evaluated
design and are not runnable deployment instructions.

| Deployment (`api.local.toml`) | Request `reach` | Network |
| --- | --- | --- |
| no `reach_provider` (default) | anything | **Never.** `true` gives 503 `reach_disabled`. |
| `reach_provider = "wikipedia"`, `reach_default` unset or `"off"` | omitted / `false` | Never |
| same | `"auto"` | Only for freshness or explicit-search questions |
| same | `true` | Any message, except project-directed ones and unusable queries |
| `reach_default = "auto"` | omitted | Like `"auto"` |

- Configuring a provider only **permits** Reach; it never turns on `auto` by itself. A request
  can select behavior the deployment permits, never grant it.
- Project-directed messages never leave the machine. When local context is supplied (M8),
  Reach is not used.
- Not installable in this release. A future adoption would add `truststore` as an optional
  extra; see [Capability Density](#tls-and-capability-density).

## Privacy: fail-closed minimization

1. Only the **current message** contributes to the outbound query. History, host context,
   project material and retrieved passages are never added, and no model writes the query.
2. Protected material is removed **first**: URLs, emails, credential words with their values,
   API-key-shaped tokens, IP addresses, phone numbers, card and ID numbers, and words appearing in
   host context. A project-name mention, or another M8 project-directed signal, blocks the
   request outright.
3. The rest is reduced to at most 12 search terms and 200 characters.
4. Only then is the query judged usable: it needs a real subject, not just freshness or filler
   words. If it isn't usable, **no request is made**.

Known limitation: a private person's name typed into the question is not detected.

## Transparency

When Reach is considered, replies and the SSE `started` event include a `reach` object.
The example below is an experimental supplied-evidence response, not a currently available
online capability:

```json
"reach": {"used": true, "reason": "supplied", "provider": "wikipedia",
          "query": "latest version android", "supplied": true,
          "sources": [{"title": "Android (operating system)", "url": "https://en.wikipedia.org/wiki/..."}],
          "notice": false}
```

| Field | Meaning |
| --- | --- |
| `query` | The exact text that left the machine |
| `used` | The provider was consulted. It does **not** mean the answer was verified. |
| `supplied` | Results reached the model |
| `sources` | Validated provider titles and article URLs, never model-written citations |
| `notice` | The offline-honesty instruction applied |

**Reasons:** `supplied`, `no_results`, `not_useful`, `reach_unavailable`, `reach_timeout`,
`query_unusable`, `project_directed`, `local_context`, `not_fresh`, `reach_off`,
`reach_disabled`.

The browser widget shows **"Searched externally for: …"** whenever a query was sent. It has no
Reach control.

## Provider behavior and bounds (evaluated v1 design)

- **One request per turn:** a single MediaWiki call returns intro extracts and search snippets.
- **Connection:** HTTPS only, with OS-native certificate verification, never disabled. Redirects
  are never followed, and nothing is cached or stored in cookies.
- **Limits:** a 5-second overall deadline and a 512 KiB response cap. At most 3 results are
  supplied, each up to 1,600 characters, and only `https://en.wikipedia.org/wiki/` URLs are kept.
- **Filtering:** results must pass M8's usefulness check before reaching the model. H1 replaced
  whole-result evidence with at most 3 selected sentences (2 per article, 600 characters);
  that compact-selection hypothesis was also rejected. H2's separate frozen design is documented
  in `tests/reach_h2/README.md`, not implemented as a shipped provider path.
- **Failures fall back to the offline-honesty path, with no retry:** HTTP 429 or 5xx, a
  timeout, a TLS failure, malformed or non-JSON content, or a captive portal.
- **Framing:** results are untrusted, quoted evidence, "External search results from
  Wikipedia, retrieved at <time>…". They are never instructions, never persisted, and use the one
  model call.

## TLS and Capability Density

Verified HTTPS was measured on the reference machine (Windows 11, Python 3.13, OpenSSL 3.0):

| Approach | Wikipedia | Expired, wrong-host or self-signed certificate | Setup time | Peak memory | Size |
| --- | --- | --- | ---: | ---: | ---: |
| Standard library | **fails** (expired certificate in Python's view of the Windows store) | rejected | 32 ms | 0.1 MiB | — |
| `certifi` | works | rejected | 245 ms | 2.8 MiB | 265 KB |
| **`truststore` 0.10.4** (chosen) | works | rejected | 95 ms | 1.9 MiB | 144 KB |

`truststore` verifies through the operating system's trust store, as `curl` does. That also
respects institution-managed roots and OS certificate updates. It is the smallest approach that
works. Because Reach was not adopted, it is **not** a Dwindy dependency in this release.
