"""Run the frozen Project Awareness benchmark against a freshly synchronized fixture."""
import argparse
import json
from pathlib import Path
import tempfile

from dwindy.project import synchronize
from dwindy.retrieval import RetrievalIndex
from project.evaluate import evaluate
from project_support import materialize

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split',choices=['dev','holdout','all'],default='dev')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='dwindy-project-eval-') as folder:
        report=synchronize(materialize(folder))
        index=RetrievalIndex(Path(folder)/'index.sqlite3')
        try:
            result=evaluate(lambda q:[p.mapping() for p in index.search(q)],None if args.split=='all' else args.split)
        finally: index.close()
    result['rank1_misses']=[c for c in result['cases'] if c['answerable'] and c['rank']!=1]
    result['negative_nonempty_cases']=[c for c in result['cases'] if not c['answerable'] and c['returned']]
    result['selected']=report['selected']
    print(json.dumps(result,indent=2))
