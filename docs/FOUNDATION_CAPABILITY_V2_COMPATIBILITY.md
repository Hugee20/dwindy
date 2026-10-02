# Foundation capability wording v2 compatibility check

This is a versioned implementation compatibility check, not a replacement,
correction, or retroactive pass of the frozen `policy_foundation_v1` evaluation.
Its frozen files, rubric, gates, and holdout are unchanged.

The only production change replaces the trusted runtime sentence with:

`DWINDY/action-capability: Dwindy (this assistant) cannot perform actions in the host application.`

`tests/foundation_capability_v2.py` observes the same four frozen capability
profiles with the same inputs, contract fields, trigger conditions, authority,
placement, and budgets. Only recognition of the exact approved sentence differs.
The other 28 observers delegate to the unchanged frozen implementation. Separate
mechanical audits check placement, token accounting, transience, and one generation;
these introduce no semantic acceptance criterion. A negative test demonstrates
that missing runtime wording fails rather than copying expected answers.

Pre-inference results: frozen Foundation probes **30/32**, with `capability_1`
and `capability_2` failing the old exact-sentence checks; compatibility capability
profiles **4/4**, unchanged remaining profiles **28/28**, combined compatibility
checks **32/32**. All 317 Python tests pass, including the original 48 plumbing
profiles. Both historical freeze hashes match. No frozen failure is relabeled.

`tests/eval_policy_foundation_v2_dev.py` retains the development-only paired
protocol and checks both results separately before inference. Outputs go to a
new run directory. This adapter does not authorize holdout inference or adoption.
Semantic scoring still uses the unchanged Foundation rubric and gates.
