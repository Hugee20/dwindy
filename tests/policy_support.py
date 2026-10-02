"""M11 test support: pinned M10 modules and recording model-free backend."""
import subprocess
import sys
import types
from dwindy.backend import Completion, TextDelta
from test_terminal import FakeBackend

BASELINE='25ea503202ba9b8030a78c2ac59df117aac7d0b9'


def baseline_core():
    for name,path in (('_m10_evidence','src/dwindy/evidence.py'),('_m10_core','src/dwindy/core.py')):
        full='dwindy.'+name
        if full in sys.modules: continue
        code=subprocess.check_output(['git','show',BASELINE+':'+path]).decode('utf-8')
        if name=='_m10_core': code=code.replace('from .evidence import','from ._m10_evidence import')
        module=types.ModuleType(full);module.__package__='dwindy';sys.modules[full]=module
        exec(compile(code,BASELINE+':'+path,'exec'),module.__dict__)
    return sys.modules['dwindy._m10_core'].DwindyCore


def baseline_inputs(data):
    baseline_core()
    module=sys.modules['dwindy._m10_evidence']
    evidence=data.get('evidence');facts=data.get('facts')
    if evidence:
        evidence=module.Evidence(tuple(module.Passage(module.Source(**p.source.mapping()),p.text,p.score)
                                      for p in evidence.passages),evidence.max_tokens,evidence.fallback,evidence.origin,evidence.framing)
    if facts: facts=module.Facts(facts.computed,facts.host,facts.host_budget)
    return dict(evidence=evidence,facts=facts,notice=data.get('notice'))


class RecordingBackend(FakeBackend):
    def __init__(self,limit=20000,failure=None,text='ok',reason='stop'):
        super().__init__(limit,failure);self.text=text;self.reason=reason
        self.close_while_active=False;self.in_generate=False
    def generate(self,messages,options):
        if self.in_generate: raise AssertionError('Concurrent model reuse')
        self.in_generate=True;self.requests.append(list(messages))
        try:
            if self.text: yield TextDelta(self.text)
            if self.failure: raise self.failure
            yield Completion(self.reason,self.count_tokens(messages),len(self.text))
        finally:
            self.closed_streams+=1;self.in_generate=False
    def close(self):
        self.close_while_active|=self.in_generate
