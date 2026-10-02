import io
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from dwindy import context_policy
from dwindy.backend import ContextLimitError, GenerationOptions, Message
from dwindy.context_policy import CUES, ContextDecision, cue_count, decide, useful
from dwindy.core import DwindyCore
from dwindy.evidence import GUIDANCE, UNAVAILABLE_GUIDANCE, Evidence, Passage, Source
from dwindy.retrieval import STOPWORDS, RetrievalError, match_query, query_terms
from test_terminal import FakeBackend

sys.path.insert(0, str(Path(__file__).parent))
from context.evaluate import CUE_TABLE_CAP, load


def passage(text, path='docs/a.md', source_type='project_documentation'):
    return Passage(Source('d', 'c', 'Doc', path, 'h', 1, 1, 0, len(text), '', source_type), text)


class FakeSearch:
    def __init__(self, passages=(), error=None):
        self.passages, self.error, self.queries = tuple(passages), error, []

    def __call__(self, query, limit):
        self.queries.append((query, limit))
        if self.error:
            raise RetrievalError(self.error)
        return self.passages


def old_match_query(query):
    """The M6/M7 implementation, kept verbatim to prove the refactor is identical."""
    terms = list(dict.fromkeys(t.casefold() for t in re.findall(r"[^\W_]+", query, re.UNICODE)
                              if t.casefold() not in STOPWORDS))[:32]
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)


