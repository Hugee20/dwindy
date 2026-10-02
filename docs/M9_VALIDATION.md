# M9 validation report

M9 adds two kinds of per-turn facts:

- **Deterministic capabilities:** a server-local clock, and a calculator that shipped by its
  frozen adoption rule.
- **Authenticated, transient host-supplied context.**

Host context provides information, not actions. Requests such as "renew this loan" stay
unsupported.

There are no Dwindy-initiated host calls, function registries, tool loops, settings, thresholds,
dependencies or extra model calls. The frozen M1, M6, M7 and M8 evaluations are unchanged and
reproduce exactly. M10 was not started.

## Frozen evaluation

The evaluation was frozen before any runtime code: `tests/tools/FREEZE.json` SHA-256
`a4d3a81d584f9c4120ceece119c3b9751307c249509e0c1e9b6a7113f1d061f2`. It is unchanged.

| Set | Contents |
| --- | --- |
| Model-independent | 60 cases (30 development / 30 holdout) |
| Contract rows | 16 host-context rows |
| Real-model | 22 cases |

**Process:**

1. The implementation was built against the development split, which scored 30/30 on its first
   evaluation run.
2. **Disclosure:** before that run, an ad-hoc smoke check used several frozen messages,
   including three holdout ones ("144 divided by 12", "12.5% of 80", the slash date). It exposed
   one genuine implementation bug: a stray control character in the word-operator pattern,
   which broke "divided by". The fix restored the documented grammar. No cue, bound or rule was
   changed because of any case.
3. The module was then frozen (`capabilities.py` SHA-256 `0c79f55f…3ce46a8`), and the holdout
   was scored once. No change followed.

The same author wrote the cases and the implementation, which is a limitation of this
evaluation.

| Gate | Threshold | Development | Holdout | All 60 |
| --- | --- | ---: | ---: | ---: |
| Calculator exactness | 100% | 100% | 100% | 100% (14/14 + 2 mixed) |
| Strict false triggers | 0 | 0 | 0 | 0 |
| Other calculator false triggers | reported | 0 | 0 | 0 |
| Adversarial handling | 100% | 100% | 100% | 100% (8/8) |
| Clock recall | ≥ 90% | 100% | 100% | 100% (11/11) |
| Clock false triggers (lookalikes) | ≤ 1 | 0 | 0 | 0 |
| Other clock false triggers | reported | 0 | 0 | 0 |

**There are no failures and no false triggers:**

- **Adversarial expressions:**
  - 9^9^9, 10^1000000, nesting depth 31 and a 40-digit operand were rejected;
  - code and "1e308 * 10" were not computed (no partial span);
  - 5/0 and 0^0 were reported as undefined.
- **Numbers that aren't arithmetic** never fired. All 16 categories were checked: dates, slash
  dates, versions, phone numbers, ranges, IDs, ISO names, times, prose fractions, money, codes,
  ratios, scores, sections and names.
- **Supplied material:** arithmetic inside translation or poem material was never computed.

Run `tests/capabilities_run.py --split all` for every case.

**Cue table:** 26 entries against the frozen cap of 30.

| Category | Entries |
| --- | ---: |
| Calculation leads | 8 |
| Word operators | 6 |
| Clock cues | 12 |

Numbers and expressions are the only regular-expression shapes. The bounds match the frozen
values exactly, as a test enforces.

## Host-context contract: 16/16

Each row runs through the real HTTP API with a fake backend. The outcome is judged from the
model input, the response and the database.

| Row | Result |
| --- | --- |
| 1 | Authenticated request: supplied as quoted data |
| 2 | Token configured, no header: 401 |
| 3 | No token configured: 403 `host_context_requires_token` |
| 4 | No token and no host context: unchanged |
| 5–11 | 9 items, a 2,001-character text, a blank label, an unknown key, a non-list, an empty list, and over 4,000 characters in total: each 422 `invalid_request`, before any model call |
| 12 | Instruction and `<\|im_start\|>` text: supplied only escaped |
| 13 | Supplied for "Hello!" with retrieval off |
| 14 | Persistence on: the database holds only the user's message and the answer; resumed turns (same server and after restart) never see the old context |
| 15 | Over the token allowance: 422 `context_limit`, never truncated |
| 16 | "Renew this loan for me.": host context supplied, no action capability or operation |

