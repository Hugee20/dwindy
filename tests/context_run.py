"""Run the frozen M8 context-selection evaluation (development split unless asked otherwise)."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import tempfile

from dwindy.context_policy import decide
from dwindy.project import synchronize
from dwindy.retrieval import RetrievalIndex
from context.evaluate import evaluate
from project_support import materialize

EXTRA = Path(__file__).parent/'context'/'extra'


@contextmanager
def fixture_index():
    """The frozen M7 Lantern Desk fixture plus the frozen M8 extra manifest."""
    with tempfile.TemporaryDirectory(prefix='dwindy-context-eval-') as folder:
        shutil.copytree(EXTRA, Path(folder)/'extra')
        synchronize(materialize(folder, documents_manifest='extra/collection.toml'))
        index = RetrievalIndex(Path(folder)/'index.sqlite3')
        try:
            yield index
        finally:
            index.close()


def outcome(evidence):
    if evidence is None:
        return 'direct'
    if evidence.fallback == 'unavailable':
        return 'unavailable'
    return 'context' if evidence.passages else 'honest_empty'


def decide_fn(index):
    name = index.project_snapshot['name'] if index.project_snapshot else None
    def run(case):
        decision, evidence = decide(case['message'], 'auto', search=index.search, project_name=name)
        # Core supplies at most three passages, so only those can reach the model.
        paths = [p.source.source_path for p in evidence.passages[:3]] if evidence else []
        return dict(outcome=outcome(evidence), attempted=decision.attempted, source_paths=paths, reason=decision.reason)
    return run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['dev', 'holdout', 'all'], default='dev')
    args = parser.parse_args()
    with fixture_index() as index:
        result = evaluate(decide_fn(index), None if args.split == 'all' else args.split)
    print(json.dumps({k: result[k] for k in ('overall', 'splits', 'categories', 'failures')}, indent=2))
    for case in result['cases']:
        print(f"{case['id']:28} {case['expected']:8} {case['outcome']:13} {case['reason']:20} {','.join(case['source_paths'])}")
