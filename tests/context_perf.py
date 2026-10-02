"""M8 context-selection overhead on the frozen fixture and the M7 scale project; no model.

Each measurement runs in a fresh process so earlier work cannot pre-grow its heap.
"""
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import time

from dwindy.context_policy import decide
from dwindy.retrieval import RetrievalIndex

FAST = ['Hello!', 'Write me a short poem.', 'Can you repeat your previous answer?',
        'Translate to Spanish: The loan duration is eight days.']
FIXTURE_SEARCHED = ['How do I reserve a microscope?', 'What is the capital of France?', 'Where is the returns logic?',
                    'What does this system do?', 'What is photosynthesis?', 'Which ledger do calibration records use?']


def timings(fn, rounds):
    durations = []
    for _ in range(rounds):
        start = time.perf_counter(); fn(); durations.append(time.perf_counter()-start)
    return dict(p50_ms=statistics.median(durations)*1000, p95_ms=sorted(durations)[int(len(durations)*.95)-1]*1000)


def phase(kind, index_path):
    import psutil  # Existing optional eval extra; measurement only.
    proc = psutil.Process()
    index = RetrievalIndex(index_path)
    try:
        name = index.project_snapshot['name'] if index.project_snapshot else None
        if kind == 'fixture':
            messages = FIXTURE_SEARCHED
        else:
            messages = [f'Topic{n % 55:03d} section{n % 110:02d} handler_{n % 30:02d}_{n:03d}' for n in range(200)]
            messages += ['How long is the review process for maintenance records?', 'What is the capital of France?']
        index.search('warm up', 12)
        before = proc.memory_info().rss
        cycle = iter(messages * 400)
        searched = timings(lambda: decide(next(cycle), 'auto', search=index.search, project_name=name), 400)
        plain = iter(messages * 400)
        search_only = timings(lambda: index.search(next(plain), 12), 400)
        fast = iter(FAST * 500)
        fast_paths = timings(lambda: decide(next(fast), 'auto', search=index.search, project_name=name), 2000)
        off = timings(lambda: decide('How do I reserve a microscope?', 'off'), 2000)
        rss = proc.memory_info().rss - before
        chunks = index.connection.execute('SELECT count(*) FROM chunks').fetchone()[0]
    finally:
        index.close()
    return dict(chunks=chunks, auto_with_search=searched, search_alone=search_only, fast_paths=fast_paths,
                off=off, rss_increase_bytes=rss)


def run():
    sys.path.insert(0, str(Path(__file__).parent))
    from context_run import fixture_index
    from project_perf import build
    from dwindy.project import synchronize
    results = {}
    with fixture_index() as index, tempfile.TemporaryDirectory(prefix='dwindy-context-perf-') as folder:
        index_path = index.connection.execute('PRAGMA database_list').fetchone()[2]
        root = Path(folder)
        synchronize(build(root, random.Random(42)))
        for kind, path in (('fixture', index_path), ('m7_scale', str(root/'index.sqlite3'))):
            output = subprocess.run([sys.executable, __file__, kind, path], capture_output=True, text=True, check=True).stdout
            results[kind] = json.loads(output)
    results['note'] = ('Warm OS cache, fresh process per index, after one warm-up search. RSS is the increase '
                       'across 2,800+ decisions after the index was opened. No model is loaded.')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    if len(sys.argv) == 3: print(json.dumps(phase(sys.argv[1], sys.argv[2])))
    else: run()
