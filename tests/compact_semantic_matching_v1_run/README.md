# Isolated development runner

This directory is experimental implementation machinery **outside** the frozen
`compact_semantic_matching_v1` evaluation and outside production Dwindy. The user
authorized one practical smallest-stack development decision in the completion
directive of 2026-10-03. Model2Vec 0.9.0/potion-base-8M was tested; it was not adopted.
See `docs/COMPACT_SEMANTIC_MATCHING_V1_CONCLUSION.md`.

`acquire.py` is an explicit public-artifact acquisition step, with pinned revision
and hashes. The isolated environment, wheels and model weights live in ignored
`.cache/compact_semantic_matching_v1/`; base Dwindy does not require Model2Vec.
`runner.py` uses the native local encoder, existing FTS writer, context policy and
Core. It blocks network/DNS and closes Core's lazy stream at `TurnStarted`, before
generation. It loads only development cases and source bodies. All seven frozen
thresholds and all A/R/S/H arms are recorded separately; no response tuning occurs.

Source text and IDs are preserved through each stage. Actual supply comes from
Core's packet metadata, not an admission guess. Model-free accounting is explicitly
the frozen oracle, not a claim about Qwen tokenizer behavior. Cosines and encoder
view audits are internal; the public evaluation projection is only supply state
and supplied source IDs. This implements the evaluation concept, not a production
API or UI contract.

Historical bindings in `dev_potion_01/ARTIFACTS.json` include this runner, acquisition
code, evaluator, fixtures' freeze and the production modules used. Package versions
and wheel hashes are in `dependency_footprint.json`, model artifacts in
`acquisition.json`. Do not silently redirect historical observations to changed
runtime code. No holdout runner or automatic candidate iteration is provided.

No quality profile passed, so the frozen stop rule ended the line before full
resource/historical retrieval measurement. Development-query latency is diagnostic
only; it must not be presented as a resource-gate pass. Re-running acquisition or
evaluation is not part of ordinary regression tests.
