"""Pure observation scoring. No retrieval, encoder, network or generation.

Sealed holdout scoring requires a separately approved versioned execution adapter;
this interface cannot silently run or score it. Construction validation checks
authored identities/offsets in both initial splits, not retrieval outcomes.
"""
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).parent
CATEGORIES = dict(english_semantic=12,filipino=12,taglish=12,lexical=8,
                  identifier=8,morphology=8,short_local=4,no_supply=16)
ARMS = ('A','R','S','H')
SEMANTIC = ('english_semantic','filipino','taglish')


def read(name, root=ROOT):
    return json.loads((root/name).read_text(encoding='utf-8'))


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                     separators=(',',':')).encode('utf-8')).hexdigest()


def load_cases(split='dev'):
    if split!='dev':
        raise PermissionError('Holdout is sealed; this evaluator accepts development only')
    return read('cases_dev.json')


def verify_manifest(name='FREEZE.json',root=ROOT):
    manifest = read(name,root)
    names = {p.relative_to(root).as_posix() for p in root.rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.name not in ('FREEZE.json','DRAFT_MANIFEST.json')}
    if names!=set(manifest):
        raise AssertionError('Manifest file set changed')
    for path, expected in manifest.items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest()!=expected:
            raise AssertionError('Manifest bytes changed: '+path)
    return hashlib.sha256((root/name).read_bytes()).hexdigest()


def verify_bindings():
    repo = ROOT.parent.parent
    for name in ('baseline.json','historical.json'):
        for path,expected in read(name)['files'].items():
            if hashlib.sha256((repo/path).read_bytes()).hexdigest()!=expected:
                raise AssertionError('Historical/production bytes changed: '+path)
    return True


def validate_review(root=ROOT):
    rows = read('language_review.json',root)['entries']
    cases = [c for part in ('dev','holdout') for c in read(f'cases_{part}.json',root)
             if c['fluent_review_required']]
    if len(rows)!=49 or {r['id'] for r in rows}!={c['id'] for c in cases}:
        raise ValueError('Require fluent review of 48 language positives and the quoted-text control')
    by_id = {c['id']:c for c in cases}
    for r in rows:
        if r['case_sha256']!=canonical_hash(by_id[r['id']]):
            raise ValueError('Review refers to changed fixture: '+r['id'])
        if r['status']!='approved' or not r['reviewer'] or not r['reviewed_at']:
            raise PermissionError('Fluent human review pending: '+r['id'])
    return True


def validate_fixtures():
    documents = read('documents.json')
    docs = {d['id']:d for d in documents}
    if len(docs)!=288 or len({d['path'] for d in documents})!=288:
        raise AssertionError('Document identities/count changed')
    split = read('split.json')
    queries = []
    all_ids = set()
    for part in ('dev','holdout'):
        cases = read(f'cases_{part}.json')
        if len(cases)!=80 or Counter(c['category'] for c in cases)!=Counter(CATEGORIES):
            raise AssertionError('Wrong split/category composition')
        if split[part]!=[c['id'] for c in cases] or all_ids&set(split[part]):
            raise AssertionError('Split identities changed/overlap')
        all_ids.update(split[part])
        for c in cases:
            queries.append(c['query'])
            required = c['category'] in ('filipino','taglish') or c['id']=='dev_no_supply_10'
            if c.get('fluent_review_required')!=required:
                raise AssertionError('Required language review omitted')
            if c['split']!=part or c['context_expected']!=(c['category']!='no_supply'):
                raise AssertionError('Gold decision inconsistent')
            if bool(c['relevance_gold'])!=c['context_expected'] or bool(c['answer_gold'])!=c['context_expected']:
                raise AssertionError('Missing/incorrect gold spans')
            for key in ('relevance_gold','answer_gold'):
                for g in c[key]:
                    d = docs[g['document_id']]
                    text = (ROOT/d['path']).read_text(encoding='utf-8')
                    if d['split']!=part or g['source_id']!=d['source_id'] or not 0<=g['start']<g['end']<=len(text) or text[g['start']:g['end']]!=g['text']:
                        raise AssertionError('Invalid gold identity/span')
            gold_ids = {g['document_id'] for g in c['relevance_gold']}
            if gold_ids&set(c['distractors']) or any(docs[i]['split']!=part for i in c['distractors']):
                raise AssertionError('Distractor gold/split collision')
    if len(set(queries))!=160:
        raise AssertionError('Duplicate query')
    for d in documents:
        p = Path(d['path'])
        if p.is_absolute() or '..' in p.parts or p.parts[:2]!=('corpus',d['split']):
            raise AssertionError('Invalid corpus path')
        raw = (ROOT/p).read_bytes()
        if b'\r' in raw or b'\0' in raw or hashlib.sha256(raw).hexdigest()!=d['content_hash']:
            raise AssertionError('Corpus byte hash changed')
        raw.decode('utf-8')
    return dict(cases=160,dev=80,holdout=80,positive_per_split=64,negative_per_split=16,
                documents=288,language_review_required=49)


