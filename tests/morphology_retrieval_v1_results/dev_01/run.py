"""Approved development/performance/historical orchestration outside the freeze.
No holdout execution, production patching, network or model call.
"""
import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import types

REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'src'),str(REPO/'tests')]
from morphology_retrieval_v1 import evaluate as ev, reference as ref, workload
from dwindy import context_policy as policy, ingest, retrieval, project
from dwindy.backend import GenerationOptions
from dwindy.core import DwindyCore

OUT=Path(__file__).resolve().parent
EXPECTED='6c1b8a9e252a55a878987082dc0f0e599ac8175486819d6b2697a988072d2bca'


def save(name,value):
    path=OUT/name
    if path.exists():raise AssertionError('Never overwrite an existing run artifact: '+name)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def verify():
    assert ev.verify_freeze()==EXPECTED
    ref.verify_runtime_sources()
    for name,digest in json.loads((ev.ROOT/'historical.json').read_text())['files'].items():
        assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==digest,name


def kernel(index):
    """Frozen algorithms with isolated timing callbacks; no audit-only replay.

Inclusive search/usefulness and nested normalization are reported independently;
exclusive components are computed by subtraction, never added twice.
"""
    clock={}
    def add(key,duration):clock[key]=clock.get(key,0.0)+duration
    def measured(name,fn):
        def call(*a,**kw):
            start=time.perf_counter()
            try:return fn(*a,**kw)
            finally:add(name,time.perf_counter()-start)
        return call
    ns=dict(retrieval.RetrievalIndex.search.__globals__)
    ns['match_query']=measured('fts_query_construction',retrieval.match_query)
    search_fn=types.FunctionType(retrieval.RetrievalIndex.search.__code__,ns, 'search',retrieval.RetrievalIndex.search.__defaults__)
    search_fn.__kwdefaults__=retrieval.RetrievalIndex.search.__kwdefaults__
    bound=types.MethodType(search_fn,index)
    search=measured('search_inclusive',bound)
    if index.arm=='C':
        index.normalizer.normalize=measured('porter_normalization',index.normalizer.normalize)
    def useful(values,terms):
        return policy.useful(values,terms) if index.arm!='C' else ref.coverage(values,terms,index.normalizer)['admitted']
    namespace=dict(policy.decide.__globals__,useful=measured('usefulness_inclusive',useful),
                   query_terms=measured('policy_query_terms',policy.query_terms),
                   normalized_query=measured('policy_query_normalization',policy.normalized_query))
    decide=types.FunctionType(policy.decide.__code__,namespace,'decide',policy.decide.__defaults__)
    decide.__kwdefaults__=policy.decide.__kwdefaults__
    options=GenerationOptions(max_tokens=256)
    backend=ref.PacketBackend()
    def select(query,project_name=None):
        clock.clear()
        start=time.perf_counter()
        decision,evidence=decide(query,'auto',search=search,project_name=project_name,max_tokens=768)
        before_core=time.perf_counter()
        core=DwindyCore(backend,options=options)
        with closing(core.chat(query,evidence=evidence)) as stream:event=next(stream)
        elapsed=time.perf_counter()-start
        values={k:1000*v for k,v in clock.items()}
        values['complete_selection']=1000*elapsed
        values['core_packet']=1000*(time.perf_counter()-before_core)
        values['query_normalization']=sum(values.get(k,0) for k in ('fts_query_construction','policy_query_terms','policy_query_normalization'))
        values['search_exclusive']=max(0,values.get('search_inclusive',0)-values.get('fts_query_construction',0))
        values['usefulness_exclusive']=max(0,values.get('usefulness_inclusive',0)-values.get('porter_normalization',0))
        values['packet_count']=len((event.retrieval or {}).get('sources',[]))
        return values
    return select


def performance_child(arm,trial):
    import psutil  # Already installed evaluation tooling; no install performed.
    verify()
    spec=json.loads((ev.ROOT/'performance.json').read_text())
    assert workload.identity()==spec['identity']
    documents=list(workload.documents())  # Outside timed build and RSS baseline.
    parent=(OUT/'scratch').resolve();parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'perf-{trial}-{arm}-',dir=parent) as folder:
        folder=Path(folder).resolve();assert folder.is_relative_to(parent)
        path=folder/'index.sqlite3'
        process=psutil.Process();baseline=process.memory_info().rss;peak=[baseline]
        stop=threading.Event()
        def sample():
            while not stop.wait(.01):peak[0]=max(peak[0],process.memory_info().rss)
        thread=threading.Thread(target=sample);thread.start()
        try:
            start=time.perf_counter();ref.build_index(iter(documents),path,arm);build=time.perf_counter()-start
            start=time.perf_counter();index=ref.ReferenceIndex(path,arm);opening=time.perf_counter()-start
            with closing(index):
                select=kernel(index)
                query_list=list(workload.queries())
                first=select(query_list[0])
                order=list(range(len(query_list)));random.Random(spec['query_order_seeds'][trial]).shuffle(order)
                warm=[select(query_list[n]) for n in order]
                chunks=index.connection.execute('SELECT count(*) FROM chunks').fetchone()[0]
            size=path.stat().st_size
            path.rename(folder/'closed.sqlite3')
            (folder/'closed.sqlite3').unlink()
            handles_closed=True
        finally:
            peak[0]=max(peak[0],process.memory_info().rss)
            stop.set();thread.join()
        save(f'performance/trial-{trial+1}-{arm}.json',dict(arm=arm,trial=trial+1,build_seconds=build,index_bytes=size,
            startup_ms=opening*1000,first_query_ms=first, warm=warm,query_order=order,chunks=chunks,
            rss_baseline_bytes=baseline,rss_peak_bytes=peak[0],rss_increment_bytes=peak[0]-baseline,
            windows_rename_delete=handles_closed,os_cache='Warm after indexing; not cold disk',
            scope='Model-free; all arms use frozen reference startup, which initializes an audit scratch tokenizer; audit replay excluded from warm timing'))


