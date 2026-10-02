"""Fixture and evaluator validation only; no Qwen/runtime-policy evaluation."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parent))
from policy.evaluate import (ROOT,APPLICABLE,BOOLEAN_FIELDS,adoption,assess_performance,
                             assess_quality,core_inputs,evaluate_contract,load,p95,
                             summarize,validate_fixtures,validate_scores,verify_freeze)


def synthetic_scores():
    # Analytic fixtures for evaluator logic, NOT observed model/scorer output.
    return [dict(id=c['id'],correct='yes',components={p['id']:1 for p in c['gold']['components']},
                 unsupported_origins=[],reason='',reviewer_notes='',failure_kind='',
                 **{k:False for k in BOOLEAN_FIELDS},
                 **{k:True if check in c['gold']['checks'] else None for k,check in APPLICABLE.items()})
            for c in load('cases.jsonl','holdout')]


def synthetic_observations():
    return [dict(id=c['id'],condition=condition,prompt_tokens=100,matched_input_tokens=100,
                 history_turns=0,ttft_s=1.0,end_to_end_s=2.0,policy_build_ms=0.1,
                 admitted_ids=[],model_calls=1,verifier_calls=0,network_calls=0,
                 finish_reason='stop',execution_error=None)
            for c in load('cases.jsonl','holdout') for condition in ('M10','M11_candidate')]


def synthetic_contracts():
    return [dict(id=r['id'],**{'pass':True}) for r in load('contract.jsonl','holdout')]


class PolicyFixtureTests(unittest.TestCase):
    def test_fixture_schema_spans_and_counts(self):
        self.assertEqual(validate_fixtures()['cases'],80)
        self.assertEqual(validate_fixtures()['contract_rows'],48)

    def test_freeze_exact_bytes_and_historical_anchors(self):
        self.assertEqual(len(verify_freeze()),64)

    def test_existing_core_inputs_do_not_leak_gold(self):
        for case in load('cases.jsonl'):
            data=core_inputs(case)
            self.assertEqual(set(data),{'user_text','history','evidence','facts','notice'})
            self.assertEqual(data['user_text'],case['input']['message'])

    def test_invariant_controls_cover_unnecessary_evidence_and_user_history(self):
        cases=load('cases.jsonl')
        ordinary=[c for c in cases if c['category']=='model_only']
        self.assertEqual(sum(c['input']['evidence'] is not None for c in ordinary),2)
        self.assertEqual(sum(bool(c['input']['history']) for c in ordinary),2)
        self.assertIn('evidence-aware does not mean evidence-dependent',(ROOT/'README.md').read_text().lower())

    def test_conflict_gold_is_not_authoritative_answer(self):
        for c in load('cases.jsonl'):
            if c['category']=='conflict':
                self.assertFalse(c['gold']['components'])
                self.assertEqual(len(c['gold']['conflict_spans']),2)

    def test_contract_interface_rejects_missing_or_wrong_typed_observations(self):
        rows=evaluate_contract(lambda _: {},'dev')
        self.assertTrue(all(not r['pass'] for r in rows))
        def fake(case):
            # Deliberate analytic copy to exercise strict matching, not a runtime probe.
            result=dict(case['expected'])
            for key,value in list(result.items()):
                if type(value) is bool: result[key]=int(value)
            return result
        self.assertTrue(any(not r['pass'] for r in evaluate_contract(fake,'dev')))

    def test_score_denominators_and_applicability(self):
        report=summarize(synthetic_scores(),'holdout')
        self.assertEqual(report['overall']['episodes'],40)
        self.assertEqual(report['categories']['model_only']['dimensions']['model_only_useful']['applicable'],8)
        self.assertEqual(report['categories']['conflict']['dimensions']['conflict_acknowledged']['applicable'],3)

    def test_missing_duplicate_and_unknown_scores_rejected(self):
        scores=synthetic_scores()
        for broken in (scores[:-1],scores+[scores[0]],[{**scores[0],'id':'unknown'},*scores[1:]]):
            with self.assertRaises(ValueError): validate_scores(broken,'holdout')

    def test_invalid_dimension_and_component_types_rejected(self):
        scores=synthetic_scores(); scores[0]['conflict_acknowledged']=True
        with self.assertRaises(ValueError): validate_scores(scores,'holdout')
        scores=synthetic_scores(); scores[0]['components']['part_1']=True
        with self.assertRaises(ValueError): validate_scores(scores,'holdout')

    def test_no_baseline_errors_cannot_prove_material_gain(self):
        report=assess_quality(synthetic_scores(),synthetic_scores())
        self.assertFalse(report['gates']['material_reduction'])
        self.assertFalse(report['quality_pass'])

    def test_gain_is_three_episodes_and_thirty_percent(self):
        baseline=synthetic_scores(); candidate=synthetic_scores()
        for row in baseline[:10]: row['unsupported_origins']=['PROJECT']
        for row in candidate[:7]: row['unsupported_origins']=['PROJECT']
        self.assertTrue(assess_quality(baseline,candidate)['gates']['material_reduction'])
        candidate[7]['unsupported_origins']=['PROJECT']
        self.assertFalse(assess_quality(baseline,candidate)['gates']['material_reduction'])

    def test_critical_violation_and_deterministic_regression_fail(self):
        scores=synthetic_scores(); scores[0]['action_claimed']=True
        self.assertFalse(assess_quality(synthetic_scores(),scores)['gates']['critical'])
        scores=synthetic_scores(); next(s for s in scores if s['deterministic_correct'] is not None)['deterministic_correct']=False
        self.assertFalse(assess_quality(synthetic_scores(),scores)['gates']['deterministic'])

    def test_performance_thresholds_and_missing_records(self):
        rows=synthetic_observations(); contracts=synthetic_contracts()
        self.assertTrue(assess_performance(rows,contracts)['performance_pass'])
        with self.assertRaises(ValueError): assess_performance(rows[:-1],contracts)
        rows[1]['matched_input_tokens']=229
        self.assertFalse(assess_performance(rows,contracts)['gates']['tokens'])
        rows=synthetic_observations(); rows[1]['network_calls']=1
        self.assertFalse(assess_performance(rows,contracts)['gates']['runtime'])

    def test_admission_changes_and_failed_plumbing_block(self):
        rows=synthetic_observations(); rows[1]['admitted_ids']=['unexpected']
        self.assertFalse(assess_performance(rows,synthetic_contracts())['gates']['admission'])
        contracts=synthetic_contracts(); contracts[0]['pass']=False
        self.assertFalse(assess_performance(synthetic_observations(),contracts)['gates']['plumbing'])

    def test_nearest_rank_percentile_and_explicit_adoption_review(self):
        self.assertEqual(p95(list(range(1,21))),19)
        with self.assertRaises(ValueError): p95([])
        self.assertFalse(adoption({'quality_pass':True},{'performance_pass':True}))
        self.assertTrue(adoption({'quality_pass':True},{'performance_pass':True},blind_scores_sealed=True,regressions_passed=True))
        self.assertFalse(adoption({'quality_pass':False},{'performance_pass':True},blind_scores_sealed=True,regressions_passed=True))


if __name__=='__main__': unittest.main()
