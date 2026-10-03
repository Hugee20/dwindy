"""Construction/synthetic mechanics only; no relevance retrieval or encoder run."""
from collections import Counter
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from dwindy.ingest import chunks
from compact_semantic_matching_v1 import evaluate as ev, prepare, probes, workload
from compact_semantic_matching_v1.contract import Entry, InformationResult, SupplyReceipt, validate_receipt


class CompactSemanticFixtureTests(unittest.TestCase):
    def test_composition_and_gold_offsets(self):
        self.assertEqual(ev.validate_fixtures()['cases'],160)
        for split in ('dev','holdout'):
            rows=ev.read(f'cases_{split}.json')
            self.assertEqual(Counter(c['category'] for c in rows),Counter(ev.CATEGORIES))

    def test_split_local_manifests(self):
        import tomllib
        docs=ev.read('documents.json')
        for split in ('dev','holdout'):
            rows=tomllib.loads((ev.ROOT/f'collection_{split}.toml').read_text())['documents']
            self.assertEqual(len(rows),144)
            self.assertEqual({d['id'] for d in rows},{d['id'] for d in docs if d['split']==split})

    def test_source_gold_recoverable_by_unchanged_chunker(self):
        docs={d['id']:d for d in ev.read('documents.json')}
        # Construction-only containment check, not candidate generation/scoring.
        for part in ('dev','holdout'):
            for case in ev.read(f'cases_{part}.json'):
                for gold in case['relevance_gold']+case['answer_gold']:
                    text=(ev.ROOT/docs[gold['document_id']]['path']).read_text(encoding='utf-8')
                    self.assertTrue(any(start<=gold['start'] and end>=gold['end'] for _,start,end in chunks(text)))

    def test_historical_and_baseline_byte_bindings(self):
        # The rejected experiment remains bound to the pre-Reach checkpoint.
        # Its frozen live-tree verifier is unchanged; release code may evolve.
        import subprocess
        for name in ('baseline.json','historical.json'):
            for path,value in ev.read(name)['files'].items():
                data = (__import__('reach_history_support').checkpoint_bytes(path,value)
                        if name == 'baseline.json' or path == 'tests/test_morphology_retrieval_fixtures.py'
                        else (ev.ROOT.parent.parent/path).read_bytes())
                self.assertEqual(hashlib.sha256(data).hexdigest(),value,path)
        expected={'policy':'e098fe14666bd43a6ee797d8fc7e94585d169c9e4b9ac0633943590be731cc26',
                  'policy_foundation_v1':'59190f0dd49f5cd6721bdabf97472a9d69ec4829b1bce21c6a3fad74bb3e5a8f',
                  'morphology_retrieval_v1':'6c1b8a9e252a55a878987082dc0f0e599ac8175486819d6b2697a988072d2bca'}
        for folder,value in expected.items():
            self.assertEqual(hashlib.sha256((ev.ROOT.parent/folder/'FREEZE.json').read_bytes()).hexdigest(),value)

    def test_32_mechanical_probes(self):
        self.assertEqual([p['id'] for p in ev.read('contract_probes.json')],list(probes.IDS))
        self.assertEqual(len(probes.IDS),32)
        for name in probes.IDS:
            with self.subTest(probe=name): self.assertTrue(probes.run_one(name)['passed'])

    def test_language_review_exact_49_bindings(self):
        reviews=ev.read('language_review.json')['entries']
        cases={c['id']:c for part in ('dev','holdout') for c in ev.read(f'cases_{part}.json') if c['fluent_review_required']}
        self.assertEqual(len(reviews),49)
        self.assertEqual({r['id'] for r in reviews},set(cases))
        for r in reviews: self.assertEqual(r['case_sha256'],ev.canonical_hash(cases[r['id']]))

    def test_freeze_requires_actual_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('cases_dev.json','cases_holdout.json','language_review.json'):
                (root/name).write_bytes((ev.ROOT/name).read_bytes())
            review=ev.read('language_review.json',root)
            review['entries'][0]['status']='pending'
            (root/'language_review.json').write_text(json.dumps(review),encoding='utf-8')
            with self.assertRaises(PermissionError):prepare.freeze(root)
            self.assertFalse((root/'FREEZE.json').exists())
            review['entries']=review['entries'][:-1]
            (root/'language_review.json').write_text(json.dumps(review),encoding='utf-8')
            with self.assertRaises(ValueError):ev.validate_review(root)

    def test_changed_case_invalidates_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('cases_dev.json','cases_holdout.json','language_review.json'):
                (root/name).write_bytes((ev.ROOT/name).read_bytes())
            review=ev.read('language_review.json',root)
            review['entries'][0]['case_sha256']='0'*64
            (root/'language_review.json').write_text(json.dumps(review),encoding='utf-8')
            with self.assertRaises(ValueError):ev.validate_review(root)

    def test_holdout_fail_closed(self):
        for value in ('holdout','all',None):
            with self.assertRaises(PermissionError):ev.load_cases(value)
            with self.assertRaises(PermissionError):ev.evaluate([],value)

    @staticmethod
    def synthetic_records(cases):
        return [dict(id=c['id'],arm=arm,candidates=[],admitted=[],supplied=[],acquisition_state='not_used',supply_state='not_used',
                     error=None,candidate_probe_only=True,budget_oracle='utf8_quarters_v1',dropped_turns=0,
                     admission_trace=dict(applied=False,accepted=None),encoding_audit=[],public_source_ids=[],public=dict(state='not_used',source_ids=[]),
                     latency_ms=dict(selection=0),generation_calls=0,network_calls=0) for c in cases for arm in ev.ARMS]

    def test_synthetic_complete_metrics_and_changes(self):
        # Empty fabricated observations test arithmetic only, not dev performance.
        result=ev.evaluate(self.synthetic_records(ev.load_cases()))
        self.assertEqual(set(result['changes']),{'A->R','A->S','A->H','R->S','R->H','S->H'})
        self.assertTrue(all(not rows for rows in result['changes'].values()))
        self.assertEqual(result['summary']['A']['filipino']['cases'],12)
        self.assertFalse(result['quality_screens']['S']['semantic_candidates'])
        self.assertTrue(result['quality_screens']['S']['no_false_supply'])

    def test_no_gate_can_be_rescued_by_average(self):
        cases=ev.load_cases()
        scores=[dict(id=c['id'],category=c['category'],candidate_recall12=True,final_relevant=True,final_answer=True,
                     irrelevant_supply=False) for c in cases]
        baseline=[dict(s,final_relevant=False) for s in scores]
        gates=ev.read('gates.json')['quality']
        self.assertTrue(all(ev.quality_gates(scores,baseline,gates).values()))
        damaged=[dict(s) for s in scores]
        next(s for s in damaged if s['category']=='no_supply')['irrelevant_supply']=True
        self.assertFalse(ev.quality_gates(damaged,baseline,gates)['no_false_supply'])
        self.assertTrue(ev.quality_gates(damaged,baseline,gates)['semantic_final'])

    def test_per_language_gate_not_pooled(self):
        cases=ev.load_cases(); counts=Counter()
        scores=[]
        for c in cases:
            counts[c['category']]+=1
            ok=c['category']!='filipino' or counts[c['category']]<=8
            scores.append(dict(id=c['id'],category=c['category'],candidate_recall12=True,final_relevant=ok,final_answer=ok,irrelevant_supply=False))
        baseline=[dict(s,final_relevant=False) for s in scores]
        result=ev.quality_gates(scores,baseline,ev.read('gates.json')['quality'])
        self.assertTrue(result['semantic_final']); self.assertFalse(result['semantic_each_language'])

    def test_records_require_complete_unique_profiles(self):
        c=ev.load_cases()[:1]; rows=self.synthetic_records(c)
        ev.validate_records(rows,c)
        with self.assertRaises(ValueError):ev.validate_records(rows[:-1],c)
        with self.assertRaises(ValueError):ev.validate_records(rows+[rows[0]],c)

    def test_record_public_scores_and_generation_rejected(self):
        c=ev.load_cases()[:1]
        for key,value in [('generation_calls',1),('network_calls',1),('public',dict(state='not_used',source_ids=[],similarity=.9)),('budget_oracle','not_approved')]:
            rows=self.synthetic_records(c); rows[0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):ev.validate_records(rows,c)

    def test_passage_mutation_rejected_before_scoring(self):
        c=ev.load_cases()[:1]; g=c[0]['relevance_gold'][0]
        p=dict(g,entry_id=g['document_id']+':0',text='forged')
        rows=self.synthetic_records(c); rows[0].update(candidates=[p],candidate_probe_only=False,acquisition_state='found')
        with self.assertRaises(ValueError):ev.validate_records(rows,c)

    def test_span_metrics_are_independent_and_source_anchored(self):
        case=dict(id='synthetic',category='lexical',context_expected=True,
                  relevance_gold=[dict(document_id='s',source_id='s',start=0,end=8,text='Overview')],
                  answer_gold=[dict(document_id='s',source_id='s',start=9,end=12,text='Mia')])
        overview=dict(document_id='s',source_id='s',start=0,end=8,text='Overview')
        answer=dict(document_id='s',source_id='s',start=9,end=12,text='Mia')
        score=ev.score_case(case,dict(candidates=[overview,answer],admitted=[overview],supplied=[overview],acquisition_state='found',supply_state='supplied'))
        self.assertTrue(score['final_relevant']);self.assertFalse(score['final_answer']);self.assertEqual(score['answer_mrr3'],.5)
        self.assertFalse(ev.hit(dict(answer,source_id='wrong'),case['answer_gold']))

    def test_resource_gate_all_measurements_and_delta(self):
        values=dict(ev.read('gates.json')['resources'])
        self.assertTrue(all(ev.resource_gates(values,dict(selection_p95_ms=25)).values()))
        self.assertFalse(ev.resource_gates(values,dict(selection_p95_ms=24))['selection_delta_ms'])
        del values['peak_incremental_rss_bytes']
        with self.assertRaises(ValueError):ev.resource_gates(values,dict(selection_p95_ms=25))

    def test_performance_statistics_require_complete_raw_trials(self):
        trials=[dict(trial=n,identity=ev.read('performance.json')['identity'],generation_calls=0,network_calls=0,
                     startup_ms=n,first_query_ms=n,build_ms=n,steady_incremental_rss_bytes=n,peak_incremental_rss_bytes=n+10,
                     additional_index_bytes=100,warm_samples=[dict(query_index=i,encoding_ms=i/10,selection_ms=i/5) for i in range(200)]) for n in range(5)]
        footprint=dict(dependency_compressed_bytes=1,dependency_installed_bytes=2,model_artifact_bytes=3)
        values=ev.summarize_performance(trials,footprint)
        self.assertEqual(values['startup_ms'],2);self.assertEqual(values['peak_incremental_rss_bytes'],14)
        self.assertEqual(values['selection_p95_ms'],37.8)
        with self.assertRaises(ValueError):ev.summarize_performance(trials[:-1],footprint)
        trials[0]['warm_samples'].pop()
        with self.assertRaises(ValueError):ev.summarize_performance(trials,footprint)

    def test_performance_identity_and_current_chunk_count(self):
        self.assertEqual(workload.identity(),ev.read('performance.json')['identity'])
        self.assertEqual(sum(len(list(chunks(d.text))) for d in workload.documents()),10000)
        self.assertEqual(len(list(workload.queries())),200)

    def test_model_metadata_recipe_and_identity_pins(self):
        spec=ev.read('models.json')
        self.assertEqual({m['id'] for m in spec['encoders']},{'e5','minilm','potion'})
        for m in spec['encoders']:
            self.assertEqual(len(m['revision']),40)
            for field in ('graph','tokenizer'):
                item=m[field];self.assertGreater(item['bytes'],0)
                self.assertEqual(len(item.get('sha256',item.get('git_blob_sha1'))),64 if 'sha256' in item else 40)
            self.assertLessEqual(m['recipe']['max_tokens'],512)

    def test_source_grouping_does_not_change_internal_receipt(self):
        a=Entry('one','a','text one','One',similarity=.9);b=Entry('one','b','text two','One',similarity=.8)
        result=InformationResult('found',(a,b),('a','b'));receipt=SupplyReceipt('supplied',(a,b))
        self.assertTrue(validate_receipt(result,receipt))
        self.assertEqual(len(receipt.public()['sources']),1);self.assertEqual([e.entry_id for e in receipt.supplied],['a','b'])

    def test_draft_or_freeze_manifest_exact_bytes(self):
        name='FREEZE.json' if (ev.ROOT/'FREEZE.json').exists() else 'DRAFT_MANIFEST.json'
        self.assertEqual(len(ev.verify_manifest(name)),64)