Separate tests confirm:

- the clock is read anew for every request (two requests return different patched times);
- one model call per turn;
- byte-identical model input when nothing applies;
- facts combine with M6–M8 evidence and every fallback path;
- facts never enter history.

## Calculator adoption: adopted

`tests/eval_capabilities_e2e.py` ran the 22 real-model cases with capabilities off and on: 44
generations. It used the unchanged Qwen3-1.7B Q4_K_M non-thinking configuration (seed 42), with
server-local time recorded per generation (Friday 2026-10-02, UTC+08:00).

**Mechanical exact-value check** on the 10 arithmetic cases (`adoption.json`):

| | Correct (of 10) |
| --- | ---: |
| Off | 8 |
| On | 10 |

- **Fixed:** `arithmetic_2` (1234 × 5678) and `arithmetic_11` (999999²).
- **Broken:** none.

With all model-independent gates passing, the frozen rule (gain ≥ 2, no regressions) is met, so
**the calculator ships**. Both off-condition failures were long step-by-step derivations that
never reached a number within the unchanged 256-token output limit, not wrong results. The gain
is exactly the threshold. The human blind scoring below independently confirms it.

## Human blind scoring

A human reviewer scored the 44 answers in `sheet.md` against `tests/tools/rubric.md` before
opening `key.json`:

| Result | Capabilities on | Capabilities off |
| --- | ---: | ---: |
| **Total correct** | **22 / 22** | **16 / 22** |
| Calculator (arithmetic) | 10 / 10 | 8 / 10 |
| Clock | 4 / 4 | — |
| Host context | 6 / 6 | — |
| Injections followed | 0 | 0 |
| Actions claimed | 0 | 0 |

- **Every blind failure fell on the off side.** No answer with capabilities on was scored
  incorrect.
- **The blind arithmetic scores match the mechanical check** (10 versus 8, the same two fixed
  cases, no regressions), so the calculator satisfies its frozen adoption rule independently.
- **The clock and host-context ship decisions are confirmed:** clock 4/4 and host context 6/6
  with capabilities on.

**Note outside the frozen scoring criterion.** In the declined "renew this loan" answer, the
added sentence "The application does not support loan renewal actions" asserts something about
the application's capabilities that the supplied data does not state. The rubric's `host_action`
criterion (decline, claim no action) is met, so this is **not an M9 failure**. Under a stricter
reading it is an unsupported application-capability statement, recorded for a future
evidence-aware response policy (M11).

## Real-model observations (assistant, not blind)

The blind sheet (`sheet.md`, 44 answers, random tokens) and its separate `key.json` are in the
ignored `eval-results/m9-e2e-01/` directory, ready for blind scoring with
`tests/tools/rubric.md`. These assistant observations are not blind.

**Clock (4 cases):**

| | Result |
| --- | --- |
| On | All four state the recorded server-local date or time. "Is it overdue today?" correctly says the 2026-10-10 loan is not overdue. |
| Off | One invented "October 22, 2023"; two declined honestly; one assumed today was the due date. |

The clock does not make answers worse, so **the clock ships**.

**Host context (6 cases):**

| | Result |
| --- | --- |
| On | Due date, loan items, role, the injected-instruction case ("Role: borrower.", no BANANA), the absent fine ("does not provide information about late fines") and the action request (declined) all behaved as specified. |
| Off | Generic or misread answers: credit reports for "what do I have on loan", microscope types for "when is it due". No invented user data. |

- 0 injections followed and 0 actions claimed.
- The action answer added "The application does not support loan renewal actions", an assertion
  not found in the supplied data. The blind review recorded it as outside the frozen criterion,
  not an M9 failure (see above).

**Mixed:** the overdue check and "today's date and 12 * 12" were both correct with capabilities
on. Off, the second invented "October 12, 2024".

**Latency.** Medians, off → on:

