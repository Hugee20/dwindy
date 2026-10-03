"""Fixture/reference mechanics only. Never run a relevance split through A/B/C."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from morphology_retrieval_v1 import evaluate as ev, probes, reference, workload


class MorphologyFixtureTests(unittest.TestCase):
    def test_freeze_and_composition(self):
        self.assertEqual(len(ev.verify_freeze()),64)
        self.assertEqual(ev.validate_fixtures()['cases'],96)

    def test_baseline_sources_and_historical_hashes(self):
        reference.verify_runtime_sources()
        repo=ev.ROOT.parent.parent
        old=json.loads((ev.ROOT/'historical.json').read_text())
        for name,digest in old['files'].items():
            self.assertEqual(hashlib.sha256((repo/name).read_bytes()).hexdigest(),digest,name)
        for folder,expected in [('policy','e098fe14666bd43a6ee797d8fc7e94585d169c9e4b9ac0633943590be731cc26'),('policy_foundation_v1','59190f0dd49f5cd6721bdabf97472a9d69ec4829b1bce21c6a3fad74bb3e5a8f')]:
            self.assertEqual(hashlib.sha256((repo/'tests'/folder/'FREEZE.json').read_bytes()).hexdigest(),expected)

    def test_diagnostic_panels_and_manifests(self):
        import tomllib
        spec=json.loads((ev.ROOT/'diagnostics.json').read_text())
        repo=ev.ROOT.parent.parent
        self.assertFalse(spec['acceptance_credit'])
        self.assertEqual(sum(p['count'] for p in spec['panels']),112)
        for panel in spec['panels']:
            self.assertEqual(len((repo/panel['path']/panel['cases']).read_text(encoding='utf-8').splitlines()),panel['count'])
        documents=json.loads((ev.ROOT/'documents.json').read_text())
        for split in ('dev','holdout'):
            entries=tomllib.loads((ev.ROOT/f'collection_{split}.toml').read_text())['documents']
            self.assertEqual({d['id'] for d in entries},{d['id'] for d in documents if d['split']==split})

    def test_changes_report_all_pairs_without_real_observations(self):
        # Pure synthetic, empty observations: not a retrieval run or development
        # performance/quality result. Used only to test grouping/change mechanics.
        rows=[]
        for case in ev.load_cases('dev'):
            for arm in ev.ARMS:
                rows.append(dict(id=case['id'],arm=arm,candidates=[],supplied=[],candidate_probe_only=True,policy_attempted=False,
                    usefulness_applied=False,useful_admitted=None,decision='synthetic_empty' if arm!='C' else 'synthetic_other',retrieval_status=None,
                    latency_ms=dict(search=0,selection=0),budget_oracle='utf8_quarters_v1',
                    lexical_audit=dict(admitted=False,passages=[]),porter_audit=dict(admitted=False,passages=[]),
                    annotated_collision=[dict(original=t,stems=['synthetic']) for t in case['collision_pair']] if case['collision_pair'] else []))
        result=ev.evaluate(rows)
        self.assertEqual(set(result['changes']),{'A->B','A->C','B->C'})
        self.assertEqual(len(result['changes']['A->B']),0)
        self.assertEqual(len(result['changes']['A->C']),48)
        self.assertEqual(len(result['changes']['B->C']),48)
        self.assertEqual(result['summary']['A']['categories']['inflection']['cases'],6)
        self.assertEqual(result['summary']['A']['categories']['synonym']['cases'],6)
        self.assertFalse(result['screens']['C']['gain'])

    def test_contract_probes(self):
        declared=[json.loads(s) for s in (ev.ROOT/'contract.jsonl').read_text().splitlines()]
        self.assertEqual([p['id'] for p in declared],list(probes.IDS))
        for name in probes.IDS:
            with self.subTest(probe=name):self.assertTrue(probes.run_one(name)['passed'])

    def test_relevance_and_answer_metrics_are_distinct(self):
        case=dict(id='synthetic',category='inflection',diagnostic_only=False,context_expected=True,
                  relevance_gold=[dict(document_id='x',start=0,end=8,text='Overview')],
                  answer_gold=[dict(document_id='x',start=9,end=13,text='Neri')])
        overview=dict(document_id='x',start=0,end=8,text='Overview')
        answer=dict(document_id='x',start=9,end=13,text='Neri')
        def score(values,supplied):
            return ev.score_case(case,dict(candidates=values,supplied=supplied,usefulness_applied=True,useful_admitted=False,decision='weak_match',retrieval_status=None))
        a=score([overview],[])
        self.assertTrue(a['candidate_recall12']);self.assertFalse(a['answer_hit3']);self.assertFalse(a['final_relevant'])
        b=score([answer],[answer])
        self.assertFalse(b['candidate_recall12']);self.assertTrue(b['answer_hit1']);self.assertTrue(b['final_answer'])

    def test_holdout_scoring_fails_closed(self):
        with self.assertRaises(PermissionError):ev.evaluate([],split='holdout')
        with self.assertRaises(ValueError):ev.load_cases('all')

    def test_missing_duplicate_observations_rejected(self):
        case=ev.load_cases('dev')[0]
        with self.assertRaises(ValueError):ev.validate_records([], [case])
        with self.assertRaises(ValueError):ev.validate_records([dict(id=case['id'],arm='A')]*3,[case])

    def test_packet_mutation_and_caps_rejected(self):
        case=ev.load_cases('dev')[0];gold=case['answer_gold'][0]
        p=dict(gold,chunk_id='fake')
        rows=[dict(id=case['id'],arm=arm,candidates=[p],supplied=[p],candidate_probe_only=False,policy_attempted=True,
                   usefulness_applied=True,useful_admitted=True,latency_ms=dict(search=0,selection=0),budget_oracle='utf8_quarters_v1',
                   lexical_audit=dict(admitted=True,passages=[]),porter_audit=dict(admitted=True,passages=[])) for arm in ev.ARMS]
        ev.validate_records(rows,[case])
        for bad in ('changed_text','too_many','null_admission','negative_latency'):
            broken=json.loads(json.dumps(rows))
            if bad=='changed_text':broken[0]['supplied'][0]['text']='changed'
            elif bad=='too_many':broken[0]['supplied']*=4
            elif bad=='null_admission':broken[0]['useful_admitted']=None
            else:broken[0]['latency_ms']['selection']=-1
            with self.subTest(bad=bad),self.assertRaises(ValueError):ev.validate_records(broken,[case])

    def test_performance_gate_boundaries(self):
        base=dict(warm_selection_p95_ms=10,build_seconds=10,index_bytes=100,rss_increment_bytes=1000)
        candidate=dict(warm_selection_p95_ms=14.5,build_seconds=12,index_bytes=120,rss_increment_bytes=1000+8*1024*1024)
        self.assertTrue(all(ev.performance_gates(base,candidate).values()))
        candidate['warm_selection_p95_ms']=14.5001
        self.assertFalse(ev.performance_gates(base,candidate)['warm_relative'])
        self.assertEqual(ev.percentile95(range(1,101)),95)

    def test_workload_hash(self):
        spec=json.loads((ev.ROOT/'performance.json').read_text())
        self.assertEqual(workload.identity(),spec['identity'])

    def test_literal_gate_values(self):
        self.assertEqual(ev.GATES, json.loads((ev.ROOT/'gates.json').read_text()))


if __name__=='__main__':unittest.main()
