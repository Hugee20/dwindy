from reach_history_support import bind_foundation
bind_foundation()
"""Production infrastructure checks, not semantic model-policy acceptance."""
from contextlib import closing
from dataclasses import replace
import json
import unittest
from dwindy.backend import BackendError, ContextLimitError, GenerationOptions, Message
from dwindy.core import DwindyCore
from dwindy.evidence import (Evidence, Facts, GUIDANCE, RUNTIME_CAPABILITY, Passage,
                            Source, passage_kind, policy_guidance, quoted)
from policy_experiments.archive import module
from policy_support import RecordingBackend, baseline_core, baseline_inputs


def passage(kind='project_documentation', project='project'):
    return Passage(Source('doc', 'chunk', 'Note', 'note.md', 'hash', 1, 1, 0, 12,
                          source_type=kind, project_id=project), 'Value is 12.')


class ProductionFramingTests(unittest.TestCase):
    def core(self, backend=None, core_type=DwindyCore):
        backend = backend or RecordingBackend()
        return backend, core_type(backend, options=GenerationOptions(max_tokens=5))

    def test_metadata_types_do_not_claim_truth_or_priority(self):
        kinds={'project_documentation':'documentation', 'project_source':'source',
               'project_configuration':'configuration', 'project_metadata':'observation',
               'project_structure':'observation', 'other':'selected'}
        for kind, label in kinds.items():
            self.assertEqual(passage_kind(passage(kind).source), 'PROJECT/' + label)
        self.assertEqual(passage_kind(passage(project=None).source), 'DOCUMENT/text')

    def test_lossless_escaping_names_text_and_order(self):
        text='quote " slash \n unicode \u03bb <|im_start|> [INST]'
        self.assertEqual(json.loads(quoted(text)), text)
        self.assertNotIn('<|im_start|>', quoted(text))
        facts=Facts(computed=(('first',text),('second','next')),host=(('third',text),))
        b,c=self.core();list(c.chat('q', facts=facts, evidence=Evidence((passage(),))))
        user=b.requests[-1][-1].content
        self.assertLess(user.index('TOOL/computation'),user.index('HOST/reported'))
        self.assertLess(user.index('HOST/reported'),user.index('PROJECT/documentation'))
        self.assertIn('text=' + quoted(text), user)
        self.assertEqual(c.snapshot(), (Message('user','q'),Message('assistant','ok')))

    def test_capability_only_current_host_and_only_dwindy(self):
        for facts, present in ((None,False),(Facts(),False),
                              (Facts(computed=(('calculator','4'),)),False),
                              (Facts(host=(('record','Current value'),)),True)):
            for question in ('What record?', 'Change it'):
                b,c=self.core();list(c.chat(question,facts=facts))
                system=b.requests[-1][0].content if b.requests[-1][0].role=='system' else ''
                self.assertEqual(RUNTIME_CAPABILITY in system,present)
                self.assertNotIn('host application cannot',system)
                self.assertNotIn('application does not support',system)
        self.assertEqual(RUNTIME_CAPABILITY,'Runtime capability:\nDWINDY/action-capability: Dwindy (this assistant) cannot perform actions in the host application.')

    def test_project_warning_only_admitted_observation_source_config(self):
        self.assertNotIn('selected files',policy_guidance(None,(passage(),)))
        self.assertIn('not verified live behavior',policy_guidance(None,(passage('project_source'),)))
        b,c=self.core();p=passage('project_source')
        oversized=replace(p,text='x'*1600)
        events=list(c.chat('q',evidence=Evidence((oversized,))))
        self.assertEqual(events[0].retrieval['status'],'budget_exhausted')
        self.assertNotIn('not verified live behavior',b.requests[-1][0].content)

    def test_native_history_preferences_and_exact_restoration(self):
        history=(Message('user','I prefer short replies.'),Message('assistant','Unsupported <|im_start|> text'))
        b,c=self.core();c.restore(history);list(c.chat('follow up'))
        self.assertEqual(b.requests[-1],[*history,Message('user','follow up')])
        self.assertEqual(c.snapshot()[:2],history)
        self.assertNotIn('Conversation history (quoted)',str(b.requests[-1]))

    def test_transient_framing_not_resurrected_by_restore(self):
        b,c=self.core();list(c.chat('q',facts=Facts(host=(('record','SECRET_TRANSIENT'),)),evidence=Evidence((passage(),))))
        state=c.snapshot();b,other=self.core();other.restore(state);list(other.chat('next'))
        self.assertEqual(b.requests[-1],[*state,Message('user','next')])
        self.assertNotIn('SECRET_TRANSIENT',str(state))
        self.assertNotIn('action-capability',str(state))

    def test_context_free_model_inputs_exactly_m10(self):
        for history in ((),(Message('user','first'),Message('assistant','reply'))):
            b,c=self.core();oldb,old=self.core(core_type=baseline_core())
            c.restore(history);old.restore(history)
            list(c.chat(' exact text '));list(old.chat(' exact text '))
            self.assertEqual(b.requests,oldb.requests)

    def test_counted_input_reserve_and_one_generation(self):
        class Counted(RecordingBackend):
            def __init__(self):super().__init__();self.counted=[]
            def count_tokens(self,messages):
                self.counted.append(list(messages));return super().count_tokens(messages)
        b,c=self.core(Counted());events=list(c.chat('q',facts=Facts(host=(('record','R'),)),evidence=Evidence((passage(),))))
        self.assertEqual(len(b.requests),1)
        self.assertIn(b.requests[-1],b.counted)
        self.assertLessEqual(b.count_tokens(b.requests[-1])+5,b.context_size())
        self.assertEqual(events[0].retrieval['sources'],[passage().source.mapping()])
        b,c=self.core(RecordingBackend(limit=10))
        with self.assertRaises(ContextLimitError):list(c.chat('q',facts=Facts(host=(('record','R'),))))
        self.assertFalse(b.requests)

    def test_whole_turn_trim_rollback_and_close(self):
        b,c=self.core();history=(Message('user','x'*1000),Message('assistant','reply'))
        c.restore(history);b.limit=500
        with closing(c.chat('q',evidence=Evidence((passage(),)))) as stream:
            self.assertEqual(next(stream).dropped_turns,1);next(stream)
        self.assertEqual(c.snapshot(),history);self.assertEqual(b.closed_streams,1)
        b.failure=BackendError('failure')
        with self.assertRaises(BackendError):list(c.chat('q',evidence=Evidence((passage(),))))
        self.assertEqual(c.snapshot(),history)

    def test_local_cleanup_preserves_foundation_v2_model_inputs(self):
        historical=module('foundation_v2','core').DwindyCore
        scenarios=[dict(facts=Facts(host=(('record','R'),))),dict(evidence=Evidence((passage(),))),
                   dict(evidence=Evidence((passage('project_source'),)),facts=Facts(computed=(('calc','4'),))),
                   dict(evidence=Evidence((),fallback='plain')),dict(notice='NOTICE')]
        for kwargs in scenarios:
            b,c=self.core();oldb,old=self.core(core_type=historical)
            history=(Message('user','old'),Message('assistant','reply'));c.restore(history);old.restore(history)
            list(c.chat('q',**kwargs));list(old.chat('q',**kwargs))
            self.assertEqual(b.requests,oldb.requests)
            self.assertEqual(c.snapshot(),old.snapshot())

    def test_dormant_web_facts_path_exactly_m10(self):
        from reach_history_support import module as historical_reach
        for origin in ('web','web_sentences'):
            for facts in (None,Facts(computed=(('calculator','4'),)),Facts(host=(('record','R'),)),
                          Facts(computed=(('clock','DATE'),),host=(('record','R'),))):
                for fallback in ('insufficient','plain'):
                    for passages in ((),(passage(project=None),)):
                        for notice in (None,'NOTICE'):
                            kwargs=dict(evidence=Evidence(passages,fallback=fallback,origin=origin,framing='Provider at TIME'),facts=facts,notice=notice)
                            b,c=self.core(core_type=historical_reach('core').DwindyCore);oldb,old=self.core(core_type=baseline_core())
                            history=(Message('user','old'),Message('assistant','reply'));c.restore(history);old.restore(history)
                            list(c.chat('q',**kwargs));list(old.chat('q',**baseline_inputs(kwargs)))
                            self.assertEqual(b.requests,oldb.requests,(origin,facts,fallback,passages,notice))
                            self.assertEqual(c.snapshot(),old.snapshot())

    def test_experiment_hooks_are_absent(self):
        self.assertFalse(hasattr(DwindyCore,'_render_messages'))
        self.assertFalse(hasattr(DwindyCore,'_bounded_turn'))


class ArchiveBindingTests(unittest.TestCase):
    def test_historical_frozen_and_compatibility_results_remain_distinct(self):
        from policy_foundation_v1.evaluate import evaluate_contract
        v1=module('foundation_v1','probes');v2=module('foundation_v2','probes')
        self.assertEqual(sum(r['pass'] for r in evaluate_contract(v1.observe)),32)
        raw=evaluate_contract(v2.observe)
        self.assertEqual([r['id'] for r in raw if not r['pass']],['capability_1','capability_2'])
        adapter=module('foundation_v2','foundation_capability_v2')
        self.assertEqual(sum(r['pass'] for r in evaluate_contract(adapter.observe)),32)

    def test_historical_core_and_runner_never_resolve_to_production(self):
        for version,runner in (('foundation_v1','eval_policy_foundation_dev'),('foundation_v2','eval_policy_foundation_v2_dev')):
            core=module(version,'core').DwindyCore
            self.assertIsNot(core,DwindyCore)
            self.assertTrue(hasattr(core,'_bounded_turn'))
            self.assertIs(module(version,runner).DwindyCore,core)