def hit(entry,gold):
    return any(entry['document_id']==g['document_id'] and entry['source_id']==g['source_id']
               and entry['start']<=g['start'] and entry['end']>=g['end']
               and entry['text'][g['start']-entry['start']:g['end']-entry['start']]==g['text'] for g in gold)


def score_case(case,record):
    def rank(values,gold):
        return next((i for i,p in enumerate(values,1) if hit(p,gold)),None)
    candidates,admitted,supplied = (record[k] for k in ('candidates','admitted','supplied'))
    r = rank(candidates,case['relevance_gold'])
    a = rank(candidates[:3],case['answer_gold'])
    return dict(id=case['id'],category=case['category'],positive=case['context_expected'],
                candidate_recall12=r is not None,candidate_recall3=r is not None and r<=3,
                admitted_relevant=rank(admitted,case['relevance_gold']) is not None,
                admitted_answer=rank(admitted,case['answer_gold']) is not None,
                final_relevant=rank(supplied,case['relevance_gold']) is not None,
                answer_hit1=a==1,answer_hit3=a is not None,answer_mrr3=1/a if a else 0,
                final_answer=rank(supplied,case['answer_gold']) is not None,
                irrelevant_supply=not case['context_expected'] and bool(supplied),
                nongold_supplied_entries=sum(not hit(p,case['relevance_gold']) for p in supplied),
                acquisition_state=record['acquisition_state'],supply_state=record['supply_state'])


