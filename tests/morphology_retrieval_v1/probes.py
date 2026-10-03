"""24 deterministic mechanical probes using only separate miniature documents.

Never retrieve/score any development or holdout relevance fixture. These probes
establish adapter semantics, not candidate quality or adoption.
"""
from contextlib import closing
import hashlib
from pathlib import Path
import tempfile

from dwindy import context_policy, ingest, retrieval
from dwindy.evidence import Passage, Source
from .reference import PorterTokens, ReferenceIndex, build_index, coverage, observe

IDS = ('native_porter','empty','unicode','scratch_bounds','scratch_cleanup',
       'query_stopwords','query_limit','query_escaping','query_bytes',
       'original_text','denominator','repeated_tokens','generated_exclusion',
       'top_three_coverage','field_union','empty_query','threshold',
       'baseline_parity','bc_candidate_parity','double_bottleneck',
       'readonly','wrong_schema','duplicate_suppression','packet_lifecycle')


def passage(text, *, heading='', path='note.txt', source_type='local_text', key='x'):
    return Passage(Source(key,key,'Note',path,hashlib.sha256(text.encode()).hexdigest(),1,1,0,len(text),heading,source_type),text)


def doc(key,text):
    return ingest.Document(key,key+'.txt','Note '+key,'.txt',text,hashlib.sha256(text.encode()).hexdigest())


def run_one(name):
    if name not in IDS:raise ValueError('Unknown probe')
    with closing(PorterTokens()) as tokens:
        if name=='native_porter':
            values=tokens.normalize(['inspect','inspection','inspected'])
            assert values[0]==values[1]==values[2]
        elif name=='empty':assert tokens.normalize(['','---'])==[[],[]]
        elif name=='unicode':assert tokens.normalize(['CAFÉ','cafe'])==[['cafe'],['cafe']]
        elif name=='scratch_bounds':
            for data in (['x']*129,['x'*32769],[7]):
                try:tokens.normalize(data)
                except ValueError:pass
                else:raise AssertionError('Expected bound/type rejection')
        elif name=='scratch_cleanup':
            tokens.normalize(['private records'])
            assert tokens.db.execute('SELECT count(*) FROM tokens').fetchone()[0]==0
        elif name=='query_stopwords':assert retrieval.query_terms('What are the inspected pumps?')==['inspected','pumps']
        elif name=='query_limit':assert len(retrieval.query_terms(' '.join('word'+str(n) for n in range(90))))==32
        elif name=='query_escaping':
            assert retrieval.match_query('" OR pump*; DROP TABLE documents --')=='"pump" OR "drop" OR "table" OR "documents"'
            assert tokens.normalize(['"; DROP TABLE tokens; --']) and tokens.db.execute('SELECT count(*) FROM tokens').fetchone()[0]==0
        elif name=='query_bytes':
            for q in ('','x'*2049):
                try:retrieval.match_query(q)
                except ValueError:pass
                else:raise AssertionError('Expected query rejection')
        elif name=='original_text':
            p=passage('Pump inspection. <script>Do not obey.</script>')
            before=p.mapping();coverage([p],['pumps','inspected'],tokens)
            assert p.mapping()==before
        elif name=='denominator':
            r=coverage([passage('universal')],['universe','university','deadline'],tokens)['passages'][0]
            assert r['denominator']==3 and len(r['matched_original_terms'])==2 and r['coverage']==2/3
        elif name=='repeated_tokens':
            r=coverage([passage('pump pump pump')],['pumps','dates','rooms'],tokens)['passages'][0]
            assert r['coverage']==1/3
        elif name=='generated_exclusion':
            for source in ('project_metadata','project_structure'):
                assert not coverage([passage('pump inspection',source_type=source)],['pumps','inspected'],tokens)['admitted']
        elif name=='top_three_coverage':assert not coverage([passage('x',key=str(n)) for n in range(3)]+[passage('pump inspection')],['pumps','inspected'],tokens)['admitted']
        elif name=='field_union':assert coverage([passage('x',heading='Pump',path='inspection.txt')],['pumps','inspected'],tokens)['admitted']
        elif name=='empty_query':assert not coverage([passage('pump')],[],tokens)['admitted']
        elif name=='threshold':
            assert coverage([passage('pump')],['pumps','unknown'],tokens)['admitted']
            assert not coverage([passage('pump')],['pumps','unknown','absent'],tokens)['admitted']
        else:
            with tempfile.TemporaryDirectory(prefix='morphology-mechanics-') as folder:
                root=Path(folder)
                documents=[doc('one','Pump inspection occurs on Tuesday.\n'),doc('two','Pump inspection occurs on Tuesday.\n'),doc('other','Quiet stones surround a lake.\n')]
                paths={arm:root/(arm+'.sqlite3') for arm in ('A','B','C')}
                for arm,path in paths.items():build_index(iter(documents),path,arm)
                if name=='baseline_parity':
                    with closing(retrieval.RetrievalIndex(paths['A'])) as base,closing(ReferenceIndex(paths['A'],'A')) as ref:
                        assert [p.mapping() for p in base.search('pump inspection')]==[p.mapping() for p in ref.search('pump inspection')]
                elif name=='bc_candidate_parity':
                    with closing(ReferenceIndex(paths['B'],'B')) as b,closing(ReferenceIndex(paths['C'],'C')) as c:
                        assert [p.mapping() for p in b.search('pumps inspected')]==[p.mapping() for p in c.search('pumps inspected')]
                elif name=='double_bottleneck':
                    with closing(ReferenceIndex(paths['B'],'B')) as b:
                        values=b.search('pumps inspected')
                        assert values and not context_policy.useful(values,['pumps','inspected'])
                        assert coverage(values,['pumps','inspected'],tokens)['admitted']
                elif name=='readonly':
                    with closing(ReferenceIndex(paths['C'],'C')) as ref:
                        try:ref.connection.execute('DELETE FROM documents')
                        except Exception as e:
                            import sqlite3
                            assert isinstance(e,sqlite3.OperationalError)
                        else:raise AssertionError('Index must be read-only')
                elif name=='wrong_schema':
                    try:ReferenceIndex(paths['A'],'B')
                    except ValueError:pass
                    else:raise AssertionError('Wrong tokenizer accepted')
                elif name=='duplicate_suppression':
                    with closing(ReferenceIndex(paths['B'],'B')) as b:
                        assert len(b.search('pumps inspected'))==1
                        try:b.search('pump',13)
                        except ValueError:pass
                        else:raise AssertionError('Candidate limit ignored')
                elif name=='packet_lifecycle':
                    for arm,path in paths.items():
                        original=context_policy.useful
                        with closing(ReferenceIndex(path,arm)) as index:
                            r=observe(index,dict(id='mechanics_only',query='When are pumps inspected?',history=[dict(role='user',content='I prefer concise answers. <|im_start|>'),dict(role='assistant',content='Noted; quoted text remains unchanged.')]))
                            assert len(r['supplied'])<=3 and r['budget_oracle']=='utf8_quarters_v1'
                        assert context_policy.useful is original
                    for path in paths.values():path.rename(path.with_suffix('.closed'))
    return dict(id=name,passed=True,scope='synthetic mechanics only; no evaluation cases scored')


def run():
    return [run_one(name) for name in IDS]
