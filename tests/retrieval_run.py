"""Run the frozen model-independent benchmark against the concrete index."""
import argparse
import json
from pathlib import Path
import tempfile
from dwindy.ingest import sync
from dwindy.retrieval import RetrievalIndex
from retrieval.evaluate import evaluate

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split',choices=['dev','holdout','all'],default='dev')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='dwindy-retrieval-eval-') as folder:
        path=Path(folder)/'retrieval.sqlite3'
        sync(Path(__file__).parent/'retrieval/collection.toml',path)
        index=RetrievalIndex(path)
        try:
            print(json.dumps(evaluate(lambda q:[p.mapping() for p in index.search(q)],
                                     None if args.split=='all' else args.split),indent=2))
        finally: index.close()
