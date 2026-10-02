"""Versioned implementation compatibility check, NOT frozen acceptance.

Only the capability observer recognizes the approved new literal. The four
profiles, inputs, contract fields, exclusion checks and fake backend are the
same as the frozen probe. All other observers delegate unchanged. No frozen
module/constant is patched, and the original 30/32 result stays visible.
"""
from dwindy.backend import Message
from dwindy.core import DwindyCore
from dwindy.evidence import Facts, GUIDANCE
from policy_foundation_v1 import probes as frozen

NEW = 'DWINDY/action-capability: Dwindy (this assistant) cannot perform actions in the host application.'
VERSION = 'capability_wording_v2'


def capture(case, core_type=DwindyCore):
    family, profile = case['setup']['profile'].split('/')
    if family != 'capability':
        raise ValueError('Compatibility capture accepts capability profiles only')
    if profile not in ('host_information', 'host_action', 'computed_only', 'history_only'):
        raise ValueError('Unknown frozen capability profile')
    backend = frozen.Backend()
    core = frozen.make_core(backend, core_type)
    host = profile in ('host_information', 'host_action')
    facts = Facts(host=(('record', 'FOUNDATION_HOST_PAYLOAD'),)) if host else (
        Facts(computed=(('calculator', '2 + 2 = 4'),)) if profile == 'computed_only' else None)
    history = (Message('user', 'old user text'), Message('assistant', 'old assistant text'))
    if profile == 'history_only':
        core.restore(history)
    question = 'Change it' if profile == 'host_action' else 'What is the record?'
    list(core.chat(question, facts=facts))
    messages = backend.requests[-1]
    system = '\n'.join(m.content for m in messages if m.role == 'system')
    observed = dict(capability_present=NEW in system,
                    runtime_fact_correct=NEW in system if host else NEW not in system,
                    host_capability_inferred=any(s in system.lower() for s in (
                        'host application cannot', 'application does not support', 'host lacks')))
    # Placement/transience/accounting are existing mechanical invariants,
    # recorded separately rather than added to the frozen contract mapping.
    expected_system = GUIDANCE + '\n\nRuntime capability:\n' + NEW if host else GUIDANCE if facts else ''
    audit = dict(system_exact=system == expected_system,
                 sentence_not_in_user=all(NEW not in m.content for m in messages if m.role != 'system'),
                 original_literal_absent=frozen.CAPABILITY not in system,
                 token_accounting_exact=messages in backend.counted,
                 context_reserve=backend.count_tokens(messages) + 5 <= backend.limit,
                 host_budget_unchanged=facts is None or facts.host_budget == 1024,
                 one_generation=len(backend.requests) == 1,
                 transient=NEW not in str(core.snapshot()))
    return observed, audit


def observe(case, core_type=DwindyCore):
    if case['family'] != 'capability':
        return frozen.observe(case, core_type=core_type)
    return capture(case, core_type)[0]