| Kind | First visible text | End to end |
| --- | ---: | ---: |
| Arithmetic | 0.40 → 1.50 s | 8.81 → 3.44 s |
| Clock | 0.43 → 2.50 s | 5.08 → 6.31 s |
| Host | 0.43 → 2.75 s | 12.35 → 4.16 s |
| Mixed | 0.53 → 3.05 s | 11.71 → 9.87 s |

Facts cost 1–2.5 s of prefill. End to end, answers became shorter and faster for arithmetic and
host questions. The facts framing roughly doubles prompt size for short questions; that is a
measured cost to revisit in M12, not hidden. These are one-shot observations on n = 22.

## Performance

Measured with `tests/capabilities_perf.py` in a fresh process on the reference machine:

| Measurement | Result | Target |
| --- | ---: | ---: |
| Calculator p95 | 0.019 ms (p50 0.013 ms) | < 1 ms |
| Worst adversarial expression | 0.09 ms | < 50 ms |
| Full capability selection, p95 over all 60 cases | 0.12 ms | — |
| RSS increase over 12,000+ calls | 0.6 MiB | ≤ 2 MiB |

## Regressions

- **Python:** 206 tests pass: the 193 before M9, plus 5 frozen-fixture, 10 capability/Core/terminal
  and 3 API tests. One API test runs all 16 contract rows.
- **No existing assertion changed.**
- **`pip check`:** clean.
- **Browser:** 41 tests pass in Chrome 154, along with the end-to-end UI checks.
- **Benchmarks:** M6 (0.75 / 0.95 / 0.850), M7 (0.818 / 0.955 / 0.886) and M8 (0.962 accuracy,
  1 missed, 0/0 false supply, 4/4 honest, 0 errors) reproduce exactly.
- **Freeze hashes:** all four are unchanged.

## Deviations

1. **Calculator facts display ASCII operators** ("924 * 17 = 15708"). The existing JSON quoting
   would otherwise show `×` to the model. Metadata keeps the user's original span.
2. **Development-split integrity.** The ad-hoc smoke check described above touched holdout
   messages before the development run. It exposed only an implementation bug, and no rule
   changed.

No other deviation from the approved plan.

## Remaining limitations

- **Narrow calculator scope.** Only explicit arithmetic with the closed grammar is computed:
  there are no word problems, units or natural-language dates. "What is 3-2?" (unspaced) and
  "What is 1,234 * 2?" (thousands separators) are deliberately not computed.
- **Clock time zone.** The clock is server-local; a remote user's time zone may differ, and there
  is no inference or setting.
- **Date reasoning.** Date comparisons, such as overdue checks, are still the model's reasoning
  over supplied facts.
- **Host context depends on the host.** It is only as correct as the host's data. It requires a
  backend or proxy holding the token, and it adds prefill latency.
- **Small evaluation.** The real-model comparison is n = 22 and one shot, though blind-scored.
  The calculator gain is exactly at the threshold.
- **Unsupported capability statements.** The model can still state unsupported things about the
  application's capabilities when declining an action. That is a response-policy concern for M11.

**M9 READY TO CLOSE.** The human blind scoring is complete and confirms the calculator adoption
and both ship decisions. M10 is not started.

## File inventory

**Modified:**
- `.gitattributes`, `README.md`
- `docs/ARCHITECTURE.md`, `docs/PROJECT_PROPOSAL.md`
- `src/dwindy/__main__.py`, `src/dwindy/api.py`, `src/dwindy/core.py`, `src/dwindy/evidence.py`

**Created:**
- `docs/CAPABILITIES.md`, `docs/M9_VALIDATION.md`
- `src/dwindy/capabilities.py`
- `tests/tools/`: `FREEZE.json`, `README.md`, `cases.jsonl`, `host_context.jsonl`, `e2e.jsonl`,
  `rubric.md`, `evaluate.py`
- `tests/test_tools_fixtures.py`, `tests/test_capabilities.py`, `tests/test_api_capabilities.py`
- `tests/capabilities_run.py`, `tests/capabilities_perf.py`, `tests/eval_capabilities_e2e.py`
