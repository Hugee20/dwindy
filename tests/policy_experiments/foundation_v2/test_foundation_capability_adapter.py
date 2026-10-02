"""Compatibility checks never change or retroactively pass the frozen probes."""
import unittest
from unittest.mock import patch
from dwindy.core import DwindyCore
from dwindy.backend import Message
from foundation_capability_v2 import NEW, capture, observe
from policy_foundation_v1 import probes as frozen
from policy_foundation_v1.evaluate import evaluate_contract, load, verify_freeze


class CapabilityAdapterTests(unittest.TestCase):
    def test_frozen_incompatibility_is_preserved(self):
        rows = evaluate_contract(frozen.observe)
        self.assertEqual([r['id'] for r in rows if not r['pass']], ['capability_1', 'capability_2'])
        self.assertEqual(frozen.CAPABILITY, 'DWINDY/action-capability: no host-action executor is available.')
        self.assertEqual(verify_freeze(), '59190f0dd49f5cd6721bdabf97472a9d69ec4829b1bce21c6a3fad74bb3e5a8f')

    def test_compatibility_contract_and_placement_pass(self):
        self.assertTrue(all(r['pass'] for r in evaluate_contract(observe)))
        for case in load('contract.jsonl'):
            if case['family'] == 'capability':
                self.assertTrue(all(capture(case)[1].values()), case['id'])

    def test_non_capability_profiles_delegate_unchanged(self):
        case = next(c for c in load('contract.jsonl') if c['family'] != 'capability')
        with patch.object(frozen, 'observe', return_value={'sentinel': True}) as delegated:
            self.assertEqual(observe(case), {'sentinel': True})
        delegated.assert_called_once_with(case, core_type=DwindyCore)

    def test_wrong_rendering_fails_instead_of_copying_expectations(self):
        class Damaged(DwindyCore):
            def _bounded_turn(self, *args, **kwargs):
                messages, recent = super()._bounded_turn(*args, **kwargs)
                return [Message(m.role, m.content.replace(NEW, 'absent')) for m in messages], recent
        case = next(c for c in load('contract.jsonl') if c['id'] == 'capability_1')
        observed, audit = capture(case, core_type=Damaged)
        self.assertFalse(observed['capability_present'])
        self.assertFalse(observed['runtime_fact_correct'])
        self.assertFalse(audit['system_exact'])
