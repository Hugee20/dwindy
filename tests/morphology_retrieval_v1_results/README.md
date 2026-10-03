# Morphology retrieval v1 preserved development record

Disposition: **development-stage rejection; no adoption**. The fresh morphology
holdout remains sealed and unspent. Neither M11 holdout was used. Reach/H2 remains
deferred. No additional morphology candidate is authorized or planned.

This record is outside the frozen `tests/morphology_retrieval_v1/` directory.
Its freeze SHA-256 remains:

`6c1b8a9e252a55a878987082dc0f0e599ac8175486819d6b2697a988072d2bca`

See [the conclusion](../../docs/MORPHOLOGY_RETRIEVAL_V1_CONCLUSION.md) and
[the complete development report](dev_01/REPORT.md). The frozen README describes
the pre-execution state and is intentionally not revised.

## Original artifacts, preserved byte-for-byte

`dev_01/` is the original local `eval-results/morphology-dev-01/` run archive,
excluding the empty scratch directory. It contains 26 files:

- `development-observations.json`: 48 development cases times three arms; actual
  candidate/admission/supply records and original-token/stem audits.
- `development-report.json`: unchanged frozen evaluator output, including every
  pairwise change and individual gold score.
- `historical-report.json`: complete spent M6/M7/M8 diagnostics and historical gate.
- `mechanical.json`: all 24 structural probes passed.
- `performance/`: all 15 isolated trial files and aggregate summary; no removals.
- `final.json`: independent B/C gate results, rejected recommendation and environment.
- `validation.json`: original 343-test regression and hash/cleanup validation.
- `REPORT.md`, `run.py`, `report.py`: original report and orchestration scripts.
- `ARTIFACTS.json`: original SHA-256 map for the other 25 files.

The original artifact manifest SHA-256 is:

`41dfeea362febd3890bfcce8c3adeaa94c66fefcc943ec0146e385dc12c7a34c`

`checkpoint_validation.json` alongside this README records subsequent archival,
regression, historical hash and whitespace checks; it does not replace the
original run validation or relabel any evaluation result.

## Validation without retrieval or inference

From the repository root, use the existing Python environment:

```powershell
@'
import hashlib, json
from pathlib import Path
root = Path('tests/morphology_retrieval_v1_results/dev_01')
manifest = root / 'ARTIFACTS.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == '41dfeea362febd3890bfcce8c3adeaa94c66fefcc943ec0146e385dc12c7a34c'
expected = json.loads(manifest.read_text(encoding='utf-8'))
actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
assert actual == set(expected) | {'ARTIFACTS.json'}
for name, digest in expected.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
print('26 original artifacts verified')
'@ | .venv/Scripts/python.exe -B -
```

Git attributes disable newline conversion for the freeze and archive so their
byte hashes survive Windows checkout.

## Execution-script assumptions and stopping boundary

The archived runner derives the repository root from its original location:
`eval-results/morphology-dev-01/run.py`. Do not execute it directly from this
archive. Any separately authorized replay would copy the preserved archive to
that original relative location in an isolated checkout, preserve existing
outputs and verify the runtime/hash bindings before execution. Do not overwrite
recorded results to replay. The runner refuses output overwrites, and the frozen
evaluator rejects holdout scoring. These scripts are historical reproducibility
material, not authorization to rerun development, performance or holdout.

The original run validation mentions paths under ignored `eval-results/` and
the then-untracked fixture directory. Those statements describe that run; the
current archive is the reviewable standalone checkpoint record. No threshold,
label, evaluator, ranking or report was rewritten during archival.