def validate_records(records,cases,documents=None):
    expected = {(c['id'],arm) for c in cases for arm in ARMS}
    if len(records)!=len(expected) or {(r['id'],r['arm']) for r in records}!=expected:
        raise ValueError('Require exactly one case/arm observation for a single frozen model/threshold profile')
    by_id = {c['id']:c for c in cases}
    docs = documents or {d['id']:d for d in read('documents.json')}
    for r in records:
        if r.get('generation_calls')!=0 or r.get('network_calls')!=0:
            raise ValueError('Zero generation/network calls required')
        if r.get('budget_oracle')!='utf8_quarters_v1':
            raise ValueError('Unapproved accounting oracle')
        if type(r.get('dropped_turns')) is not int or r['dropped_turns']<0:
            raise ValueError('Missing/invalid history trimming observation')
        admission = r.get('admission_trace')
        if not isinstance(admission,dict) or type(admission.get('applied')) is not bool:
            raise ValueError('Explicit admission/bypass trace required')
        if admission['applied'] != (type(admission.get('accepted')) is bool):
            raise ValueError('Bypass is null, not measured rejection')
        if r['admitted'] and admission['applied'] and not admission['accepted']:
            raise ValueError('Rejected admission cannot admit')
        if type(r.get('candidate_probe_only')) is not bool:
            raise ValueError('Must distinguish diagnostics from actual acquisition')
        for field,limit in (('candidates',12),('admitted',12),('supplied',3)):
            values = r[field]
            ids = [p['entry_id'] for p in values]
            if len(values)>limit or len(ids)!=len(set(ids)):
                raise ValueError('Entry bounds/identity violated')
            for p in values:
                d = docs.get(p['document_id'])
                if not d or d['split']!=by_id[r['id']]['split'] or p['source_id']!=d['source_id']:
                    raise ValueError('Unknown/wrong-split source')
                text = (ROOT/d['path']).read_text(encoding='utf-8')
                if type(p['start']) is not int or type(p['end']) is not int or not 0<=p['start']<p['end']<=len(text) or text[p['start']:p['end']]!=p['text']:
                    raise ValueError('Source text/span changed')
                if not p['entry_id'] or not p['entry_id'].startswith(d['id']+':'):
                    raise ValueError('Entry identity must be source-anchored')
        for parent,child in (('candidates','admitted'),('admitted','supplied')):
            ids = {p['entry_id'] for p in r[child]}
            if r[child]!=[p for p in r[parent] if p['entry_id'] in ids]:
                raise ValueError('Identity/text/order must survive each stage')
        state,supply = r['acquisition_state'],r['supply_state']
        if state not in ('found','no_match','unavailable','not_used') or supply not in ('supplied','budget_exhausted','no_match','unavailable','not_used'):
            raise ValueError('Unknown acquisition/supply state')
        if bool(r['supplied'])!=(supply=='supplied'):
            raise ValueError('Supply state disagrees with actual packet')
        if state=='unavailable' and (not r.get('error') or r['supplied']):
            raise ValueError('Operational failure lost')
        if state in ('not_used','unavailable','no_match') and (r['admitted'] or supply!=state):
            raise ValueError('Failed/bypassed acquisition cannot admit')
        if state=='found' and not r['candidates']:
            raise ValueError('Found must contain candidates')
        if state in ('unavailable','no_match') and r['candidates']:
            raise ValueError('Operational failure/empty acquisition cannot contain candidates')
        if state=='found' and not r['admitted'] and supply!='no_match':
            raise ValueError('Rejected candidates cannot masquerade as supply')
        if supply=='budget_exhausted' and not r['admitted']:
            raise ValueError('Budget exhaustion requires admitted entries')
        if state=='found' and r['admitted'] and supply not in ('supplied','budget_exhausted'):
            raise ValueError('Admitted packet state inconsistent')
        if r['candidate_probe_only'] and state!='not_used':
            raise ValueError('Diagnostic candidate search cannot be an acquisition')
        if r['public_source_ids']!=list(dict.fromkeys(p['source_id'] for p in r['supplied'])):
            raise ValueError('Public presentation must reference actual supplied sources only')
        if r.get('public')!={'state':supply,'source_ids':r['public_source_ids']}:
            raise ValueError('Public evaluation projection must exclude similarity and internal audit fields')
        audits = r.get('encoding_audit')
        if not isinstance(audits,list): raise ValueError('Encoder view audit required')
        if r['arm']=='A' and audits: raise ValueError('Lexical baseline cannot encode')
        if r['arm']!='A' and state=='found':
            if {a['entry_id'] for a in audits}!={p['entry_id'] for p in r['candidates']} or len(audits)!=len(r['candidates']):
                raise ValueError('Require one encoded-span audit per selected candidate')
            by_entry = {p['entry_id']:p for p in r['candidates']}
            for a in audits:
                p = by_entry[a['entry_id']]
                if not 0<=a['body_start']<=a['body_end']<=len(p['text']) or not 0<a['retained_tokens']<=a['max_tokens'] or a['input_tokens']<a['retained_tokens']:
                    raise ValueError('Invalid encoded view/token bound')
                if not isinstance(p.get('cosine'),(int,float)) or not math.isfinite(p['cosine']) or not -1<=p['cosine']<=1:
                    raise ValueError('Finite internal cosine audit required')
        if r['candidate_probe_only'] and r['arm']!='A' and audits:
            raise ValueError('Ordinary model-only bypass must not execute an encoder')
        for value in r['latency_ms'].values():
            if not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError('Invalid timing')


def quality_gates(scores,baseline,gates):
    sem = [s for s in scores if s['category'] in SEMANTIC]
    base = {s['id']:s for s in baseline}
    exact = [s for s in scores if s['category'] in ('lexical','identifier')]
    return dict(semantic_candidates=sum(s['candidate_recall12'] for s in sem)>=gates['semantic_candidates'],
                semantic_final=sum(s['final_relevant'] for s in sem)>=gates['semantic_final'],
                semantic_each_language=all(sum(s['final_relevant'] for s in sem if s['category']==k)>=gates['semantic_each_language'] for k in SEMANTIC),
                semantic_answers=sum(s['final_answer'] for s in sem)>=gates['semantic_answers'],
                semantic_net_gain=sum(s['final_relevant']-base[s['id']]['final_relevant'] for s in sem)>=gates['semantic_net_gain'],
                exact_retention=sum(s['final_relevant'] for s in exact)==gates['exact_retention'] and all(not base[s['id']]['final_relevant'] or s['final_relevant'] for s in exact),
                morphology=sum(s['final_relevant'] for s in scores if s['category']=='morphology')>=gates['morphology'],
                short_local=sum(s['final_relevant'] for s in scores if s['category']=='short_local')>=gates['short_local'],
                no_false_supply=sum(s['irrelevant_supply'] for s in scores)==gates['false_supply'])