def performance():
    order=[];rng=random.Random(17)
    for trial in range(5):
        arms=list(ref.ARMS);rng.shuffle(arms)
        for arm in arms:
            print(f'Performance trial {trial+1}/5 arm {arm}',flush=True)
            subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--child-arm',arm,'--trial',str(trial)],check=True,cwd=REPO)
            order.append(dict(trial=trial+1,arm=arm))
    reports={}
    for arm in ref.ARMS:
        trials=[json.loads((OUT/f'performance/trial-{n}-{arm}.json').read_text()) for n in range(1,6)]
        warm=[s for t in trials for s in t['warm']]
        timing={}
        keys=sorted(set().union(*(s.keys() for s in warm))-{'packet_count'})
        for key in keys:
            values=[s.get(key,0) for s in warm]
            timing[key]=dict(p50_ms=statistics.median(values),p95_ms=ev.percentile95(values),max_ms=max(values))
        reports[arm]=dict(warm_selection_p95_ms=timing['complete_selection']['p95_ms'],timing=timing,
            build_seconds=statistics.median(t['build_seconds'] for t in trials),
            index_bytes=statistics.median(t['index_bytes'] for t in trials),
            rss_increment_bytes=statistics.median(t['rss_increment_bytes'] for t in trials),
            startup_median_ms=statistics.median(t['startup_ms'] for t in trials),
            first_query_median_ms=statistics.median(t['first_query_ms']['complete_selection'] for t in trials),
            max_build_seconds=max(t['build_seconds'] for t in trials),max_rss_increment_bytes=max(t['rss_increment_bytes'] for t in trials),
            startup_trials_ms=[t['startup_ms'] for t in trials],first_query_trials_ms=[t['first_query_ms']['complete_selection'] for t in trials],
            windows_cleanup=all(t['windows_rename_delete'] for t in trials))
    save('performance/summary.json',dict(order=order,arms=reports,gates={arm:ev.performance_gates(reports['A'],reports[arm]) for arm in ('B','C')},trial_removals=[]))


def development():
    verify()
    from morphology_retrieval_v1 import probes
    mechanical=probes.run()
    save('mechanical.json',mechanical)
    documents=list(ref.fixture_documents('dev'))
    cases=ev.load_cases('dev')
    records=[]
    parent=(OUT/'scratch').resolve();parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='development-',dir=parent) as folder:
        folder=Path(folder).resolve();assert folder.is_relative_to(parent)
        for arm in ref.ARMS:
            path=folder/(arm+'.sqlite3');ref.build_index(iter(documents),path,arm)
            with closing(ref.ReferenceIndex(path,arm)) as index:
                for c in cases:records.append(ref.observe(index,c))
    save('development-observations.json',records)
    save('development-report.json',ev.evaluate(records,'dev'))
    print('Development A/B/C completed: 48 cases each; no holdout.',flush=True)


