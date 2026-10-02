"""Historical v3 model-free checks; never replace production modules."""
import hashlib,json,sys,types
from pathlib import Path
ROOT=Path(__file__).parent/'v3'
def load_test(name):
    hashes=json.loads((ROOT/'PRESERVED.json').read_text(encoding='utf-8'))
    for filename,digest in hashes.items():
        if hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()!=digest:
            raise AssertionError('Historical v3 changed: '+filename)
    for local,filename in (('dwindy._v3_evidence','evidence.py'),('dwindy._v3_core','core.py'),('_v3_test_policy_framing','test_policy_framing.py'),('_v3_test_policy_history','test_policy_history.py')):
        if local in sys.modules:continue
        module=types.ModuleType(local);module.__package__='dwindy' if local.startswith('dwindy.') else '';module.__file__=str(ROOT/filename)
        code=(ROOT/filename).read_text(encoding='utf-8').replace('from .evidence import','from ._v3_evidence import').replace('from dwindy.core import','from dwindy._v3_core import').replace('from dwindy.evidence import','from dwindy._v3_evidence import').replace('from test_policy_framing import','from _v3_test_policy_framing import').replace('from test_terminal import conversation_messages','from policy_experiments.history_support import conversation_messages')
        sys.modules[local]=module;exec(compile(code,module.__file__,'exec'),module.__dict__)
    return sys.modules['_v3_'+name]
