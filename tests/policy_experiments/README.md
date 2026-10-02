# Historical policy experiments

The v3 source and focused tests here are byte-for-byte copies preserved before
foundation runtime assembly. PRESERVED.json records their hashes. load_v3.py
binds them to separate test-only modules; production modules are never replaced.
The top-level historical test wrappers retain their original assertions. Passing
these tests describes the old experimental representation, not adoption or
foundation acceptance. The failed original development screens and uninspected
holdout remain recorded in tests/policy and docs/M11_DEVELOPMENT*.md.

The original development runner and its recorded candidate-source/ablation
artifacts remain unchanged. Use eval_policy_foundation_dev.py for the separately
frozen narrowed hypothesis; it has no holdout execution option. Historical
quoted-history helpers are not part of the production runtime.


M11 development is concluded; both original and Foundation holdouts remain sealed/unspent.
Neither hypothesis was adopted as a complete response policy. `foundation_v1/` and
`foundation_v2/` preserve exact Core/evidence source matching their recorded run manifests,
plus their runner/test source. Their PRESERVED.json files check every archived byte.
`archive.py` binds each version into distinct modules. Immutable input data classes are
shared only after their definition source is checked identical, for fixture compatibility; all framing, instructions and Core execution come from the
archived version. No production module is replaced. Frozen probes are loaded unchanged into
version-specific namespaces with explicit historical imports.

Historical results remain distinct: Foundation v1 frozen 32/32; Foundation v2 frozen 30/32
with the two exact-old-sentence failures; versioned v2 compatibility 32/32. These are historical
mechanics, not adoption. `runners/` additionally preserves the broad v3 runner byte-for-byte.
The top-level historical runner commands now fail closed to prevent accidental inference or
silent evaluation of cleaned production as an old candidate. Model-free test entry points use
archived implementations. Any further inference requires separately approved work.

Original broad-candidate raw results/source hashes and available source snapshots remain under
local eval-results; no unavailable source is reconstructed or historical result overwritten.
No weights, secrets or personal conversations are included in the source archives. History
quoting/decoding belongs only to historical experiment support, never production assertions.
