"""One bounded development experiment, outside the immutable evaluation.

No production globals are patched. Uses the native pinned Model2Vec encoder,
current FTS writer/search/Core, and the frozen arms/threshold grid. No Qwen call.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
    os.environ[key]='1'
os.environ.update(TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TRANSFORMERS_OFFLINE='1')

from contextlib import closing
from dataclasses import replace
import hashlib
import gzip
import json
from pathlib import Path
import socket
import sys
import time

REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'src'),str(REPO/'tests')]
from compact_semantic_matching_v1 import evaluate as ev
from compact_semantic_matching_v1.probes import PacketBackend
from compact_semantic_matching_v1.contract import embedding_view
from dwindy import context_policy as policy
from dwindy.backend import GenerationOptions,Message
from dwindy.core import DwindyCore
from dwindy.evidence import Evidence,Passage,Source
from dwindy.ingest import Document,write_documents
from dwindy.retrieval import RetrievalIndex,query_terms

FREEZE='8b61db931e3382e47edb1f1a36a9c1eb17262ebd971f829b970ec1ac4f95138a'
CACHE=REPO/'.cache/compact_semantic_matching_v1'
MODEL=CACHE/'models/potion'
NETWORK_ATTEMPTS=0


def deny_network(*args,**kwargs):
    global NETWORK_ATTEMPTS
    NETWORK_ATTEMPTS+=1
    raise AssertionError('Network is forbidden during local semantic evaluation')


def block_network():
    socket.socket.connect=deny_network
    socket.socket.connect_ex=deny_network
    socket.create_connection=deny_network
    socket.getaddrinfo=deny_network
    socket.gethostbyname=deny_network
    socket.gethostbyaddr=deny_network


def load_encoder():
    started=time.perf_counter()
    manifest=json.loads((CACHE/'acquisition.json').read_text())
    assert manifest['revision']=='bf8b056651a2c21b8d2565580b8569da283cab23'
    for item in manifest['files']:
        path=MODEL/item['path']
        if not path.is_file(): raise FileNotFoundError('semantic_model_unavailable: '+str(path))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('semantic_model_corrupt: '+str(path))
    from model2vec import StaticModel
    model=StaticModel.from_pretrained(MODEL,force_download=False)
    assert model.dim==256 and model.normalize
    return model,(time.perf_counter()-started)*1000


def fixture_documents():
    # Metadata for both initial splits may exist in the manifest, but only
    # development source bodies can be read/indexed by this runner.
    for d in ev.read('documents.json'):
        if d['split']!='dev':continue
        text=(ev.ROOT/d['path']).read_text(encoding='utf-8')
        yield Document(d['id'],d['path'],d['name'],'.txt',text,d['content_hash'],source_type=d['source_type'])


def entries(index):
    rows=index.connection.execute('''SELECT c.*,d.name,d.source_path,d.content_hash,d.source_type,f.body
        FROM chunks c JOIN documents d ON d.id=c.document_id JOIN chunks_fts f ON f.rowid=c.id
        ORDER BY d.id,c.ordinal''').fetchall()
    return tuple(Passage(Source(r['document_id'],r['chunk_key'],r['name'],r['source_path'],r['content_hash'],
                         r['line_start'],r['line_end'],r['start'],r['end'],r['heading'],r['source_type']),r['body'],0.) for r in rows)


def deduplicate(values,limit=12):
    result,seen=[],set()
    for p in values:
        digest=hashlib.sha256(p.text.encode()).hexdigest()
        if digest in seen or any(p.source.document_id==q.source.document_id and min(p.source.end,q.source.end)>max(p.source.start,q.source.start) for q in result):continue
        seen.add(digest);result.append(p)
        if len(result)==limit:break
    return tuple(result)


def hybrid(lexical,dense):
    fusion,original={},{}
    for values in (lexical,dense):
        for rank,p in enumerate(values,1):
            identity=p.source.chunk_id
            fusion[identity]=fusion.get(identity,0.)+1/(60+rank)
            original[identity]=p
    values=sorted(original.values(),key=lambda p:(-fusion[p.source.chunk_id],p.source.document_id,p.source.start))
    return deduplicate(values)


def encode(model,texts):
    return model.encode(list(texts),max_length=512,batch_size=256,show_progress_bar=False,use_multiprocessing=False)


def view_audit(model,p):
    view=embedding_view(p.text,p.source.heading,p.source.name,model='potion')
    full=model.tokenizer.encode(view,add_special_tokens=False)
    # Match Model2Vec's native max_length path, including its character cap and
    # unknown-token removal. Audit body offsets; never replace supplied text.
    capped=view[:512*model.median_token_length]
    retained=model.tokenizer.encode(capped,add_special_tokens=False)
    selected=[(i,span) for i,span in zip(retained.ids,retained.offsets) if i!=model.unk_token_id][:512]
    input_tokens=sum(i!=model.unk_token_id for i in full.ids)
    end=selected[-1][1][1] if selected else 0
    body_offset=len(view)-len(p.text)
    complete=capped==view and input_tokens<=512
    return dict(entry_id=p.source.document_id+':'+p.source.chunk_id,body_start=0,
                body_end=len(p.text) if complete else min(len(p.text),max(0,end-body_offset)),input_tokens=input_tokens,
                retained_tokens=len(selected),max_tokens=512)


def mapping(p,semantic=False):
    result=p.mapping()
    result.update(source_id=p.source.document_id,entry_id=p.source.document_id+':'+p.source.chunk_id)
    if semantic:result['cosine']=float(p.score)
    return result


class Experiment:
    def __init__(self,index,model=None):
        import numpy as np
        self.np=np;self.index=index;self.model=model
        self.passages=entries(index)
        self.positions={p.source.chunk_id:n for n,p in enumerate(self.passages)}
        self.audits={p.source.chunk_id:view_audit(model,p) for p in self.passages} if model else {}
        self.vectors=None
        if model:
            self.vectors=encode(model,[embedding_view(p.text,p.source.heading,p.source.name,model='potion') for p in self.passages]).astype('float32')
            assert self.vectors.shape==(len(self.passages),256)
            lengths=np.linalg.norm(self.vectors,axis=1)
            assert np.isfinite(self.vectors).all() and np.allclose(lengths,1,atol=1e-4)

    def observe(self,case,arm,threshold):
        started=time.perf_counter();timing=dict(query_encoding=0.,lexical_search=0.,dense_search=0.,fusion=0.,admission=0.,core_packet=0.)
        candidates=[];admitted=[];accepted=None;applied=False;error=None;decision_reason=None
        if arm=='A':
            def search(query,limit):
                t=time.perf_counter();values=self.index.search(query,limit)
                timing['lexical_search']+=(time.perf_counter()-t)*1000;candidates.extend(values)
                return values
            t=time.perf_counter();decision,evidence=policy.decide(case['query'],case['mode'],search=search,max_tokens=768)
            timing['admission']=(time.perf_counter()-t)*1000-timing['lexical_search']
            decision_reason=decision.reason
            applied=decision.reason in ('relevant_match','weak_match','no_candidates')
            accepted=bool(evidence and evidence.passages) if applied else None
            admitted=list(evidence.passages) if evidence else []
            acquisition='found' if candidates else 'no_match' if decision.attempted else 'not_used'
        else:
            shape=policy.classify(case['query'])
            terms=query_terms(case['query'])
            bypass=shape in ('conversational','history','self_contained') or len(case['query'].encode())>2048 or (not terms and shape!='directed') or case['mode']=='off'
            evidence=None
            if bypass:
                acquisition='not_used';decision_reason=shape or 'no_terms'
            else:
                t=time.perf_counter();q=encode(self.model,[case['query']])[0]
                timing['query_encoding']=(time.perf_counter()-t)*1000
                lexical=()
                if arm in ('R','H'):
                    t=time.perf_counter();lexical=self.index.search(case['query'],12)
                    timing['lexical_search']=(time.perf_counter()-t)*1000
                dense=()
                t=time.perf_counter()
                if arm=='R':
                    lexical=tuple(replace(p,score=float(self.np.clip(self.vectors[self.positions[p.source.chunk_id]]@q,-1,1))) for p in lexical)
                else:
                    similarities=self.vectors@q
                    order=self.np.argsort(-similarities,kind='stable')
                    dense=deduplicate(tuple(replace(self.passages[int(n)],score=float(self.np.clip(similarities[n],-1,1))) for n in order))
                    if arm=='H':lexical=tuple(replace(p,score=float(self.np.clip(similarities[self.positions[p.source.chunk_id]],-1,1))) for p in lexical)
                timing['dense_search']=(time.perf_counter()-t)*1000
                t=time.perf_counter()
                candidates=list(dense if arm=='S' else hybrid(lexical,dense) if arm=='H' else sorted(lexical,key=lambda p:(-p.score,p.source.document_id,p.source.start)))
                timing['fusion']=(time.perf_counter()-t)*1000
                acquisition='found' if candidates else 'no_match'
                t=time.perf_counter();applied=shape!='directed' and case['mode']!='on'
                admitted=[p for p in candidates if not applied or p.score>=threshold]
                accepted=bool(admitted) if applied else None
                if admitted:evidence=Evidence(tuple(admitted),768,'plain' if applied else 'insufficient')
                elif not applied:evidence=Evidence((),768)
                timing['admission']=(time.perf_counter()-t)*1000
                decision_reason='semantic_match' if admitted else 'semantic_rejected' if candidates else 'no_candidates'
        backend=PacketBackend();core=DwindyCore(backend,options=GenerationOptions(max_tokens=256))
        history=tuple(Message(**m) for m in case.get('history',[]));core.restore(history)
        t=time.perf_counter()
        with closing(core.chat(case['query'],evidence=evidence)) as stream:event=next(stream)
        timing['core_packet']=(time.perf_counter()-t)*1000
        assert core.snapshot()==history and backend.calls==0
        ids={s['chunk_id'] for s in (event.retrieval or {}).get('sources',[])}
        supplied=[p for p in admitted if p.source.chunk_id in ids]
        supply='supplied' if supplied else 'budget_exhausted' if admitted else 'not_used' if acquisition=='not_used' else 'no_match'
        public_ids=list(dict.fromkeys(p.source.document_id for p in supplied))
        timing['selection']=(time.perf_counter()-started)*1000
        semantic=arm!='A'
        return dict(id=case['id'],arm=arm,candidates=[mapping(p,semantic) for p in candidates],admitted=[mapping(p,semantic) for p in admitted],
            supplied=[mapping(p,semantic) for p in supplied],acquisition_state=acquisition,supply_state=supply,error=error,
            candidate_probe_only=False,admission_trace=dict(applied=applied,accepted=accepted),encoding_audit=[self.audits[p.source.chunk_id] for p in candidates] if semantic else [],
            public_source_ids=public_ids,public=dict(state=supply,source_ids=public_ids),budget_oracle='utf8_quarters_v1',dropped_turns=event.dropped_turns,
            latency_ms=timing,generation_calls=backend.calls,network_calls=NETWORK_ATTEMPTS,decision_reason=decision_reason,core_retrieval=event.retrieval)


def run_dev(output):
    assert ev.verify_manifest()==FREEZE;ev.verify_bindings()
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    block_network();model,startup=load_encoder()
    index_path=output/'dev.sqlite'
    write_documents(fixture_documents(),index_path)
    index=RetrievalIndex(index_path)
    try:
        experiment=Experiment(index,model)
        cases=ev.load_cases('dev')
        all_results=[]
        for threshold in ev.read('protocol.json')['thresholds']:
            records=[experiment.observe(c,arm,threshold) for c in cases for arm in ev.ARMS]
            result=ev.evaluate(records)
            (output/f'raw_{threshold:.2f}.json.gz').write_bytes(gzip.compress(json.dumps(records,ensure_ascii=False,separators=(',',':')).encode('utf-8'),mtime=0))
            (output/f'score_{threshold:.2f}.json.gz').write_bytes(gzip.compress(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf-8'),mtime=0))
            summary=dict(threshold=threshold,summary=result['summary'],quality_screens=result['quality_screens'])
            all_results.append(summary)
            print(json.dumps(dict(threshold=threshold,quality_screens=result['quality_screens'])),flush=True)
        summary=dict(model='potion',freeze_sha256=FREEZE,startup_ms=startup,network_attempts=NETWORK_ATTEMPTS,generation_calls=0,profiles=all_results)
        (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
        assert ev.verify_manifest()==FREEZE and NETWORK_ATTEMPTS==0
    finally:index.close()


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Explicit new development output directory required')
    run_dev(sys.argv[1])
