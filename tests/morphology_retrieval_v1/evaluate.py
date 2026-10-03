"""Frozen observation evaluator; does not retrieve, load a model or use the network.

Holdout scoring is fail-closed pending a separate reviewed candidate freeze and
explicit authorization. Construction tests use development or synthetic records.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).parent
ARMS = ('A','B','C')
PAIRS = (('A','B'),('A','C'),('B','C'))
CATEGORIES = ('inflection','derivation','exact_identifier','collision','accidental_overlap','ordinary_control','synonym','filipino_taglish')
GATES = dict(morph_candidate_hits=11,morph_top3_hits=10,morph_final_hits=10,morph_gain=3,
             exact_hits=6,false_supply=0,warm_p95_ms=25,latency_ratio=1.25,latency_slack_ms=2,
             build_ratio=1.20,size_ratio=1.20,extra_rss_bytes=8*1024*1024)


def load_cases(split):
    if split not in ('dev','holdout'):
        raise ValueError('Explicit split required; no automatic combined split')
    return [json.loads(line) for line in (ROOT/'cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip() and json.loads(line)['split']==split]


def verify_freeze(root=ROOT):
    manifest = json.loads((root/'FREEZE.json').read_text(encoding='utf-8'))
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='FREEZE.json'}
    if actual!=set(manifest):raise AssertionError('Frozen file set changed')
    for name,digest in manifest.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise AssertionError('Frozen bytes changed: '+name)
    return hashlib.sha256((root/'FREEZE.json').read_bytes()).hexdigest()


def validate_fixtures():
    documents = json.loads((ROOT/'documents.json').read_text(encoding='utf-8'))
    docs = {d['id']:d for d in documents}
    cases = load_cases('dev')+load_cases('holdout')
    if len(docs)!=96 or len(cases)!=96 or len({c['id'] for c in cases})!=96:
        raise AssertionError('Wrong composition/duplicate identities')
    split = json.loads((ROOT/'split.json').read_text())
    for part in ('dev','holdout'):
        rows = [c for c in cases if c['split']==part]
        if len(rows)!=48 or Counter(c['category'] for c in rows)!=Counter({k:6 for k in CATEGORIES}):
            raise AssertionError('Wrong category split')
        if split[part]!=[c['id'] for c in rows]:raise AssertionError('Split changed')
    if set(split['dev'])&set(split['holdout']):raise AssertionError('Split overlap')
    for d in documents:
        path = Path(d['path'])
        if path.is_absolute() or '..' in path.parts or path.parts[0]!='corpus' or path.suffix not in ('.txt','.md'):
            raise AssertionError('Invalid corpus path')
        raw = (ROOT/path).read_bytes()
        if b'\r' in raw or b'\0' in raw or not raw.decode('utf-8').strip():raise AssertionError('Invalid UTF-8/LF text')
    for c in cases:
        if c['diagnostic_only']!=(c['category'] in ('synonym','filipino_taglish')):
            raise AssertionError('Diagnostic category contributes acceptance credit')
        if type(c['context_expected']) is not bool:raise AssertionError('Missing gold decision')
        if bool(c['relevance_gold'])!=c['context_expected'] or bool(c['answer_gold'])!=c['context_expected']:
            raise AssertionError('Gold presence disagrees with context label')
        for key in ('relevance_gold','answer_gold'):
            for g in c[key]:
                d = docs[g['document_id']]
                text = (ROOT/d['path']).read_text(encoding='utf-8')
                if d['split']!=c['split'] or not 0<=g['start']<g['end']<=len(text) or text[g['start']:g['end']]!=g['text']:
                    raise AssertionError('Gold span/split invalid')
        if c['category']=='collision' and (not c['collision_pair'] or len(c['collision_pair'])!=2):
            raise AssertionError('Missing collision annotation')
    return dict(cases=96,documents=96,dev=48,holdout=48,acceptance_per_split=36,diagnostic_per_split=12)


def _hit(passage,gold):
    return any(passage['document_id']==g['document_id'] and passage['start']<=g['start'] and passage['end']>=g['end']
               and passage['text'][g['start']-passage['start']:g['end']-passage['start']]==g['text'] for g in gold)


def score_case(case,record):
    candidates, supplied = record['candidates'],record['supplied']
    def rank(gold,values):
        return next((i for i,p in enumerate(values,1) if _hit(p,gold)),None)
    relevant = rank(case['relevance_gold'],candidates)
    answer = rank(case['answer_gold'],candidates[:3])
    final_relevant = rank(case['relevance_gold'],supplied)
    final_answer = rank(case['answer_gold'],supplied)
    return dict(id=case['id'],category=case['category'],diagnostic_only=case['diagnostic_only'],
                positive=case['context_expected'],candidate_recall12=relevant is not None,
                relevant_top3=relevant is not None and relevant<=3,
                usefulness_applied=record['usefulness_applied'],useful_admitted=record['useful_admitted'],
                selected=bool(supplied),final_relevant=final_relevant is not None,
                final_answer=final_answer is not None,answer_hit1=answer==1,answer_hit3=answer is not None,
                answer_mrr3=1/answer if answer else 0,irrelevant_supply=not case['context_expected'] and bool(supplied),
                decision=record['decision'],retrieval_status=record['retrieval_status'])


def validate_records(records,cases):
    expected = {(c['id'],arm) for c in cases for arm in ARMS}
    if len(records)!=len(expected) or {(r['id'],r['arm']) for r in records}!=expected:
        raise ValueError('Require exactly one record per case/arm')
    by_id = {c['id']:c for c in cases}
    documents = {d['id']:d for d in json.loads((ROOT/'documents.json').read_text(encoding='utf-8'))}
    for r in records:
        if any(type(r[k]) is not bool for k in ('candidate_probe_only','policy_attempted','usefulness_applied')):
            raise ValueError('Boolean field required')
        if r['usefulness_applied'] != (type(r['useful_admitted']) is bool):
            raise ValueError('Admission must be null when bypassed; false is a measured rejection')
        if r['usefulness_applied'] and not r['useful_admitted'] and r['supplied']:
            raise ValueError('Rejected usefulness cannot supply passages')
        if len(r['candidates'])>12 or len(r['supplied'])>3:raise ValueError('Passage caps violated')
        identifiers = [p['chunk_id'] for p in r['candidates']]
        if len(set(identifiers))!=len(identifiers):raise ValueError('Duplicate candidate identifier')
        supplied_ids = [p['chunk_id'] for p in r['supplied']]
        if len(set(supplied_ids))!=len(supplied_ids):raise ValueError('Duplicate supplied slot')
        if r['supplied']!=[p for p in r['candidates'] if p['chunk_id'] in supplied_ids]:raise ValueError('Supplied text/order not preserved')
        for p in r['candidates']:
            d = documents.get(p['document_id'])
            if not d or d['split']!=by_id[r['id']]['split']:raise ValueError('Unknown/wrong-split document')
            text = (ROOT/d['path']).read_text(encoding='utf-8')
            if type(p['start']) is not int or type(p['end']) is not int or not 0<=p['start']<p['end']<=len(text) or text[p['start']:p['end']]!=p['text']:
                raise ValueError('Invalid observed source span')
        for k in ('search','selection'):
            v = r['latency_ms'][k]
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('Invalid latency')
        if r['budget_oracle']!='utf8_quarters_v1':raise ValueError('Unknown budget oracle')
        for audit in ('lexical_audit','porter_audit'):
            if type(r[audit]['admitted']) is not bool or len(r[audit]['passages'])>3:raise ValueError('Invalid audit')
            for p in r[audit]['passages']:
                if p['denominator']!=len(r['query_terms']) or p['coverage']!=(len(p['matched_original_terms'])/p['denominator'] if p['denominator'] else 0):
                    raise ValueError('Coverage denominator/count changed')
                if 'original_tokens' not in p or 'resulting_stems' not in p or 'query_token_stems' not in p:
                    raise ValueError('Missing collision/token trace')
        case=by_id[r['id']]
        if case['collision_pair']:
            annotated=r.get('annotated_collision')
            if not annotated or [a['original'] for a in annotated]!=case['collision_pair'] or any(not isinstance(a['stems'],list) for a in annotated):
                raise ValueError('Missing annotated collision token/stem trace')


def _summary(rows):
    positives = [r for r in rows if r['positive']]
    count = len(positives)
    return dict(cases=len(rows),positive_cases=count,
                candidate_recall12=sum(r['candidate_recall12'] for r in positives)/count if count else None,
                relevant_recall3=sum(r['relevant_top3'] for r in positives)/count if count else None,
                final_selection_recall=sum(r['final_relevant'] for r in positives)/count if count else None,
                useful_applied=sum(r['usefulness_applied'] for r in rows),
                useful_admitted=sum(r['useful_admitted'] is True for r in rows),
                answer_hit1=sum(r['answer_hit1'] for r in positives)/count if count else None,
                answer_hit3=sum(r['answer_hit3'] for r in positives)/count if count else None,
                answer_mrr3=sum(r['answer_mrr3'] for r in positives)/count if count else None,
                final_answer_recall=sum(r['final_answer'] for r in positives)/count if count else None,
                irrelevant_supply=sum(r['irrelevant_supply'] for r in rows))


def evaluate(records,split='dev'):
    if split!='dev':raise PermissionError('Holdout scoring is sealed; separately approved candidate freeze required')
    verify_freeze()
    cases = load_cases(split)
    validate_records(records,cases)
    by_key = {(r['id'],r['arm']):r for r in records}
    scored = {arm:[score_case(c,by_key[c['id'],arm]) for c in cases] for arm in ARMS}
    summaries = {arm:dict(overall=_summary(rows),categories={cat:_summary([r for r in rows if r['category']==cat]) for cat in CATEGORIES}) for arm,rows in scored.items()}
    changes, ranking_changes = {}, {}
    for left,right in PAIRS:
        changed = []
        ranked = []
        for c in cases:
            a,b = by_key[c['id'],left],by_key[c['id'],right]
            fields = ('policy_attempted','usefulness_applied','useful_admitted','decision','retrieval_status')
            def identities(values):return [(p['document_id'],p['chunk_id'],p['start'],p['end'],p['text']) for p in values]
            if identities(a['candidates'])!=identities(b['candidates']):
                ranked.append(dict(id=c['id'],before=a['candidates'],after=b['candidates']))
            if any(a[k]!=b[k] for k in fields) or identities(a['supplied'])!=identities(b['supplied']):
                changed.append(dict(id=c['id'],category=c['category'],diagnostic_only=c['diagnostic_only'],
                                    before=a,after=b))
        changes[left+'->'+right] = changed
        ranking_changes[left+'->'+right] = ranked
    screens = {}
    baseline = {r['id']:r for r in scored['A']}
    for arm in ('B','C'):
        morph = [r for r in scored[arm] if r['category'] in ('inflection','derivation')]
        exact = [r for r in scored[arm] if r['category']=='exact_identifier']
        controls = [r for r in scored[arm] if r['category'] in ('collision','accidental_overlap','ordinary_control')]
        gained = [r['id'] for r in morph if r['final_relevant'] and not baseline[r['id']]['final_relevant']]
        lost = [r['id'] for r in morph if not r['final_relevant'] and baseline[r['id']]['final_relevant']]
        screens[arm] = dict(candidate_recall=sum(r['candidate_recall12'] for r in morph)>=11,
                           relevant_top3=sum(r['relevant_top3'] for r in morph)>=10,
                           final_selection=sum(r['final_relevant'] for r in morph)>=10,
                           gain=len(gained)-len(lost)>=3,
                           exact_retention=sum(r['final_relevant'] for r in exact)==6,
                           zero_false_supply=sum(r['irrelevant_supply'] for r in controls)==0,
                           no_exact_loss=all(not baseline[r['id']]['final_relevant'] or r['final_relevant'] for r in exact),
                           gained=gained,lost=lost,
                           mechanical_and_historical_required=True,performance_required=True)
    return dict(split=split,summary=summaries,screens=screens,changes=changes,ranking_changes=ranking_changes,
                every_case=scored,acceptance='Not complete without all mechanical/historical/performance checks; holdout never automatic')


def percentile95(values):
    return sorted(values)[math.ceil(.95*len(values))-1]


def performance_gates(baseline,candidate):
    if any(type(r[k]) not in (float,int) or not math.isfinite(r[k]) or r[k]<0
           for r in (baseline,candidate) for k in ('warm_selection_p95_ms','build_seconds','index_bytes','rss_increment_bytes')):
        raise ValueError('Invalid performance observation')
    return dict(warm_absolute=candidate['warm_selection_p95_ms']<=25,
                warm_relative=candidate['warm_selection_p95_ms']<=1.25*baseline['warm_selection_p95_ms']+2,
                build=candidate['build_seconds']<=1.2*baseline['build_seconds'],
                size=candidate['index_bytes']<=1.2*baseline['index_bytes'],
                rss=candidate['rss_increment_bytes']-baseline['rss_increment_bytes']<=8*1024*1024)
