"""Model-free foundation probes. Observe real inputs/state; never return fixture expectations.

These are acceptance probes for a future assembled implementation. The current experimental
v3 is not that implementation; fixture validation must not report it as accepted.
"""
from contextlib import closing
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from dwindy.backend import BackendError, Completion, ContextLimitError, GenerationOptions, Message, TextDelta
from dwindy.core import DwindyCore
from dwindy.evidence import Evidence, Facts, Passage, Source
from dwindy.persistence import ConversationStore
from dwindy.reach import HONESTY_NOTICE
from dwindy.config import ConfigError
from dwindy.server import ApiConfig

CAPABILITY='DWINDY/action-capability: no host-action executor is available.'

class Backend:
    def __init__(self,limit=20000,text='probe reply',failure=False):
        self.limit=limit;self.text=text;self.failure=failure;self.requests=[];self.counted=[];self.closed=0
    def close(self):pass
    def context_size(self):return self.limit
    def count_tokens(self,messages):
        self.counted.append(tuple(messages));return sum(len(m.content)+1 for m in messages)
    def generate(self,messages,options):
        self.requests.append(tuple(messages))
        try:
            if self.failure:raise BackendError('fixture failure')
            if self.text:yield TextDelta(self.text)
            yield Completion('stop',self.count_tokens(messages),len(self.text))
        finally:self.closed+=1

def passage(text='FOUNDATION_LOCAL_PAYLOAD',kind='local_text',project=False):
    return Passage(Source('foundation-d','foundation-c','Fixture note','docs/fixture.md','fixture',1,1,0,len(text),source_type=kind,project_id='fixture-project' if project else None),text)

def make_core(backend,core_type,history=()):
    core=core_type(backend,options=GenerationOptions(max_tokens=5));core.restore(tuple(history));return core

def records(messages):
    """Parse actual typed data records; decoding here is an observation, not rendering."""
    out=[]
    for m in messages:
        for line in m.content.splitlines():
            if line.startswith('Source ') or line.startswith(('HOST/reported ','TOOL/computation ')):
                if ' text=' in line:
                    out.append((line.split(' text=',1)[0],json.loads(line.split(' text=',1)[1])))
    return out

