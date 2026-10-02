# Frozen M9 deterministic-capability evaluation v1

This evaluation was frozen before any M9 runtime code existed. `FREEZE.json` hashes every file in
this directory except itself. Any change needs a new version. The historical M1, M6, M7 and M8
benchmarks are untouched.

M9 adds **deterministic capabilities**: small, internal, exact operations whose results reach
the model as facts. It also adds **authenticated host-supplied context**. "Tools" survives only
in this directory's name; M9 is not a tool framework. There is no registry, no function
calling and no loop.

## Scope boundary

| Part | Meaning |
| --- | --- |
| **Server-local clock** | The current date, time and weekday from the machine running Dwindy. It is not assumed to be the end user's time zone. There is no time-zone inference or configuration. |
| **Calculator** | Exact, bounded arithmetic on explicit expressions. It ships only if the frozen real-model adoption rule passes (see `rubric.md`). |
| **Host-supplied context** | Information the host application's backend has already authenticated and authorized, attached to one chat request. It provides information. **It does not implement host actions:** requests like "renew this loan" stay unsupported, and Dwindy never invokes host operations. Host actions may be evaluated separately later, if evidence shows a need and a narrow, safe design exists. |
| **Out of scope** | Dwindy-initiated host calls, tool loops, function registries, natural-language date math, unit conversion, word-problem parsing and web access. |

The clock and calculator are internal: **no toggles, no thresholds, no settings**. Exactly one
model call per turn remains.

## `cases.jsonl`: 60 model-independent cases

Within each category, odd-numbered cases are development and even-numbered cases are holdout,
giving 30 per split.

| Category | Cases | Expected |
| --- | ---: | --- |
| arithmetic | 14 | Exact `result`. `expression` is a canonical form used only to verify the label. |
| numeric_no_trigger | 16 | `none`: dates, versions, phone numbers, ranges, IDs, standards, times, fractions in prose, money, codes, ratios, scores, sections, names |
| adversarial_expression | 8 | `rejected` (beyond bounds), `undefined` (division by zero, 0^0) or `none` (code, scientific notation) |
| clock | 8 | Clock fact supplied |
| clock_no_trigger | 8 | No clock fact ("current version", "time complexity", "Day of the Dead"…) |
| mixed | 4 | Both capabilities, the clock only, the calculator only, the clock only |
| self_contained | 2 | `none`: arithmetic inside text supplied for translation, or as the subject of a poem |

**Calculator outcomes:**

- `result`: an exact value. Non-terminating results are compared to 1e-12 relative.
- `undefined`: mathematically undefined.
- `rejected`: recognized as arithmetic but beyond the bounds, so no fact is supplied.
- `none`: not arithmetic.

**Calculator bounds:**

| Bound | Limit |
| --- | --- |
| Expression length | 200 characters |
| Digits per number | 30 |
| Nesting depth | 10 |
| Exponent (absolute value) | 100 |
| Result digits | 100 |
| Decimal precision | 28 significant digits |

There is no `eval`, and no partial span is ever computed. In "1e308 * 10", for example, "308 * 10"
must not be evaluated.

## `host_context.jsonl`: 16 API contract rows

**Contract:**

- `POST /v1/chat` accepts an optional `host_context`: a list of 1–8 items, each exactly
  `{"label", "text"}`.
- Labels are 1–64 non-blank characters. Each text is 1–2,000 characters, with at most 4,000
  characters in total.
- The field is accepted **only on bearer-authenticated requests**. Without a configured token it
  is refused with 403 `host_context_requires_token`. A configured token with a missing or wrong
  header gives the existing 401.
- Host context has its own 1,024-token budget. When present, it is always supplied, framed as
  quoted data and never as instructions.
- Host context that cannot fit its budget gives 422 `context_limit`; it is never truncated.
- Host context is never persisted and never restored.

The rows check:

- validation, authentication and the token budget;
- quoting of role-marker and instruction text;
- supply for a greeting with retrieval off;
- non-persistence;
- that an action request ("Renew this loan for me.") invokes and claims no action.

**Minimal integration example** (for the eventual docs). The host's backend, never the browser,
calls Dwindy with the bearer token:

```python
requests.post("http://127.0.0.1:8000/v1/chat",
    headers={"Authorization": "Bearer " + DWINDY_TOKEN},
    json={"message": user_message,
          "host_context": [{"label": "Current user", "text": "Role: borrower. Active loans: Microscope M-2, due 2026-10-10."}]})
```

## Gates

The gates apply to all 60 cases once the holdout has been scored:

| Gate | Threshold |
| --- | --- |
| Calculator exactness, over every expected `result` | 100% |
| Strict false triggers (numeric_no_trigger + self_contained) | 0 |
| Adversarial handling | 100% correct outcome class |
| Clock recall, over every case expecting the clock | ≥ 90% |
| Clock false triggers (clock_no_trigger) | ≤ 1 of 8 |
| Host-context contract rows | All 16 correct |

Other false triggers are reported.

**Measured separately:**

- calculator evaluation p95 < 1 ms;
- every adversarial expression rejected in < 50 ms;
- added memory ≤ 2 MiB;
- byte-identical model input when no capability applies;
- exactly one model call per turn.

## Complexity boundary

The clock cues and calculator word operators ("plus", "minus", "times", "divided by",
"multiplied by", "of" after a percentage) live in **one table capped at 30 entries**
(`CUE_TABLE_CAP`). Number and expression shapes are the only regular expressions. A cue is never
added to repair one case. The M8 context-selection cue table and its 60-entry cap are unchanged.

## Labeling judgment calls

- **Supported forms:** word operators between two numbers ("7 times 8"), "N% of M", and both `^`
  and `**` for powers.
- **Fractions:** a fraction in prose ("1/2 cup") is not computed, while an explicit question with
  an operator is.
- **Unsupported forms:** 0^0 is `undefined`. Scientific notation is unsupported (`none`), with no
  partial evaluation.
- **No computing inside supplied text:** arithmetic inside text supplied for transformation, or
  as a poem's subject, is not computed. This respects M8's self-contained fast path.
- **Clock:** liberal on present-tense date and time references ("today", "now", "what day is
  it", "tomorrow"). A false clock fact costs about 20 tokens; a missing one invites an invented
  date.
- **Host-context validation:** an empty `host_context` list is rejected rather than treated as
  absent. Host context is supplied even for "Hello!", because the developer attached it
  deliberately.

## Tuning rules

- Tune against the development split only, and score the holdout once.
- Report holdout failures rather than repairing individual cases.
- Do not add parsing libraries, natural-language date parsing or broader cue lists to rescue
  failures. Report them; they may motivate a later Capability Density experiment.
