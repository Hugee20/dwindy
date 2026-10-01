"""Deterministic synthetic Project Awareness scale measurement; no model or external I/O.

The scale project sits just inside the M7 limits: 96 selected files (~9 MiB) with the
overview's 100-entry cap, plus ignored and hard-excluded trees that must not be read.
"""
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import threading
import time

from dwindy.project import synchronize
from dwindy.retrieval import RetrievalIndex

WORDS = ('manual equipment visitor delivery policy retry laboratory coordination records storage '
         'maintenance schedule return process details approved reviewed information').split()


def build(root, rng):
    host = root/'host'
    for folder in ('docs', 'src', 'config', 'docs/archive', 'node_modules/pkg'):
        (host/folder).mkdir(parents=True, exist_ok=True)
    (host/'.gitignore').write_text('docs/archive/\n', encoding='utf-8')
    (host/'README.md').write_text('# Scale project\n\nSynthetic measurement fixture.\n', encoding='utf-8')
    for n in range(55):
        sections = [f'## Topic{n:03d} section{s:02d}\n\nIdentifier X{n:03d}{s:02d}. ' + ' '.join(rng.choice(WORDS) for _ in range(150))
                    for s in range(110)]
        (host/f'docs/guide{n:03d}.md').write_text('# Guide %d\n\n' % n + '\n\n'.join(sections) + '\n', encoding='utf-8')
    for n in range(300):
        (host/f'docs/archive/old{n:03d}.md').write_text('archived\n', encoding='utf-8')
        (host/f'node_modules/pkg/f{n:03d}.md').write_text('dependency\n', encoding='utf-8')
    sources = []
    for n in range(30):
        body = ''.join(f'def handler_{n:02d}_{f:03d}(value):\n    """Process {rng.choice(WORDS)} {rng.choice(WORDS)}."""\n'
                       f'    return value + {f}\n\n' for f in range(600))
        (host/f'src/module{n:02d}.py').write_text(body, encoding='utf-8')
        sources.append(f'src/module{n:02d}.py')
    configs = []
    for n in range(10):
        (host/f'config/c{n:02d}.toml').write_text('\n'.join(f'key_{k} = {k}' for k in range(800)) + '\n', encoding='utf-8')
        configs.append(f'config/c{n:02d}.toml')
    config = root/'project.toml'
    config.write_text(f'project_id = "scale"\nname = "Scale"\nroot = "host"\nindex_path = "index.sqlite3"\n'
                      f'source_files = {json.dumps(sources)}\nconfig_files = {json.dumps(configs)}\n', encoding='utf-8')
    return config


def measured(proc, fn):
    before = proc.memory_info().rss; peak = [before]; stop = threading.Event()
    def sample():
        while not stop.wait(.01): peak[0] = max(peak[0], proc.memory_info().rss)
    sampler = threading.Thread(target=sample); sampler.start()
    try:
        start = time.perf_counter(); value = fn(); seconds = time.perf_counter()-start
    finally: stop.set(); sampler.join()
    return value, seconds, max(peak[0], proc.memory_info().rss)-before


def phase(name, folder):
    """One measurement in a fresh process, so earlier phases cannot pre-grow its heap."""
    import psutil  # Existing optional eval extra; measurement only.
    proc, root = psutil.Process(), Path(folder)
    config = root/'project.toml'
    if name == 'search':
        def fn():
            index = RetrievalIndex(root/'index.sqlite3')
            try:
                start = time.perf_counter(); index.search('Topic013 section03 identifier'); first = time.perf_counter()-start
                durations = []
                for n in range(200):
                    query = f'Topic{n % 55:03d} section{n % 110:02d} handler_{n % 30:02d}_{n:03d}'
                    start = time.perf_counter(); index.search(query); durations.append(time.perf_counter()-start)
                chunks = index.connection.execute('SELECT count(*) FROM chunks').fetchone()[0]
            finally: index.close()
            return dict(chunks=chunks, first_query_seconds=first, warm_p50_seconds=statistics.median(durations),
                        warm_p95_seconds=sorted(durations)[189])
    else:
        def fn():
            report = synchronize(config, dry_run=name == 'dry_run')
            return dict(selected_files=len(report['selected']), source_bytes=report['source_bytes'], write=report.get('write'))
    value, seconds, rss = measured(proc, fn)
    return dict(value, seconds=seconds, rss_increase_bytes=rss)


def run():
    with tempfile.TemporaryDirectory(prefix='dwindy-project-perf-') as folder:
        build(Path(folder), random.Random(42))
        results = {}
        for name in ('dry_run', 'full_sync', 'unchanged_resync', 'search'):
            output = subprocess.run([sys.executable, __file__, name, folder], capture_output=True, text=True, check=True).stdout
            results[name] = json.loads(output)
        results['index_bytes'] = (Path(folder)/'index.sqlite3').stat().st_size
        results['note'] = ('Each phase in a fresh process after imports; files were just written, so the OS '
                           'cache was warm. RSS sampled every 10 ms.')
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    if len(sys.argv) == 3: print(json.dumps(phase(sys.argv[1], sys.argv[2])))
    else: run()
