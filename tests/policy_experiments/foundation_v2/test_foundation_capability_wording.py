"""Implementation-only wording checks; both frozen evaluations remain untouched."""
from pathlib import Path
import unittest

from dwindy.backend import GenerationOptions, Message
from dwindy.core import DwindyCore
import dwindy.evidence as evidence
from policy_support import RecordingBackend

OLD = 'DWINDY/action-capability: no host-action executor is available.'
NEW = 'DWINDY/action-capability: Dwindy (this assistant) cannot perform actions in the host application.'


class CapabilityWordingTests(unittest.TestCase):
    def test_only_capability_sentence_changed_from_foundation_v1(self):
        # The unchanged development manifest anchors the prior production module.
        import hashlib
        import json
        prior = Path('eval-results/policy-foundation-v2-preparation/foundation-v1-evidence.py')
        if not prior.exists():
            self.skipTest('Local prior-runtime snapshot not distributed')
        manifest = json.loads(Path('eval-results/policy-foundation-dev-01/manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(prior.read_bytes()).hexdigest(), manifest['code_hashes']['src/dwindy/evidence.py'])
        self.assertEqual(Path(evidence.__file__).read_bytes(), prior.read_bytes().replace(OLD.encode(), NEW.encode()))

    def test_host_information_and_action_share_existing_exact_system_placement(self):
        for request in ('What record does the application report?', 'Change my delivery address.'):
            with self.subTest(request=request):
                backend = RecordingBackend()
                core = DwindyCore(backend, options=GenerationOptions(max_tokens=5))
                facts = evidence.Facts(host=(('record', 'Current value remains unchanged.'),))
                list(core.chat(request, facts=facts))
                self.assertEqual(backend.requests[-1], [
                    Message('system', evidence.GUIDANCE + '\n\nRuntime capability:\n' + NEW),
                    Message('user', evidence.facts_block(facts) + 'User question:\n' + request)])
                self.assertNotIn(OLD, str(backend.requests[-1]))
                self.assertEqual(core.snapshot()[0], Message('user', request))
                self.assertNotIn(NEW, str(core.snapshot()))

    def test_trigger_remains_current_nonempty_host_facts_only(self):
        history = (Message('user', 'previous'), Message('assistant', 'previous reply'))
        for facts in (None, evidence.Facts(), evidence.Facts(computed=(('calculator', '2 + 2 = 4'),))):
            with self.subTest(facts=facts):
                backend = RecordingBackend()
                core = DwindyCore(backend, options=GenerationOptions(max_tokens=5))
                core.restore(history)
                list(core.chat('follow up', facts=facts))
                self.assertNotIn(NEW, str(backend.requests[-1]))

    def test_known_fact_subject_is_dwindy_not_host_incapability(self):
        self.assertEqual(evidence.RUNTIME_CAPABILITY, 'Runtime capability:\n' + NEW)
        self.assertNotIn('host application cannot', evidence.RUNTIME_CAPABILITY)
        self.assertNotIn('application does not support', evidence.RUNTIME_CAPABILITY)
        self.assertNotIn('host lacks', evidence.RUNTIME_CAPABILITY)