def observe(case,core_type=DwindyCore):
    # The fixture's expected mapping is deliberately never consulted.
    family,profile=case['setup']['profile'].split('/')
    b=Backend();history=(Message('user','old user text'),Message('assistant','old assistant text'))
    core=make_core(b,core_type)
    if family=='origins':
        kind=case['setup']['source_type']
        kinds=([kind,'project_configuration'] if kind=='project_source' else [kind,'project_metadata','future_unknown_type'] if kind=='project_structure' else [kind,'local_text'] if kind=='project_documentation' else [kind])
        items=[]
        for i,k in enumerate(kinds):
            text='DATA_'+str(i);items.append(Passage(Source('d'+str(i),'c'+str(i),'Note '+str(i),'docs/note.md','fixture',1,1,0,len(text),source_type=k,project_id='fixture-project' if k!='local_text' else None),text))
        events=list(core.chat('q',evidence=Evidence(tuple(items))))
        wanted=['DOCUMENT/text' if k=='local_text' else 'PROJECT/'+{'project_documentation':'documentation','project_source':'source','project_configuration':'configuration','project_structure':'observation','project_metadata':'observation'}.get(k,'selected') for k in kinds]
        found=records(b.requests[-1])
        return dict(label_matches_metadata=len(found)==len(items) and all(label in record[0] for label,record in zip(wanted,found)),text_preserved=[record[1] for record in found]==[p.text for p in items],order_preserved=[p.source.chunk_id for p in items]==[s['chunk_id'] for s in events[0].retrieval['sources']])
    if family=='capability':
        host=profile in ('host_information','host_action');facts=Facts(host=(('record','FOUNDATION_HOST_PAYLOAD'),)) if host else Facts(computed=(('calculator','2 + 2 = 4'),)) if profile=='computed_only' else None
        if profile=='history_only':core.restore(history)
        list(core.chat('Change it' if profile=='host_action' else 'What is the record?',facts=facts));system='\n'.join(m.content for m in b.requests[-1] if m.role=='system')
        return dict(capability_present=CAPABILITY in system,runtime_fact_correct=CAPABILITY in system if host else CAPABILITY not in system,host_capability_inferred=any(s in system.lower() for s in ('host application cannot','application does not support','host lacks')))
    if family=='escaping':
        text=case['setup']['text'];facts=Facts(host=(('record',text),));list(core.chat('q',facts=facts));actual=b.requests[-1];rs=records(actual)
        return dict(round_trip_exact=len(rs)==1 and rs[0][1]==text,native_roles_unchanged=[m.role for m in actual]==['system','user'],untrusted_text_in_system=any(text in m.content for m in actual if m.role=='system'))
    if family=='native_history':
        core.restore(history if profile!='whole_turn_trim' else (*history,Message('user','keep'),Message('assistant','kept')))
        original=core.snapshot();evidence=Evidence((passage(),)) if profile=='current_evidence' else None
        if profile=='all_history_trim':b.limit=10
        elif profile=='whole_turn_trim':
            control_backend=Backend();control=make_core(control_backend,core_type,original[2:]);list(control.chat('q'));b.limit=sum(len(m.content)+1 for m in control_backend.requests[-1])+5
        events=list(core.chat('q',evidence=evidence));actual=b.requests[-1];kept=original[2*events[0].dropped_turns:]
        native=[m for m in actual if m.role in ('user','assistant')][:-1]
        return dict(native_roles=tuple(native)==kept,text_and_order_preserved=tuple(native)==kept,stored_history_native=core.snapshot()==(*kept,Message('user','q'),Message('assistant',b.text)),whole_turn_trimming=events[0].dropped_turns in range(len(original)//2+1) and len(kept)%2==0)
    if family=='transience':
        kwargs=dict(evidence=Evidence((passage(),))) if profile in ('evidence_snapshot','persistent_restart') else dict(facts=Facts(host=(('record','FOUNDATION_HOST_PAYLOAD'),))) if profile=='host_restore' else dict(notice='FOUNDATION_NOTICE_PAYLOAD')
        list(core.chat('original request',**kwargs));saved=core.snapshot()
        if profile=='persistent_restart':
            with tempfile.TemporaryDirectory() as tmp:
                store=ConversationStore(Path(tmp)/'conversation.sqlite3');store.append('F'*32,saved,'stop');store.close();store=ConversationStore(Path(tmp)/'conversation.sqlite3');restored=store.load('F'*32);store.close()
                core.restore(restored)
        elif profile=='host_restore':core=make_core(b,core_type,saved)
        original=core.snapshot();list(core.chat('followup'));stored=str(original)+str(core.snapshot())
        return dict(transient_payload_stored=any(t in stored for t in ('FOUNDATION_LOCAL_PAYLOAD','FOUNDATION_HOST_PAYLOAD','FOUNDATION_NOTICE_PAYLOAD')),original_turns_preserved=core.snapshot()[:2]==saved)
    if family=='budget':
        rejected=False
        if profile=='oversized_host':kwargs=dict(facts=Facts(host=(('record','z'*80),),host_budget=8));question='q'
        elif profile=='oversized_current':b.limit=10;kwargs={};question='z'*80
        else:
            kwargs=dict(evidence=Evidence((passage(),)));question='q'
            if profile=='nonadditive_cost':
                core.restore(history);count=b.count_tokens
                def nonlinear(messages):return count(messages)+(900 if any('Source 1' in m.content for m in messages) and any('old user text' in m.content for m in messages) else 0)
                b.count_tokens=nonlinear
        try:events=list(core.chat(question,**kwargs))
        except ContextLimitError:rejected=True
        observed=dict(counted_generated_identical=all(req in b.counted for req in b.requests),context_reserve_respected=all(b.count_tokens(req)+5<=b.limit for req in b.requests),rejection_before_generation=not rejected or not b.requests)
        if profile.startswith('oversized'):observed['model_calls']=len(b.requests)
        return observed
    if family=='lifecycle':
        b.failure=profile=='failure_rollback';b.text='' if profile=='empty_rollback' else 'probe reply';core.restore(history);before=core.snapshot()
        with closing(core.chat('q',evidence=Evidence((passage(),)))) as stream:
            try:
                if profile=='cancel_rollback':next(stream);next(stream)
                else:list(stream)
            except BackendError:pass
        expected=(*history,Message('user','q'),Message('assistant',b.text)) if profile=='one_call_success' else before
        return dict(model_calls=len(b.requests),rollback_or_commit_correct=core.snapshot()==expected,stream_closed=b.closed==1)
    if family=='public_boundary':
        if profile=='host_auth':
            import os
            from starlette.testclient import TestClient
            from dwindy.api import create_app
            from dwindy.config import Config
            outcomes=[];bodies=[]
            for configured,authorized in ((True,True),(True,False),(False,False)):
                backend=Backend();token='foundation-synthetic-bearer-123456789'
                with patch.dict(os.environ,{'DWINDY_API_TOKEN':token} if configured else {},clear=True):
                    app=create_app(Config(Path('unused.gguf'),max_tokens=5),ApiConfig(),backend=backend)
                with TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',1)) as client:
                    reply=client.post('/v1/chat',json={'message':'What is my record?','host_context':[{'label':'record','text':'HOST_DATA'}]},headers={'Authorization':'Bearer '+token} if authorized else {})
                outcomes.append((reply.status_code,len(backend.requests)));bodies.append(reply.json())
            return dict(boundary_preserved=outcomes[0]==(200,1) and all(code!=200 and calls==0 for code,calls in outcomes[1:]),no_public_confidence=all('confidence' not in json.dumps(body).lower() for body in bodies))
        if profile=='reach_disabled':
            try:ApiConfig(reach_provider='wikipedia').validate();allowed=True
            except ConfigError:allowed=False
            return dict(boundary_preserved=not allowed,no_public_confidence='confidence' not in ApiConfig.__dataclass_fields__)
        kwargs=dict(notice=HONESTY_NOTICE) if profile=='offline_notice' else dict(evidence=Evidence((passage(project=True,kind='project_structure'),)))
        events=list(core.chat('q',**kwargs));metadata=events[0].retrieval or {};text='\n'.join(m.content for m in b.requests[-1])
        return dict(boundary_preserved=HONESTY_NOTICE in text if profile=='offline_notice' else metadata.get('sources')==[passage(project=True,kind='project_structure').source.mapping()],no_public_confidence=not any(k in json.dumps(metadata).lower() for k in ('confidence','verified','grounded')))
    raise ValueError('Unknown probe profile')
