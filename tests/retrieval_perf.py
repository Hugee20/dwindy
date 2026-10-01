"""Deterministic synthetic scale measurement; no language model or external I/O."""
import json
from pathlib import Path
import random
import sqlite3
import statistics
import tempfile
import threading
import time

from dwindy.ingest import sync
from dwindy.retrieval import RetrievalIndex


def run():
    import psutil  # Existing optional eval extra; measurement only.
    with tempfile.TemporaryDirectory(prefix='dwindy-retrieval-perf-') as folder:
        root=Path(folder)
        words='manual equipment visitor delivery policy retry laboratory coordination records storage maintenance schedule return process details approved reviewed information'.split()
        rng=random.Random(42)
        manifest=[]
        total=0
        for n in range(1000):
            parts=[]
            for section in range(10):
                prefix=f'Topic{n:04d} section{section:02d} identifier X{n:04d}{section:02d}. '
                body=prefix+' '.join(rng.choice(words) for _ in range(150))
                parts.append(body[:980]+'.')
            text='\n\n'.join(parts)+'\n'
            total+=len(text.encode())
            (root/f'd{n}.txt').write_text(text,encoding='utf-8')
            manifest.append(f'[[documents]]\nid="d{n}"\npath="d{n}.txt"\nname="Document {n}"\n')
        (root/'collection.toml').write_text('\n'.join(manifest),encoding='utf-8')
        proc=psutil.Process(); before=proc.memory_info().rss; peak=[before]; stop=threading.Event()
        def sample():
            while not stop.wait(.01): peak[0]=max(peak[0],proc.memory_info().rss)
        sampler=threading.Thread(target=sample); sampler.start()
        try:
            start=time.perf_counter(); sync(root/'collection.toml',root/'index.sqlite3'); indexing=time.perf_counter()-start
            start=time.perf_counter(); index=RetrievalIndex(root/'index.sqlite3'); opening=time.perf_counter()-start
            try:
                start=time.perf_counter(); index.search('Topic0013 section03 identifier'); first=time.perf_counter()-start
                durations=[]
                for n in range(200):
                    query=f'Topic{n:04d} section{n%10:02d} identifier'
                    start=time.perf_counter(); index.search(query); durations.append(time.perf_counter()-start)
                count=index.connection.execute('SELECT count(*) FROM chunks').fetchone()[0]
            finally: index.close()
        finally: stop.set(); sampler.join()
        print(json.dumps(dict(source_bytes=total,chunks=count,index_bytes=(root/'index.sqlite3').stat().st_size,
            index_seconds=indexing,index_open_validation_seconds=opening,first_query_seconds=first,
            warm_p50_seconds=statistics.median(durations),warm_p95_seconds=sorted(durations)[189],
            isolated_rss_increase_bytes=max(peak[0],proc.memory_info().rss)-before,
            note='First connection/query after indexing; OS filesystem cache was not flushed. RSS sampled every 10 ms.'),indent=2))


if __name__=='__main__': run()
