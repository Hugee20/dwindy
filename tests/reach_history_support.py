"""Replay deferred Reach against its committed implementation, not today's production.

No new evaluation: the existing historical tests retain their original assertions.
228f023 is the clean checkpoint preceding practical Reach. Frozen fixtures are untouched.
"""
import subprocess
import sys
import types

CHECKPOINT = '228f023'


def module(name):
    full = 'dwindy._historical_reach_' + name
    if full in sys.modules:
        return sys.modules[full]
    dependencies = {'core': ('evidence',), 'reach': ('evidence',), 'server': ('reach',),
                    'api': ('core', 'server', 'reach', 'evidence')}
    for dep in dependencies.get(name, ()):
        module(dep)
    path = ('tests/' if name == 'policy_probes' else 'src/dwindy/') + name + '.py'
    code = subprocess.check_output(['git', 'show', CHECKPOINT + ':' + path]).decode('utf-8')
    for dep in dependencies.get(name, ()):
        code = code.replace('from .' + dep + ' import', 'from ._historical_reach_' + dep + ' import')
    code = code.replace('from . import capabilities, reach',
                        'from . import capabilities\nfrom . import _historical_reach_reach as reach')
    if name == 'policy_probes':
        for dep in ('core', 'reach', 'server'):
            module(dep)
            code = code.replace('from dwindy.' + dep + ' import',
                                'from dwindy._historical_reach_' + dep + ' import')
        code = code.replace('from test_api import TestClient, create_app',
                            'from test_api import TestClient\nfrom dwindy._historical_reach_api import create_app')
        code = code.replace("'dwindy.api.", "'dwindy._historical_reach_api.")
        module('api')
    result = types.ModuleType(full)
    result.__package__ = 'dwindy'
    sys.modules[full] = result
    exec(compile(code, CHECKPOINT + ':' + path, 'exec'), result.__dict__)
    if name == 'evidence':
        # Immutable contracts are shared; only framing/functions are historical.
        from dwindy import evidence
        for kind in ('Source', 'Passage', 'Evidence', 'Facts'):
            setattr(result, kind, getattr(evidence, kind))
    if name == 'reach':
        from dwindy.reach import ReachError
        result.ReachError = ReachError
    return result


reach = module('reach')


def bind_foundation():
    """Keep the archived deployment-disabled probe bound to its original server."""
    from policy_experiments.archive import module as archived
    for version in ('foundation_v1', 'foundation_v2'):
        archived(version, 'probes').ApiConfig = module('server').ApiConfig


def checkpoint_bytes(path, expected):
    """Recover recorded Windows checkout bytes from the immutable Git blob.

    Git normalized some (not all) source files at checkpoint time. Accept only an
    exact recorded hash of the blob or its normal CRLF checkout transformation.
    """
    import hashlib
    data = subprocess.check_output(['git', 'show', CHECKPOINT + ':' + path])
    for candidate in (data, data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
        if hashlib.sha256(candidate).hexdigest() == expected:
            return candidate
    raise AssertionError('Checkpoint cannot reproduce frozen baseline bytes: ' + path)
