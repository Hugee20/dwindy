"""Evaluation-only A/B/C adapters. No production module/global is modified.

This module is not an application import or automatic benchmark runner. Only
small synthetic mechanics are exercised before fixture review. No model/network.
"""
from contextlib import closing
import hashlib
import inspect
import json
import math
from pathlib import Path
import sqlite3
import sys
import time
import types

from dwindy import context_policy as policy, ingest, retrieval
from dwindy.backend import GenerationOptions, Message
from dwindy.core import DwindyCore

ROOT = Path(__file__).parent
ARMS = ('A', 'B', 'C')
TOKENIZERS = {'A':'unicode61', 'B':'porter unicode61', 'C':'porter unicode61'}
MAX_SCRATCH_BYTES = 32768


class PorterTokens:
    """Bounded reusable SQLite-only tokenizer, separate from the read-only index."""
    def __init__(self):
        self.db = sqlite3.connect(':memory:', isolation_level=None)
        self.db.executescript("CREATE VIRTUAL TABLE tokens USING fts5(body,tokenize='porter unicode61');"
                              "CREATE VIRTUAL TABLE vocabulary USING fts5vocab(tokens,'instance');")

    def normalize(self, texts):
        texts = list(texts)
        if len(texts)>128 or any(not isinstance(s,str) for s in texts):
            raise ValueError('Invalid normalization batch')
        if sum(len(t.encode('utf-8')) for t in texts)>MAX_SCRATCH_BYTES:
            raise ValueError('Normalization batch exceeds bound')
        result = [[] for _ in texts]
        try:
            self.db.execute('DELETE FROM tokens')
            self.db.executemany('INSERT INTO tokens(rowid,body) VALUES (?,?)', enumerate(texts,1))
            for term, doc in self.db.execute('SELECT term,doc FROM vocabulary ORDER BY doc,offset'):
                result[doc-1].append(term)
            return result
        finally:
            self.db.execute('DELETE FROM tokens')

    def close(self):
        self.db.close()


def coverage(passages, terms, normalizer=None):
    """Keep the original distinct-query-term denominator and 50% threshold.

Only body/heading/path participate, as in M8. Generated summaries are excluded.
One original term counts once, even if its stem occurs many times. Different
original terms collapsing to one stem remain separate terms; report this effect.
"""
    terms = list(terms)
    stem_rows = normalizer.normalize(terms) if normalizer else [[t] for t in terms]
    rows = []
    for p in passages[:policy.TOP_PASSAGES]:
        original = list(dict.fromkeys(retrieval.words(p.text)+retrieval.words(p.source.heading)+retrieval.words(p.source.source_path)))
        stems = normalizer.normalize([' '.join(original)])[0] if normalizer else original
        present = set(stems)
        matched = [term for term, values in zip(terms,stem_rows) if values and set(values)<=present]
        eligible = p.source.source_type not in policy.GENERATED
        fraction = len(matched)/len(terms) if terms else 0.0
        rows.append(dict(chunk_id=p.source.chunk_id, document_id=p.source.document_id,
                         original_tokens=original, resulting_stems=list(dict.fromkeys(stems)),
                         query_token_stems=[dict(original=t,stems=s) for t,s in zip(terms,stem_rows)],
                         matched_original_terms=matched, denominator=len(terms),
                         coverage=fraction, eligible=eligible,
                         admitted=eligible and bool(terms) and fraction>=policy.MIN_COVERAGE))
    return dict(admitted=any(r['admitted'] for r in rows), passages=rows)


def _writer(arm):
    """Clone trusted, hash-pinned existing writer code into an isolated namespace.

Only the FTS declaration differs. No patching of ingest.SCHEMA, production
validation or existing databases. New evaluation indices only.
"""
    if arm not in ARMS:
        raise ValueError('Unknown arm')
    name = 'dwindy._morphology_reference_ingest'
    module = types.ModuleType(name)
    module.__package__ = 'dwindy'
    source = Path(ingest.__file__).read_text(encoding='utf-8')
    sys.modules[name] = module
    try:
        exec(compile(source, ingest.__file__, 'exec'), module.__dict__)
    finally:
        del sys.modules[name]
    module.SCHEMA = retrieval.SCHEMA.replace("tokenize='unicode61'", f"tokenize='{TOKENIZERS[arm]}'")
    return module.write_documents


def build_index(documents, path, arm):
    path = Path(path)
    if path.exists():
        raise ValueError('Fresh evaluation index required; never migrate/reuse a user index')
    return _writer(arm)(documents,path,project=dict(project_id='morphology-fixture',name='Fixture',snapshot_id='frozen',policy_version=1,indexed_at='2026-10-03T00:00:00+00:00'))


def fixture_documents(split):
    if split not in ('dev','holdout'):
        raise ValueError('Explicit split required')
    rows = json.loads((ROOT/'documents.json').read_text(encoding='utf-8'))
    for d in rows:
        if d['split'] != split:
            continue
        data = (ROOT/d['path']).read_bytes()
        yield ingest.Document(d['id'],d['path'],d['name'],Path(d['path']).suffix,
                              ingest.normalize(data),hashlib.sha256(data).hexdigest(),d['source_type'])