def evaluate(records,split='dev'):
    cases = load_cases(split)
    validate_records(records,cases)
    scores = {arm:[score_case(c,next(r for r in records if r['id']==c['id'] and r['arm']==arm)) for c in cases] for arm in ARMS}
    metrics = ('candidate_recall12','candidate_recall3','admitted_relevant','admitted_answer','final_relevant','answer_hit1','answer_hit3','answer_mrr3','final_answer','irrelevant_supply','nongold_supplied_entries')
    summary = {arm:{cat:dict(cases=len(rows),**{m:sum(s[m] for s in rows) for m in metrics})
                    for cat in CATEGORIES for rows in [[s for s in scores[arm] if s['category']==cat]]} for arm in ARMS}
    by_key = {(r['id'],r['arm']):r for r in records}
    changes = {}
    fields = ('candidates','admitted','supplied','acquisition_state','supply_state','public_source_ids')
    for left,right in itertools.combinations(ARMS,2):
        changes[f'{left}->{right}'] = [dict(id=c['id'],before=by_key[c['id'],left],after=by_key[c['id'],right]) for c in cases
                                      if any(by_key[c['id'],left][f]!=by_key[c['id'],right][f] for f in fields)]
    truncation = {arm:[dict(case_id=r['id'],**a) for r in records if r['arm']==arm for a in r['encoding_audit']
                      if a['body_start']!=0 or a['body_end']<len(next(p['text'] for p in r['candidates'] if p['entry_id']==a['entry_id'])) or a['input_tokens']>a['retained_tokens']]
                  for arm in ARMS}
    return dict(summary=summary,scores=scores,changes=changes,truncation=truncation,
                quality_screens={arm:quality_gates(scores[arm],scores['A'],read('gates.json')['quality']) for arm in ARMS if arm!='A'},
                eligibility='Incomplete until every mechanical, historical-control and resource gate also passes; no automatic holdout')


def percentile95(values):
    if not values or any(not math.isfinite(x) or x<0 for x in values):
        raise ValueError('Finite nonnegative samples required')
    return sorted(values)[math.ceil(.95*len(values))-1]


def resource_gates(observation,baseline):
    gates = read('gates.json')['resources']
    if set(observation)!=set(gates):
        raise ValueError('Complete resource measurements required')
    result = {}
    for key,limit in gates.items():
        value = observation[key]
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
            raise ValueError('Invalid resource measurement')
        result[key] = value<=limit
    result['selection_delta_ms'] = observation['selection_p95_ms']<=baseline['selection_p95_ms']+125
    return result


def summarize_performance(trials,footprint):
    """Validate complete future raw measurements, then compute frozen statistics.

    No measurement is executed here. Missing trials, hidden outliers, generation,
    network access and altered workload identities cannot produce a resource pass.
    """
    protocol = read('performance.json')
    if len(trials)!=5 or {t['trial'] for t in trials}!={0,1,2,3,4}:
        raise ValueError('Require all five isolated trials')
    values = []
    for t in trials:
        if t['identity']!=protocol['identity'] or t['generation_calls']!=0 or t['network_calls']!=0:
            raise ValueError('Changed workload or unauthorized calls')
        if len(t['warm_samples'])!=200 or {s['query_index'] for s in t['warm_samples']}!=set(range(200)):
            raise ValueError('Missing/duplicate warm samples; no outlier removal')
        for key in ('startup_ms','first_query_ms','build_ms','steady_incremental_rss_bytes','peak_incremental_rss_bytes','additional_index_bytes'):
            if not isinstance(t[key],(int,float)) or not math.isfinite(t[key]) or t[key]<0:
                raise ValueError('Invalid trial resource statistic')
        if t['peak_incremental_rss_bytes']<t['steady_incremental_rss_bytes']:
            raise ValueError('Peak cannot be below steady RSS')
        for s in t['warm_samples']:
            for key in ('encoding_ms','selection_ms'):
                if not isinstance(s[key],(int,float)) or not math.isfinite(s[key]) or s[key]<0:
                    raise ValueError('Invalid warm timing')
            if s['encoding_ms']>s['selection_ms']:
                raise ValueError('Encoding must be included in complete selection')
        values.extend(t['warm_samples'])
    result = dict(footprint)
    if set(result)!={'dependency_compressed_bytes','dependency_installed_bytes','model_artifact_bytes'}:
        raise ValueError('Complete dependency/model footprint required')
    for key in ('startup_ms','first_query_ms','build_ms','steady_incremental_rss_bytes'):
        result[key]=statistics.median(t[key] for t in trials)
    for key in ('peak_incremental_rss_bytes','additional_index_bytes'):
        result[key]=max(t[key] for t in trials)
    result['encoding_p95_ms']=percentile95([s['encoding_ms'] for s in values])
    result['selection_p95_ms']=percentile95([s['selection_ms'] for s in values])
    return result
