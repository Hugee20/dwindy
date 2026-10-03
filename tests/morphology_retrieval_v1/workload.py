"""Frozen synthetic performance inputs, disjoint from both relevance splits.

This module generates inputs only; no indexing, timings or scoring on import.
Measure in separately authorized isolated processes according to performance.json.
"""
import hashlib
import random
from dwindy.ingest import Document

SEED = 42
DOCUMENTS = 1000
BLOCKS = 10
WORDS_PER_BLOCK = 150
WORD_LIST = ('equipment pump pumps inspected inspection calibration calibrated sensor sensors '
             'return returned crate crates renewal renewed badge badges archive archived '
             'operator operation material materials register registered document approval '
             'delivery policy workshop coordination storage schedule maintenance').split()


def documents():
    rng = random.Random(SEED)
    for n in range(DOCUMENTS):
        parts = []
        for section in range(BLOCKS):
            prefix = f'Topic{n:04d} section{section:02d} identifier X{n:04d}{section:02d}. '
            body = prefix+' '.join(rng.choice(WORD_LIST) for _ in range(WORDS_PER_BLOCK))
            parts.append(body[:980]+'.')
        text = '\n\n'.join(parts)+'\n'
        yield Document(f'scale{n}',f'scale{n}.txt',f'Scale {n}', '.txt',text,hashlib.sha256(text.encode()).hexdigest())


def queries():
    for n in range(200):
        # Mix identifier-dominated, morphology, generic and irrelevant probes.
        yield (f'Topic{n:04d} section{n%10:02d} identifier' if n%4==0 else
               f'Topic{n:04d} inspected pumps' if n%4==1 else
               'badge renewals archive' if n%4==2 else 'stellar fusion astronomy')


def identity():
    digest = hashlib.sha256()
    total = 0
    for document in documents():
        data = document.text.encode('utf-8')
        total += len(data)
        # Identity includes key, byte count and exact content, not only concatenation.
        digest.update(document.id.encode()+b'\0'+str(len(data)).encode()+b'\0'+data)
    return dict(documents=DOCUMENTS,logical_source_bytes=total,source_sha256=digest.hexdigest(),
                query_sha256=hashlib.sha256(('\n'.join(queries())+'\n').encode()).hexdigest())
