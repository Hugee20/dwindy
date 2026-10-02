"""Hash-checked historical Foundation modules; never replace production modules.

Only immutable data classes are shared with production so frozen fixtures can be
passed through their existing public interface. Rendering and Core execution use
archived source. Runtime/probe/test imports bind explicitly to the same version.
"""
import hashlib
import inspect
import json
import sys
import types
from pathlib import Path
ROOT = Path(__file__).parent

def module(version, name):
    if version not in ('foundation_v1', 'foundation_v2'):
        raise ValueError('Unknown historical candidate')
    directory = ROOT / version
    hashes = json.loads((directory / 'PRESERVED.json').read_text())
    for filename, digest in hashes.items():
        if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != digest:
            raise AssertionError('Historical candidate changed: ' + filename)
    prefix = '_archive_' + version + '_'
    key = ('dwindy.' if name in ('core', 'evidence') else '') + prefix + name
    if key in sys.modules:
        return sys.modules[key]
    if name != 'evidence':
        ev = module(version, 'evidence')
        core = module(version, 'core') if name != 'core' else None
    path = directory / (name + '.py')
    if name == 'probes':
        from policy_foundation_v1.evaluate import verify_freeze
        verify_freeze()
        path = ROOT.parent / 'policy_foundation_v1' / 'probes.py'
    if name == 'eval_policy_foundation_v2_dev':
        module(version, 'foundation_capability_v2')
    if name.startswith('test_'):
        if name == 'test_policy_foundation_runner': module(version, 'eval_policy_foundation_dev')
        else: module(version, 'foundation_capability_v2')
    if name in ('foundation_capability_v2', 'eval_policy_foundation_dev', 'eval_policy_foundation_v2_dev', 'test_foundation_capability_adapter'):
        module(version, 'probes')
    source = path.read_text(encoding='utf-8')
    source = source.replace('from .evidence import', 'from .' + prefix + 'evidence import')
    source = source.replace('from dwindy.core import', 'from dwindy.' + prefix + 'core import')
    source = source.replace('from dwindy.evidence import', 'from dwindy.' + prefix + 'evidence import')
    source = source.replace('import dwindy.evidence as', 'import dwindy.' + prefix + 'evidence as')
    source = source.replace('from policy_foundation_v1 import probes as frozen', 'import ' + prefix + 'probes as frozen')
    source = source.replace('from policy_foundation_v1.probes import', 'from ' + prefix + 'probes import')
    source = source.replace('from foundation_capability_v2 import', 'from ' + prefix + 'foundation_capability_v2 import')
    source = source.replace('from eval_policy_foundation_dev import', 'from ' + prefix + 'eval_policy_foundation_dev import')
    source = source.replace("'eval_policy_foundation_dev.LlamaBackend'", repr(prefix + 'eval_policy_foundation_dev.LlamaBackend'))
    loaded = types.ModuleType(key)
    loaded.__package__ = 'dwindy' if name in ('core', 'evidence') else ''
    loaded.__file__ = str(path)
    sys.modules[key] = loaded
    exec(compile(source, str(path), 'exec'), loaded.__dict__)
    if name == 'evidence':
        from dwindy import evidence as public
        for value in ('Source', 'Passage', 'Evidence', 'Facts'):
            archived = getattr(loaded, value)
            current = getattr(public, value)
            if inspect.getsource(archived) != inspect.getsource(current):
                raise AssertionError('Historical fixture schema changed: ' + value)
            setattr(loaded, value, current)
    return loaded
