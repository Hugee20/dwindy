# M9 deterministic capabilities and host context

M9 adds two kinds of exact, non-model information to a turn:

- **Deterministic capabilities:** small internal operations Dwindy computes itself. These are
  the server-local clock and the adopted bounded calculator.
- **Host-supplied context:** information the host application's backend has already
  authenticated and authorized, attached to one chat request.

Both reach the model as quoted **facts** in the turn's single model call. Neither is a tool
framework. There is no function registry, no function calling, no loop, no outbound call and
no extra model call.

## The boundary

| Dwindy does | Dwindy does not |
| --- | --- |
| Read the server's clock when a turn needs it | Infer or configure the user's time zone |
| Compute explicit arithmetic exactly, within bounds | Parse word problems, natural-language dates or units |
| Supply host-provided information for one turn | Perform host actions ("renew this loan"), call the host, or keep host data |

Host context provides **information, not actions**. A request like "renew this loan" stays
unsupported: no host operation runs. The supplied runtime-capability fact describes Dwindy's
lack of a host-action executor. It does not guarantee that the model will verbalize this
boundary correctly; generated prose cannot establish that an action happened.
Host actions may be evaluated separately in the future, if evidence shows a need and a narrow,
safe design exists.

## Server-local clock

When a message refers to the present ("today", "tomorrow", "what time is it", "the date"…), the
turn receives:

> Server-local date and time: Friday, 2026-10-02 09:15 (UTC+08:00). This is the server's clock,
> not necessarily the user's time zone.

The clock is read **while each turn is processed**, so a long-running server never reuses a
stale reading. It is the time of the machine running Dwindy. In a local-first deployment that
is usually the user's machine, but Dwindy does not assume so and has no time-zone setting.

## Calculator

The calculator handles **explicit** arithmetic only, through a small closed grammar:

- a whole message that is an expression ("3 * (4 + 5) - 6 / 2"), or an expression after a
  calculation lead ("what is", "calculate", "how much is"…);
- numbers with `+ - * / × ÷ ^ ** %` and parentheses;
- the word operators "plus", "minus", "times", "multiplied by", "divided by", and "N% of M".

It never computes a partial span or text inside material supplied for translation or a poem.
It never reads dates, versions, phone numbers, ranges, IDs, times, prose fractions, money or
codes as arithmetic. It never uses `eval`.

**Results:**
- exact decimal results, at 28 significant digits;
- division by zero and 0^0 are reported as undefined;
- expressions beyond the bounds (200 characters, 30-digit numbers, nesting depth 10, exponents
  up to 100, results up to 100 digits) are rejected, and no fact is supplied.

The calculator passed its historical adoption rule and ships; see the
[M9 validation report](M9_VALIDATION.md).

Neither capability has a setting, toggle or threshold. They are part of Dwindy.

## Host-supplied context

The host's **backend**, never the browser, calls Dwindy with the API bearer token and a few
labeled facts it has already checked:

```python
requests.post("http://127.0.0.1:8000/v1/chat",
    headers={"Authorization": "Bearer " + DWINDY_TOKEN},
    json={"message": user_message,
          "host_context": [{"label": "Current user",
                            "text": "Role: borrower. Active loans: Microscope M-2, due 2026-10-10."}]})
```

A browser widget can use host context only through a backend that proxies its requests and adds
the context and token. Never ship the token to the browser.

**Contract:**

- `host_context` holds 1–8 items, each exactly `{"label", "text"}`. Labels are 1–64 non-blank
  characters; each text is 1–2,000 characters, with at most 4,000 in total.
- The field is accepted only on bearer-authenticated requests. Without a configured
  `DWINDY_API_TOKEN` it is refused with 403 `host_context_requires_token`; a missing or wrong
  header gives the existing 401.
- It is supplied whenever present, within its own 1,024-token allowance. Too large gives 422
  `context_limit`; it is never truncated.
- It is framed as quoted data with lossless delimiter escaping. This enforces representation,
  not model obedience or immunity to prompt injection.
- It is **never stored**. Persisted conversations keep only the user's message and the answer,
  and a resumed turn sees host context only if the host attaches it again.

## Metadata

When a capability or host context is used, the JSON reply and the SSE `started` event include:

```json
"capabilities": [{"name": "clock", "value": "2026-10-02T09:15+08:00"},
                 {"name": "calculator", "input": "924 × 17", "result": "15708"},
                 {"name": "host_context", "items": 1}]
```

The key is absent when nothing was used, and turns without capabilities are byte-identical to
M8. Python Core callers pass `facts=Facts(...)` to `DwindyCore.chat`. The terminal supplies the
clock and calculator automatically.
