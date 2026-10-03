"""Small ordinary adapter tests with synthetic vectors; no installed encoder needed."""
import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from compact_semantic_matching_v1_run import runner


class FakeTokenizer:
    def encode(self,text,add_special_tokens=False):
        class Encoded: pass
        result=Encoded();result.ids=[1]*len(text);result.offsets=[(i,i+1) for i in range(len(text))]
        return result


class FakeModel:
    median_token_length=1
    tokenizer=FakeTokenizer()
    unk_token_id=0
    def __init__(self):self.calls=[]
    def encode(self,texts,**kwargs):
        import numpy as np
        self.calls.extend(texts)
        values=np.zeros((len(texts),256),dtype='float32')
        for i,t in enumerate(texts):values[i,0 if 'red' in t or 'scarlet' in t else 1]=1.
        return values


class SemanticRunnerTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'index.sqlite'
        documents=[]
        for n,text in enumerate(('red items are stored in locker A.','blue items are stored in locker B.')):
            documents.append(runner.Document(f'synth-{n}',f'synth-{n}.txt',f'Record {n}', '.txt',text,hashlib.sha256(text.encode()).hexdigest()))
        runner.write_documents(documents,self.path);self.index=runner.RetrievalIndex(self.path)
        self.model=FakeModel();self.experiment=runner.Experiment(self.index,self.model)
    def tearDown(self):self.index.close();self.folder.cleanup()

    def case(self,query):return dict(id='synthetic',query=query,mode='auto',history=[])

    def test_discovery_ceiling_and_actual_supply_identity(self):
        r=self.experiment.observe(self.case('scarlet'), 'R',.75)
        s=self.experiment.observe(self.case('scarlet'), 'S',.75)
        self.assertEqual(r['candidates'],[]);self.assertEqual(r['supplied'],[])
        self.assertEqual(s['supplied'][0]['document_id'],'synth-0')
        self.assertEqual(s['supplied'][0]['text'],'red items are stored in locker A.')
        self.assertEqual(s['core_retrieval']['sources'][0]['chunk_id'],s['supplied'][0]['chunk_id'])
        self.assertNotIn('cosine',s['public']);self.assertEqual(s['generation_calls'],0)

    def test_model_only_bypasses_encoder_and_acquisition(self):
        before=len(self.model.calls)
        for arm in runner.ev.ARMS:
            row=self.experiment.observe(self.case('Hello!'),arm,.75)
            self.assertEqual(row['acquisition_state'],'not_used');self.assertEqual(row['supplied'],[])
        self.assertEqual(len(self.model.calls),before)

    def test_lexical_baseline_calls_unchanged_policy(self):
        with patch.object(runner.policy,'decide',wraps=runner.policy.decide) as decide:
            row=self.experiment.observe(self.case('red'),'A',.75)
        decide.assert_called_once();self.assertEqual(row['supplied'][0]['document_id'],'synth-0')

    def test_rank_fusion_preserves_original_entries(self):
        values=self.experiment.passages
        result=runner.hybrid(values,tuple(reversed(values)))
        self.assertEqual(result,values)
        self.assertEqual(runner.deduplicate(values+values),values)

    def test_truncation_audit_and_original_text_remain_separate(self):
        from dataclasses import replace
        p=replace(self.experiment.passages[0],text='red '+('x'*700))
        audit=runner.view_audit(self.model,p)
        self.assertEqual(audit['retained_tokens'],512)
        self.assertLess(audit['body_end'],len(p.text));self.assertEqual(len(p.text),704)
