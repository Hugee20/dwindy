# M8 context selection

When a retrieval index is configured, Dwindy decides for each turn whether local passages
deserve a place in the model's context. This is a **context-selection policy**, not an
intent classifier or a router. It makes no model call: ordinary generation remains the only
model call per turn.

**Principle: attempt liberally, supply conservatively.** Searching the local index costs
milliseconds. Supplying passages costs prompt tokens and seconds of CPU prefill, and
irrelevant passages can distract a small model. So the policy searches cheaply but supplies
evidence only when it is worth it.

Four things stay separate:

| Step | Owner | What it means |
| --- | --- | --- |
| Context selection | `context_policy.py` (M8) | Whether to search, and whether found passages deserve context |
| Retrieval relevance | M6 search (unchanged) | Which passages match the query lexically |
| Answerability | The model, under M6/M7 instructions | Whether supplied passages contain the answer |
| Generation | The model | The response |

Lexical overlap decides only whether evidence is worth supplying. It is never treated, or
reported, as proof that a passage answers the question.

## Retrieval modes

| Mode | Behavior |
| --- | --- |
| `off` | Never retrieve. Model input is identical to ordinary chat. |
| `on` | Forced retrieval with exact M6/M7 behavior: the same response metadata, the "local material is insufficient" instruction when nothing fits, and a 503 when retrieval fails. For debugging, evaluation and explicit API use. |
| `auto` | The policy below decides per turn. |

The mode for a turn is resolved in this order:

1. **The request:** `retrieval: true` (on), `false` (off) or `"auto"`.
2. **API configuration:** `retrieval_default = "auto"` or `"off"`. `"on"` is not accepted;
   forced retrieval is per request only.
3. **Built-in default:** `auto` when `retrieval_index_path` is configured. With no index there
   is no retrieval.

A developer who configures and synchronizes an index has said that Dwindy should act as an
assistant for that material, so `auto` is the normal mode. The server prints one line at
startup naming the active default and how to change it.

### Migration from M6/M7

| Situation | Before M8 | From M8 | To keep the old behavior |
| --- | --- | --- | --- |
| No index | Ordinary chat | Unchanged | — |
| Index configured, client omits `retrieval` | Ordinary chat | `auto`; every JSON reply and SSE `started` event includes a `retrieval` object | `retrieval_default = "off"` |
| `retrieval: false` / `true` | Off / forced | Unchanged | — |
| An M6/M7 widget copy with its box unchecked (it omits the field) | Off | `auto` | Update the widget, or set `"off"` |

Health adds `retrieval_default` whenever an index is configured.

## The policy (`auto`)

```text
message > 2,048 bytes                          -> ordinary chat        message_too_long
fast paths, from the closed cue table:
  project name | "this/your system, app, project…" | "the documentation"… |
  identifier (a_b, camelCase) | source path      -> project-directed
  only pleasantries ("Hello!", "ok bye")         -> ordinary chat        conversational
  conversation-history reference                 -> ordinary chat        history_reference
  creative verb + creative noun, or transformation verb + supplied text
                                                 -> ordinary chat        self_contained_task
project-directed  -> search (the query, not the message, has "this system" replaced by the
                     project name); supply what is found, or use the M6 insufficient-material
                     instruction if nothing is found                    project_directed
everything else   -> search, then the usefulness check:
     supply only if one ordinary passage among the top three contains at least half of
     the query's search terms (generated overview/metadata documents never count)
                                                 -> supply              relevant_match
                                                 -> ordinary chat       weak_match | no_candidates | no_terms
```

The original user message is always what the model sees and what history stores. The
project-name replacement changes only the search query, and only for the closed list of
system-reference phrases. It never grows into general query rewriting.

Opportunistic supply (`relevant_match`) uses `Evidence(fallback="plain")`. If no passage fits
the token allowance, the turn becomes ordinary chat (reason `budget_exhausted`) instead of
producing the M6 "insufficient material" reply. Project-directed and forced retrieval keep
M6 semantics.

### Complexity boundary

The cue table in `context_policy.py` is the policy's only phrase list, and it is capped at
**60 entries** (58 used). A test enforces the cap. Cues may express only high-certainty fast
paths:

- pleasantries;
- conversation-history references;
- self-contained creative or transformation requests;
- strong project references;
- identifier shapes;
- source paths.

All cues are English and match whole words. A cue is never added to repair a single
evaluation case. Anything ambiguous falls through to retrieval and the usefulness check.
"Where is…" is deliberately not a cue ("Where is Paris?").

Measured misses caused by word forms (cancel versus cancellations) or language are reported
rather than patched with stemming, synonyms or translation. They may motivate a later,
separately evaluated Capability Density experiment.

## Failure behavior

| Situation | `on` | `auto`, opportunistic | `auto`, project-directed |
| --- | --- | --- | --- |
| No index | 503 `retrieval_disabled` | Ordinary chat, `no_index` | Ordinary chat, `no_index` |
| No or weak matches | M6 behavior | Ordinary chat | M6 insufficient-material instruction |
| Nothing fits the allowance | M6 behavior | Ordinary chat, `budget_exhausted` | M6 behavior |
| Retrieval error, SQLite busy or storage worker busy | 503 | Ordinary chat; status `unavailable`, reason `retrieval_unavailable` / `retrieval_busy` | See below |
| Unexpected policy error | n/a | Ordinary chat, `policy_error` | Same |

A project-directed retrieval failure uses the **constrained fallback**. No passages are
supplied, and a transient instruction is added:

> Local project information needed for this question could not be accessed. Do not state or
> guess project-specific facts. Tell the user the project information is currently
> unavailable; answer only parts that do not depend on the project.

Whether this ships was decided by the frozen real-model adoption rule; see the
[M8 validation report](M8_VALIDATION.md). Instructions and evidence are never stored in
history or persistence.

## Metadata

For `on`, the `retrieval` object is unchanged from M6. For `off`, it is absent. For `auto`,
it is present on every turn:

```json
{"mode":"auto","attempted":true,"status":"supplied","reason":"relevant_match","sources":[...]}
```

| Key | Values |
| --- | --- |
| `status` | `supplied`, `no_match`, `budget_exhausted` (M6 meanings), `not_used` (ordinary chat), `unavailable` |
| `reason` | `conversational`, `history_reference`, `self_contained_task`, `no_terms`, `no_candidates`, `weak_match`, `relevant_match`, `project_directed`, `budget_exhausted`, `message_too_long`, `no_index`, `retrieval_unavailable`, `retrieval_busy`, `policy_error` |
| `query_normalized` | `true` only when the project-name replacement was applied |

There are no scores and no confidence values. Metadata is transient.

## Python, terminal and browser

**Python:**

```python
from dwindy.context_policy import decide
decision, evidence = decide(text, "auto", search=index.search, project_name=index.project_snapshot["name"])
for event in core.chat(text, evidence=evidence): ...   # decision.metadata(turn_started.retrieval)
```

**Terminal:** `--retrieval-index PATH` with `--retrieval auto|on|off` (default `auto`). It
prints `[Local context: N passage(s).]` when passages are supplied. Without these flags the
terminal is unchanged.

**Browser:** checked means `auto` and unchecked sends `false`. The box starts checked when
health reports `retrieval_default: "auto"`. The status line reads:

- the passage count when passages were supplied;
- "Local material checked; none used." when local material was searched but not used;
- "Local project information was unavailable." when retrieval failed.

The checkbox is a transitional developer and evaluation control. A deployment built as a
project assistant should not need end users to understand or enable "project context".