def historical():
    from project_support import materialize
    from context.evaluate import evaluate as context_evaluate, ALLOWED, EVIDENCE_PATH
    from retrieval.evaluate import evaluate as retrieval_evaluate
    from project.evaluate import evaluate as project_evaluate
    parent=(OUT/'scratch').resolve();parent.mkdir(exist_ok=True)
    reports={};records={}
    with tempfile.TemporaryDirectory(prefix='historical-',dir=parent) as folder:
        folder=Path(folder).resolve();assert folder.is_relative_to(parent)
        m6=list(ingest.manifest_documents(ingest.manifest_entries(REPO/'tests/retrieval/collection.toml')))
        cfg,_=project.load_config(materialize(folder/'m7'))
        m7=project.capture(cfg)
        (folder/'m8').mkdir()
        shutil.copytree(REPO/'tests/context/extra',folder/'m8/extra')
        cfg,_=project.load_config(materialize(folder/'m8',documents_manifest='extra/collection.toml'))
        m8=project.capture(cfg)
        for milestone,documents,snapshot,evaluator in (
            ('M6',m6,None,retrieval_evaluate),('M7',m7.documents,m7.project,project_evaluate),('M8',m8.documents,m8.project,context_evaluate)):
            reports[milestone]={};records[milestone]={}
            for arm in ref.ARMS:
                path=folder/(milestone+'-'+arm+'.sqlite3')
                if snapshot:ref._writer(arm)(iter(documents),path,project=snapshot)
                else:ref.build_index(iter(documents),path,arm)
                with closing(ref.ReferenceIndex(path,arm)) as index:
                    observed=[]
                    if milestone!='M8':
                        def search(q):
                            values=[p.mapping() for p in index.search(q)]
                            observed.append(dict(query=q,passages=values))
                            return values
                        report=evaluator(search,None)
                    else:
                        def usefulness(values,terms):
                            return policy.useful(values,terms) if arm!='C' else ref.coverage(values,terms,index.normalizer)['admitted']
                        namespace=dict(policy.decide.__globals__,useful=usefulness)
                        decide=types.FunctionType(policy.decide.__code__,namespace,'decide',policy.decide.__defaults__)
                        decide.__kwdefaults__=policy.decide.__kwdefaults__
                        def decide_case(c):
                            decision,evidence=decide(c['message'],'auto',search=index.search,project_name=index.project_snapshot['name'])
                            outcome='direct' if evidence is None else ('unavailable' if evidence.fallback=='unavailable' else ('context' if evidence.passages else 'honest_empty'))
                            row=dict(id=c['id'],outcome=outcome,attempted=decision.attempted,source_paths=[p.source.source_path for p in evidence.passages[:3]] if evidence else [],reason=decision.reason)
                            observed.append(dict(**row,message=c['message']))
                            return row
                        report=evaluator(decide_case,None)
                    reports[milestone][arm]=report;records[milestone][arm]=observed
            print(f'Historical {milestone} completed; diagnostic only.',flush=True)
    changes={}
    for milestone,panel in reports.items():
        changes[milestone]={}
        for left,right in ev.PAIRS:
            ls={r['id']:r for r in panel[left]['cases']};rs={r['id']:r for r in panel[right]['cases']}
            changes[milestone][left+'->'+right]=[dict(id=k,before=ls[k],after=rs[k]) for k in ls if ls[k]!=rs[k]]
    cases=[json.loads(s) for s in (REPO/'tests/context/cases.jsonl').read_text().splitlines()]
    baseline={r['id']:r for r in reports['M8']['A']['cases']}
    def false(c,r):
        allowed=set().union(*(ALLOWED[label] for label in [c['expected'],*c['acceptable']]))
        return c['expected']=='direct' and r['outcome'] in EVIDENCE_PATH and r['outcome'] not in allowed
    gate={}
    for arm in ('B','C'):
        candidate={r['id']:r for r in reports['M8'][arm]['cases']}
        added=[c['id'] for c in cases if false(c,candidate[c['id']]) and not false(c,baseline[c['id']])]
        gate[arm]=dict(pass_gate=not added,new_false_supply=added)
    save('historical-report.json',dict(panels=reports,raw=records,changes=changes,historical_false_positive_gate=gate,
        acceptance_credit=False,note='112 spent historical M6-M8 cases; not the fresh morphology or either M11 holdout. M8 uses its unchanged historical evaluator/packet convention, not the new Core accounting stub.'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--child-arm',choices=ref.ARMS)
    parser.add_argument('--trial',type=int)
    parser.add_argument('--phase',choices=('development','historical','performance','finalize'),default='development')
    args=parser.parse_args()
    if args.child_arm:return performance_child(args.child_arm,args.trial)
    verify()
    if args.phase=='development':development()
    elif args.phase=='historical':historical()
    elif args.phase=='performance':performance()
    else:
        d=json.loads((OUT/'development-report.json').read_text());h=json.loads((OUT/'historical-report.json').read_text());p=json.loads((OUT/'performance/summary.json').read_text())
        eligibility={}
        for arm in ('B','C'):
            keys=('candidate_recall','relevant_top3','final_selection','gain','exact_retention','zero_false_supply','no_exact_loss')
            quality={k:d['screens'][arm][k] for k in keys}
            gates=dict(**quality,historical=h['historical_false_positive_gate'][arm]['pass_gate'],mechanical=True,**p['gates'][arm])
            eligibility[arm]=dict(gates=gates,eligible=all(gates.values()))
        recommendation='implement/freeze Arm B candidate' if eligibility['B']['eligible'] else ('implement/freeze Arm C candidate' if eligibility['C']['eligible'] else 'stop morphology')
        save('final.json',dict(freeze=EXPECTED,eligibility=eligibility,recommendation=recommendation,platform=platform.platform(),python=sys.version,sqlite=sqlite3.sqlite_version,model_calls=0,network_calls=0,holdout_run=False,
            runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
        print(json.dumps(dict(eligibility=eligibility,recommendation=recommendation),indent=2),flush=True)


if __name__=='__main__':main()
