"""Independent scale inputs only; no index creation or embedding calls."""
import hashlib
import random
from dwindy.ingest import Document


def documents():
    rng = random.Random(8163)
    words = 'parcel ledger custodian repair warranty approval session export account attachment incident booking delivery consent inquiry retention'.split()
    for i in range(1000):
        blocks = []
        for j in range(10):
            body = f'PERF{i:04}_{j:02} record. '+' '.join(rng.choice(words) for _ in range(160))
            blocks.append(body[:980]+'.')
        text = '\n\n'.join(blocks)+'\n'
        yield Document(f'perf-{i}',f'perf/{i}.txt',f'Performance record {i}', '.txt',text,hashlib.sha256(text.encode()).hexdigest())


def queries():
    for i in range(200):
        yield (f'PERF{i:04}_{i%10:02} record' if i%4==0 else 'Where can I recover a discarded attachment?' if i%4==1
               else 'Who approves the booking?' if i%4==2 else 'Write a story about a golden ledger.')


def identity():
    digest,total = hashlib.sha256(),0
    for d in documents():
        raw = d.text.encode('utf-8'); total+=len(raw)
        digest.update(d.id.encode()+b'\0'+str(len(raw)).encode()+b'\0'+raw)
    return dict(documents=1000,expected_chunks=10000,logical_source_bytes=total,source_sha256=digest.hexdigest(),
                query_sha256=hashlib.sha256(('\n'.join(queries())+'\n').encode()).hexdigest())