class ContextPolicyTests(unittest.TestCase):
    def test_cue_table_is_capped_and_regex_only_for_shapes(self):
        self.assertLessEqual(cue_count(), CUE_TABLE_CAP)
        for category, entries in CUES.items():
            if category != 'shape':
                self.assertTrue(all(re.fullmatch(r"[a-z ]+", entry) for entry in entries), category)

    def test_search_expression_unchanged(self):
        root = Path(__file__).parent
        queries = [json.loads(line)['query'] for name in ('retrieval/queries.jsonl', 'project/queries.jsonl')
                   for line in (root/name).read_text(encoding='utf-8').splitlines()]
        queries += [case['message'] for case in load('cases.jsonl')] + ['DISPLAY_LIMIT "quoted" AND OR*', 'Ünïcode ÄÖ']
        for query in queries:
            self.assertEqual(match_query(query), old_match_query(query), query)
            self.assertEqual(" OR ".join(f'"{t}"' for t in query_terms(query)), old_match_query(query).replace('""', '"'))

    def test_fast_paths_never_search(self):
        search = FakeSearch([passage('Returns use asset tags.')])
        for message, reason in (('Hello!', 'conversational'), ('Thanks!', 'conversational'),
                                ('Can you repeat your previous answer?', 'history_reference'),
                                ('Write a poem about returns.', 'self_contained_task'),
                                ('Translate to French: returns use asset tags today.', 'self_contained_task')):
            decision, evidence = decide(message, 'auto', search=search)
            self.assertEqual((decision.reason, decision.attempted, evidence), (reason, False, None), message)
        self.assertEqual(search.queries, [])
        # Pleasantries followed by content fall through instead of being swallowed.
        record = FakeSearch([passage('Record returns with the asset tag.')])
        self.assertEqual(decide('Hi, how do I record returns?', 'auto', search=record)[0].reason, 'relevant_match')

    def test_ambiguous_requests_fall_through_and_are_gated(self):
        relevant = FakeSearch([passage('Borrowers reserve a microscope through Reservations.')])
        decision, evidence = decide('How do I reserve a microscope?', 'auto', search=relevant)
        self.assertEqual((decision.reason, evidence.fallback, len(evidence.passages)), ('relevant_match', 'plain', 1))
        weak = FakeSearch([passage('The loan duration is eight days.')])
        decision, evidence = decide('What is a good loan duration for a public library?', 'auto', search=weak)
        self.assertEqual((decision.reason, decision.attempted, evidence), ('weak_match', True, None))
        self.assertEqual(decide('What is photosynthesis?', 'auto', search=FakeSearch())[0].reason, 'no_candidates')

    def test_generated_documents_alone_never_justify_supply(self):
        generated = passage('name = "lantern" version = "0.4.2" python', '@project/metadata', 'project_metadata')
        self.assertFalse(useful((generated,), ['latest', 'python', 'version']))
        self.assertTrue(useful((generated, passage('Python version 3.13 is supported.')), ['python', 'version']))

    def test_project_directed_supplies_with_m6_guidance_and_normalizes_only_the_query(self):
        search = FakeSearch()
        decision, evidence = decide('What does this system do?', 'auto', search=search, project_name='Lantern Desk')
        self.assertEqual(search.queries, [('What does Lantern Desk do?', 12)])
        self.assertTrue(decision.query_normalized)
        self.assertEqual((evidence.fallback, evidence.passages), ('insufficient', ()))
        for message in ('Why is DISPLAY_LIMIT 12?', 'Where is recordReturn?', 'Open web/returns.ts',
                        'What does the documentation say?', 'Tell me a story about Lantern Desk'):
            self.assertEqual(decide(message, 'auto', search=FakeSearch(), project_name='Lantern Desk')[0].reason,
                             'project_directed', message)
        for message in ('Where is Paris?', 'Explain TCP/IP', 'What is node.js?', 'Is it red and/or blue?'):
            self.assertNotEqual(decide(message, 'auto', search=FakeSearch())[0].reason, 'project_directed', message)
        self.assertFalse(decide('What does this system do?', 'auto', search=FakeSearch())[0].query_normalized)

    def test_modes_limits_and_failures(self):
        self.assertEqual(decide('x', 'off', search=FakeSearch()), (ContextDecision('off', False, 'off'), None))
        decision, evidence = decide('hello', 'on', search=FakeSearch())
        self.assertEqual((decision.reason, evidence.fallback), ('explicit', 'insufficient'))
        with self.assertRaises(RetrievalError): decide('hello', 'on', search=FakeSearch(error='retrieval_busy'))
        with self.assertRaises(RetrievalError): decide('hello', 'on')
        with self.assertRaises(ValueError): decide('hello', 'always')
        self.assertEqual(decide('hello', 'auto')[0].reason, 'no_index')
        self.assertEqual(decide('x' * 2049, 'auto', search=FakeSearch())[0].reason, 'message_too_long')
        decision, evidence = decide('What does this app do?', 'auto', search=FakeSearch(error='retrieval_busy'))
        self.assertEqual((decision.reason, evidence.fallback), ('retrieval_busy', 'unavailable'))
        with patch.object(context_policy, 'CONSTRAINED_FALLBACK', False):
            with self.assertRaises(RetrievalError):
                decide('What does this app do?', 'auto', search=FakeSearch(error='retrieval_busy'))
        decision, evidence = decide('How long is a loan?', 'auto', search=FakeSearch(error='retrieval_unavailable'))
        self.assertEqual((decision.reason, decision.attempted, evidence), ('retrieval_unavailable', True, None))
        with patch.object(context_policy, 'classify', side_effect=RuntimeError):
            self.assertEqual(decide('How long is a loan?', 'auto', search=FakeSearch()), (ContextDecision('auto', False, 'policy_error'), None))

    def test_metadata_is_truthful_and_on_off_unchanged(self):
        core = dict(status='supplied', sources=[{'document_id': 'd'}])
        self.assertIs(ContextDecision('on', True, 'explicit').metadata(core), core)
        self.assertIsNone(ContextDecision('off', False, 'off').metadata(None))
        self.assertEqual(ContextDecision('auto', False, 'conversational').metadata(None),
                         dict(mode='auto', attempted=False, status='not_used', reason='conversational', sources=[]))
        self.assertEqual(ContextDecision('auto', True, 'retrieval_busy').metadata(None)['status'], 'unavailable')
        self.assertEqual(ContextDecision('auto', True, 'relevant_match').metadata(dict(status='not_used', sources=[]))['reason'],
                         'budget_exhausted')
        self.assertTrue(ContextDecision('auto', True, 'project_directed', True).metadata(core)['query_normalized'])


class CoreFallbackTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend(limit=4000)
        self.core = DwindyCore(self.backend, options=GenerationOptions(max_tokens=5), system_prompt='Be brief.')

    def plain_messages(self, text):
        other_backend = FakeBackend(limit=self.backend.limit)
        other = DwindyCore(other_backend, options=GenerationOptions(max_tokens=5), system_prompt='Be brief.')
        other.restore(self.core.snapshot())
        list(other.chat(text))
        return other_backend.requests[-1]

    def test_plain_fallback_is_byte_identical_to_ordinary_chat(self):
        list(self.core.chat('first'))
        expected = self.plain_messages('question')
        events = list(self.core.chat('question', evidence=Evidence((), fallback='plain')))
        self.assertEqual(events[0].retrieval, dict(status='not_used', sources=[]))
        self.assertEqual(self.backend.requests[-1], expected)
        unfit = Evidence((passage('x' * 1600),), max_tokens=10, fallback='plain')
        expected = self.plain_messages('again')
        self.assertEqual(list(self.core.chat('again', evidence=unfit))[0].retrieval['status'], 'not_used')
        self.assertEqual(self.backend.requests[-1], expected)
        self.assertNotIn('Source 1', self.backend.requests[-1][-1].content)

    def test_plain_fallback_when_guidance_cannot_fit(self):
        self.backend.limit = 60
        events = list(self.core.chat('q', evidence=Evidence((passage('fact'),), max_tokens=1, fallback='plain')))
        self.assertEqual(events[0].retrieval['status'], 'not_used')
        self.assertEqual(self.backend.requests[-1], [Message('system', 'Be brief.'), Message('user', 'q')])
        with self.assertRaises(ContextLimitError):
            list(self.core.chat('q', evidence=Evidence((passage('fact'),), max_tokens=1)))

    def test_unavailable_instruction_is_transient(self):
        events = list(self.core.chat('Who uses this app?', evidence=Evidence((), fallback='unavailable')))
        self.assertEqual(events[0].retrieval, dict(status='unavailable', sources=[]))
        self.assertEqual(self.backend.requests[-1], [Message('system', 'Be brief.\n\n' + UNAVAILABLE_GUIDANCE),
                                                     Message('user', 'Who uses this app?')])
        self.assertEqual(self.core.snapshot(), (Message('user', 'Who uses this app?'), Message('assistant', 'ok')))
        list(self.core.chat('next'))
        self.assertNotIn(UNAVAILABLE_GUIDANCE, str(self.backend.requests[-1]))
        with self.assertRaises(ValueError):
            Evidence((passage('fact'),), fallback='unavailable')

    def test_insufficient_default_keeps_m6_behavior(self):
        events = list(self.core.chat('q', evidence=Evidence(())))
        self.assertEqual(events[0].retrieval, dict(status='no_match', sources=[]))
        self.assertIn(GUIDANCE, self.backend.requests[-1][0].content)


class TerminalContextTests(unittest.TestCase):
    class Index:
        project_snapshot = {'name': 'Lantern Desk'}
        def __init__(self, passages=(), error=None):
            self.search = FakeSearch(passages, error)

    def run_terminal(self, lines, **kwargs):
        from dwindy.__main__ import terminal
        backend = FakeBackend(limit=4000)
        out = io.StringIO()
        inputs = iter(lines)
        terminal(DwindyCore(backend, options=GenerationOptions(max_tokens=5)), read=lambda _: next(inputs), output=out, **kwargs)
        return backend, out.getvalue()

    def test_terminal_uses_the_same_policy(self):
        index = self.Index([passage('Borrowers reserve a microscope through Reservations.')])
        backend, out = self.run_terminal(['How do I reserve a microscope?', 'Hello!', '/exit'], index=index, mode='auto')
        self.assertEqual(out.count('[Local context: 1 passage(s).]'), 1)
        self.assertEqual(backend.requests[-1], [Message('user', 'How do I reserve a microscope?'), Message('assistant', 'ok'),
                                                Message('user', 'Hello!')])
        self.assertEqual(len(backend.requests), 2)

    def test_terminal_on_failure_reports_and_continues(self):
        backend, out = self.run_terminal(['loan?', 'Hello!', '/exit'], index=self.Index(error='retrieval_busy'), mode='on')
        self.assertEqual(out.count('Error: Local retrieval is unavailable'), 2)  # Forced retrieval never falls back.
        self.assertEqual(backend.requests, [])

    def test_retrieval_flag_requires_index(self):
        from dwindy.__main__ import main
        with patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit):
            main(['--retrieval', 'auto'])


if __name__ == '__main__':
    unittest.main()
