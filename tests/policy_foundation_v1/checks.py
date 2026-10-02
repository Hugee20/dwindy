"""Foundation-v1 mechanics only. Synthetic grades are not model/holdout output."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from policy_foundation_v1 import evaluate as e
from policy_foundation_v1.probes import observe,Backend,make_core
from dwindy.backend import Message
from policy_support import baseline_core

def scores(split='holdout'):
 return [dict(id=c['id'],correct='yes',turn_correct=['yes']*len(c['turns']),components={p['id']:1 for p in c['gold']['components']},unsupported_origins=[],reason='',reviewer_notes='',**{k:False for k in e.BOOLS},**{k:True if c['controls'][control] else None for k,control in e.APPLICABLE.items()}) for c in e.load('cases.jsonl',split)]
def observations():
 return [dict(id=c['id'],turn=t,condition=condition,prompt_tokens=100,matched_input_tokens=100,retained_turns=0,admitted_ids=[],ttft_s=1.0,end_to_end_s=2.0,construction_ms=.1,output_tokens=10,model_calls=1,verifier_calls=0,network_calls=0,execution_error=None,finish_reason='stop',budget_audit_pass=True) for c in e.load('cases.jsonl','holdout') for t in range(len(c['turns'])) for condition in ('M10','M11_foundation')]
def contracts():return [dict(id=c['id'],**{'pass':True}) for c in e.load('contract.jsonl')]
def altered_core(backend,transform,**kwargs):
 # Negative observation control; no production transform or public setting.
 from dwindy.core import DwindyCore
 class Adapter:
  def context_size(self):return backend.context_size()
  def count_tokens(self,messages):return backend.count_tokens(messages)
  def generate(self,messages,options):yield from backend.generate(transform(messages),options)
 return DwindyCore(Adapter(),**kwargs)
class FoundationFixtureTests(unittest.TestCase):
 def test_composition_and_spans(self):
  self.assertEqual(e.validate_fixtures(),dict(episodes=48,dev=24,holdout=24,turns=56,paired_generations=112,probes=32,components=20,injection_episodes=6,attribution_episodes=8))
 def test_freeze_and_historical_integrity(self):self.assertEqual(len(e.verify_freeze()),64)
 def test_actual_input_conversion_does_not_leak_gold(self):
  for c in e.load('cases.jsonl'):
   for i in range(len(c['turns'])):
    actual=e.turn_inputs(c,i);self.assertEqual(actual['user_text'],c['turns'][i]['message']);self.assertEqual(set(actual),{'user_text','history','evidence','facts','notice'});self.assertIsNone(actual['history'] if i else None)
 def test_regression_patterns_and_controls_are_present(self):
  patterns={p for c in e.load('cases.jsonl') for p in c['patterns']}
  self.assertTrue({'quoted_then_denied_path','mixed_clock_host_misattribution','known_host_data_not_denied','irrelevant_evidence_not_required','escaped_newline_continuity_regression','user_preference_speaker_continuity'}<=patterns)
 def test_every_profile_executes_without_echoing_expected(self):
  # Execution here checks probe wiring on existing experimental v3, NOT acceptance.
  # We deliberately poison expectations; observations must stay independently typed.
  for row in e.load('contract.jsonl'):
   changed=copy.deepcopy(row);changed['expected']={k:'POISONED_EXPECTATION' for k in row['expected']}
   actual=observe(changed)
   self.assertEqual(set(row['expected'])-set(actual),set(),row['id'])
   self.assertTrue(all(type(actual[k]) is type(v) for k,v in row['expected'].items()),row['id'])
 def test_native_history_probe_detects_demoting_adapter(self):
  row=next(c for c in e.load('contract.jsonl') if c['setup']['profile']=='native_history/ordinary_followup')
  # Test-only malformed adapter, independent of whichever implementation is installed.
  def demoted(backend,**kwargs):return altered_core(backend,lambda messages:[Message('user','transcript data')],**kwargs)
  self.assertFalse(observe(row,core_type=demoted)['native_roles'])
  self.assertTrue(observe(row,core_type=baseline_core())['native_roles'])
 def test_probe_observations_detect_damaged_framing(self):
  row=next(c for c in e.load('contract.jsonl') if c['family']=='escaping')
  def damaged(backend,**kwargs):return altered_core(backend,lambda messages:[Message('user','damaged')],**kwargs)
  self.assertFalse(observe(row,core_type=damaged)['round_trip_exact'])
 def test_contract_matching_requires_values_and_exact_types(self):
  self.assertTrue(all(not r['pass'] for r in e.evaluate_contract(lambda _:{})))
  def analytic(case):return {k:int(v) if type(v) is bool else v for k,v in case['expected'].items()}
  self.assertTrue(any(not r['pass'] for r in e.evaluate_contract(analytic)))
 def test_complete_per_turn_scores_and_denominators(self):
  summary=e.summarize(scores(),'holdout');self.assertEqual(summary['overall']['episodes'],24);self.assertEqual(summary['overall']['gold_components'],10);self.assertEqual(summary['families']['continuity']['dimensions']['continuity_satisfied']['applicable'],4)
  bad=scores();r=next(s for s in bad if len(s['turn_correct'])==2);r['turn_correct'][0]='no'
  with self.assertRaises(ValueError):e.validate_scores(bad,'holdout')
 def test_missing_duplicate_unknown_and_mistyped_scores_rejected(self):
  rows=scores()
  for bad in (rows[:-1],rows+[rows[0]],[dict(rows[0],id='unknown')]+rows[1:]):
   with self.assertRaises(ValueError):e.validate_scores(bad,'holdout')
  bad=scores();bad[0]['components']['part_1']=True
  with self.assertRaises(ValueError):e.validate_scores(bad,'holdout')
  bad=scores();bad[0]['model_only_useful']=True
  with self.assertRaises(ValueError):e.validate_scores(bad,'holdout')
 def test_supported_component_or_unsupported_addition_fails(self):
  for change in ('component','unsupported'):
   candidate=scores()
   if change=='component':candidate[0]['components']['part_1']=0
   else:candidate[0]['unsupported_origins']=['PROJECT']
   self.assertFalse(e.assess_quality(scores(),candidate)['gates']['supported'])
 def test_each_applicable_behavior_is_not_an_average(self):
  for field,gate in (('deterministic_correct','deterministic'),('host_boundary','host_action'),('continuity_satisfied','continuity'),('origin_correct','attribution'),('model_only_useful','evidence_independence')):
   candidate=scores();next(r for r in candidate if r[field] is not None)[field]=False
   self.assertFalse(e.assess_quality(scores(),candidate)['gates'][gate])
 def test_critical_violations_each_block(self):
  for field in ('action_claimed','injection_followed','fabricated_citation','confidence_fabricated','provenance_leaked','provenance_misrepresented'):
   candidate=scores();candidate[0][field]=True;self.assertFalse(e.assess_quality(scores(),candidate)['gates']['critical'])
 def test_caveat_union_counts_once_and_retains_plus_one_limit(self):
  candidate=scores();candidate[0]['unnecessary_caveat']=candidate[0]['unnecessary_refusal']=True
  self.assertTrue(e.assess_quality(scores(),candidate)['gates']['caveats'])
  candidate[1]['unnecessary_caveat']=True;self.assertFalse(e.assess_quality(scores(),candidate)['gates']['caveats'])
 def test_ordinary_category_regression_is_not_hidden_by_other_gains(self):
  candidate=scores();r=next(x for x in candidate if x['id'].startswith('ordinary'));r.update(correct='no',turn_correct=['no'],reason='Analytic test')
  self.assertFalse(e.assess_quality(scores(),candidate)['gates']['ordinary_nonregression'])
 def test_performance_and_exact_turn_coverage(self):
  self.assertTrue(e.assess_performance(observations(),contracts())['performance_pass'])
  for broken in (observations()[:-1],observations()+observations()[:1]):
   with self.assertRaises(ValueError):e.assess_performance(broken,contracts())
  bad=observations();bad[0]['ttft_s']=float('nan')
  with self.assertRaises(ValueError):e.assess_performance(bad,contracts())
 def test_every_runtime_failure_blocks(self):
  for field,value in (('network_calls',1),('verifier_calls',1),('model_calls',2),('execution_error','Analytic error')):
   rows=observations();rows[0][field]=value;self.assertFalse(e.assess_performance(rows,contracts())['gates']['runtime'])
 def test_budget_admission_failed_contract_and_token_ceiling(self):
  rows=observations();rows[1]['admitted_ids']=['different'];self.assertFalse(e.assess_performance(rows,contracts())['gates']['admission'])
  rows=observations();rows[1]['budget_audit_pass']=False;self.assertFalse(e.assess_performance(rows,contracts())['gates']['admission'])
  rows=observations();rows[1]['matched_input_tokens']=229;self.assertFalse(e.assess_performance(rows,contracts())['gates']['tokens'])
  mechanical=contracts();mechanical[0]['pass']=False;self.assertFalse(e.assess_performance(observations(),mechanical)['gates']['plumbing'])
 def test_time_thresholds_and_percentiles(self):
  self.assertEqual(e.p95(list(range(1,21))),19)
  with self.assertRaises(ValueError):e.p95([])
  rows=observations()
  for r in rows:
   if r['condition']=='M11_foundation':r['construction_ms']=1.01
  self.assertFalse(e.assess_performance(rows,contracts())['gates']['construction'])
  rows=observations()
  for r in rows:
   if r['condition']=='M11_foundation':r['ttft_s']=2.01;r['end_to_end_s']=3
  self.assertFalse(e.assess_performance(rows,contracts())['gates']['ttft'])
 def test_development_cannot_trigger_holdout_acceptance(self):
  with self.assertRaises(ValueError):e.assess_quality(scores('dev'),scores('dev'),'dev')
  with self.assertRaises(ValueError):e.assess_performance([],[],'dev')
 def test_acceptance_requires_explicit_preconditions(self):
  q={'quality_pass':True};p={'performance_pass':True}
  self.assertFalse(e.adoption(q,p));self.assertTrue(e.adoption(q,p,blind_scores_sealed=True,regressions_passed=True,candidate_frozen_before_holdout=True,explicit_review=True));self.assertFalse(e.adoption({'quality_pass':False},p,blind_scores_sealed=True,regressions_passed=True,candidate_frozen_before_holdout=True,explicit_review=True))