class ReferenceIndex(retrieval.RetrievalIndex):
    """Production search algorithm with evaluation-specific schema validation."""
    def __init__(self,path,arm):
        if arm not in ARMS:raise ValueError('Unknown arm')
        self.connection = None
        self.project_snapshot = None
        self.normalizer = None
        self.arm = arm
        try:
            self.connection = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=1,isolation_level=None)
            expected = sqlite3.connect(':memory:')
            try:
                expected.executescript(retrieval.SCHEMA.replace("tokenize='unicode61'",f"tokenize='{TOKENIZERS[arm]}'")+retrieval.PROJECT_SCHEMA)
                sql = 'SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name'
                if self.connection.execute(sql).fetchall()!=expected.execute(sql).fetchall():
                    raise ValueError('Wrong reference schema/tokenizer')
            finally:expected.close()
            if self.connection.execute('PRAGMA application_id').fetchone()[0]!=retrieval.APPLICATION_ID or self.connection.execute('PRAGMA user_version').fetchone()[0]!=2:
                raise ValueError('Wrong reference identity/version')
            if self.connection.execute('PRAGMA quick_check').fetchall()!=[('ok',)] or self.connection.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Invalid index')
            self.connection.execute('PRAGMA query_only=ON')
            self.connection.execute('PRAGMA cache_size=-2048')
            self.connection.row_factory = sqlite3.Row
            self.project_snapshot = dict(self.connection.execute('SELECT project_id,name,snapshot_id,indexed_at FROM project_snapshot').fetchone())
            self.project_snapshot['freshness'] = 'not_checked'
            self.normalizer = PorterTokens()
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.normalizer is not None:
            self.normalizer.close()
            self.normalizer = None
        super().close()


class PacketBackend:
    """Frozen model-free budget oracle; NOT a Qwen tokenizer or latency claim.

Core prepares/announces the actual packet, then its stream is closed before
generation. UTF-8 bytes/4 + fixed role overhead is identical in every arm.
"""
    def count_tokens(self,messages):
        return 4+sum(8+math.ceil(len(m.content.encode('utf-8'))/4) for m in messages)
    def context_size(self):return 8192
    def generate(self,*args,**kwargs):raise AssertionError('No generation permitted')
    def close(self):pass


def observe(index,case):
    """Observe one authorized case; never called over a split during construction.

Timed selection excludes post-hoc audit/token tracing and fallback candidate
probes for bypassed requests. Search timing inside decide is recorded separately.
"""
    candidates, queries, trace = [], [], []
    search_seconds = []
    def search(query,limit):
        start = time.perf_counter()
        values = index.search(query,limit)
        search_seconds.append(time.perf_counter()-start)
        candidates.extend(values)
        queries.append(query)
        return values
    def useful(values,terms):
        if index.arm!='C':
            answer = policy.useful(values,terms)
            trace.append(dict(admitted=answer))
            return answer
        audit = coverage(values,terms,index.normalizer)
        trace.append(audit)
        return audit['admitted']
    namespace = dict(policy.decide.__globals__,useful=useful)
    decide = types.FunctionType(policy.decide.__code__,namespace,policy.decide.__name__,policy.decide.__defaults__)
    decide.__kwdefaults__ = policy.decide.__kwdefaults__
    start = time.perf_counter()
    decision,evidence = decide(case['query'],'auto',search=search,max_tokens=768,project_name=case.get('project_name'))
    core = DwindyCore(PacketBackend(),options=GenerationOptions(max_tokens=256))
    history = tuple(Message(**m) for m in case.get('history',[]))
    core.restore(history)
    with closing(core.chat(case['query'],evidence=evidence)) as stream:
        event = next(stream)
    elapsed = time.perf_counter()-start
    assert core.snapshot()==history
    shape = policy.classify(case['query'],case.get('project_name'))
    effective = policy.normalized_query(case['query'],case.get('project_name'))[0] if shape=='directed' else case['query']
    terms = retrieval.query_terms(effective)
    # Probe availability even if policy deliberately bypasses retrieval. This is
    # explicitly NOT an attempted production search and not in timed selection.
    probe_only = not queries
    if probe_only:candidates = list(index.search(effective,12))
    original = coverage(candidates,terms)
    porter = coverage(candidates,terms,index.normalizer)
    admission = trace[0]['admitted'] if trace else None
    if trace and index.arm!='C' and admission!=original['admitted']:
        raise AssertionError('Lexical audit differs from production usefulness')
    supplied_ids = {s['chunk_id'] for s in (event.retrieval or {}).get('sources',[])}
    supplied = [p.mapping() for p in candidates if p.source.chunk_id in supplied_ids]
    pair = case.get('collision_pair')
    collision = [dict(original=t,stems=s) for t,s in zip(pair,index.normalizer.normalize(pair))] if pair else []
    return dict(id=case['id'],arm=index.arm,effective_query=effective,query_terms=terms,
                candidates=[p.mapping() for p in candidates],candidate_probe_only=probe_only,
                policy_attempted=decision.attempted,usefulness_applied=bool(trace),useful_admitted=admission,
                lexical_audit=original,porter_audit=porter,
                annotated_collision=collision,
                decision=decision.reason,retrieval_status=(event.retrieval or {}).get('status'),
                supplied=supplied,latency_ms=dict(search=1000*sum(search_seconds),selection=1000*elapsed),
                budget_oracle='utf8_quarters_v1',dropped_turns=event.dropped_turns)


def verify_runtime_sources():
    pinned = json.loads((ROOT/'baseline.json').read_text())
    repo = ROOT.parent.parent
    for name,digest in pinned['files'].items():
        if hashlib.sha256((repo/name).read_bytes()).hexdigest()!=digest:
            raise AssertionError('Baseline changed: '+name)
