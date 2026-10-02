import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parent))
from policy.evaluate import evaluate_contract,verify_freeze
from policy_probes import observe

class PolicyContractTests(unittest.TestCase):
    def test_all_48_frozen_contract_profiles(self):
        verify_freeze()
        rows=evaluate_contract(observe,None)
        self.assertEqual(len(rows),48)
        self.assertTrue(all(r['pass'] for r in rows),[r for r in rows if not r['pass']])
