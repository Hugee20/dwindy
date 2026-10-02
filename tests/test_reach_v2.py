import itertools
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import pathspec  # noqa: F401  Needed only for the project-index notice rows.
except ImportError:
    pathspec = None

from project_support import materialize
from reach_support import ReplayTransport, combined_body, no_network
from test_api import create_app, TestClient
from test_terminal import FakeBackend
from dwindy import reach
from dwindy.backend import GenerationOptions
from dwindy.config import Config
from dwindy.core import DwindyCore
from dwindy.evidence import WEB_SENTENCE_GUIDANCE
from dwindy.server import ApiConfig

sys.path.insert(0, str(Path(__file__).parent))
from reach_v2.evaluate import GRID, MAX_CHARS, evaluate_notice, load, reference_select

EXTRA = Path(__file__).parent/'context'/'extra'


def runtime(case, **k):
    results = [reach.WebResult(r['title'], r['url'], r['text']) for r in case['results']]
    return [dict(title=s.title, url=s.url, sentence=s.text) for s in reach.select_sentences(results, case['query'], case['year'], **k)]


class ReachV2SelectionTests(unittest.TestCase):
    def setUp(self):
        # Reach is not adopted; these tests exercise the dormant v2 behavior explicitly.
        self.enterContext(patch.object(reach, 'REACH_ADOPTED', True))

    def test_runtime_reproduces_frozen_reference(self):
        cases = load('labels.jsonl')
        for case in cases:  # Chosen constants, every case.
            self.assertEqual(runtime(case), reference_select(case['results'], case['query'], case['year'], **reach.SELECTION), case['id'])
        for values in itertools.product(*(GRID[k] for k in ('predicate_weight', 'year_weight', 'min_score'))):
            k = dict(zip(('predicate_weight', 'year_weight', 'min_score'), values))
            for case in cases[:13]:  # Whole grid on development.
                self.assertEqual(runtime(case, **k), reference_select(case['results'], case['query'], case['year'], **k))
        self.assertTrue(all(reach.SELECTION[k] in GRID[k] for k in GRID))

    def test_supplied_sentences_keep_article_identity_and_budget(self):
        replay = ReplayTransport(combined_body('latest_python'))
        decision, evidence, notice = reach.decide('What is the latest stable version of Python?', 'auto',
                                                  backend=reach.WikipediaBackend(transport=replay))
        self.assertEqual((decision.used, decision.reason, notice), (True, 'supplied', None))
        self.assertLessEqual(sum(len(p.text) for p in evidence.passages), MAX_CHARS)
        self.assertEqual(evidence.origin, 'web_sentences')
        self.assertEqual({s.url for s in decision.sources}, {p.source.source_path for p in evidence.passages})
        backend = FakeBackend(limit=20000)  # FakeBackend counts characters: give it a character-sized allowance.
        roomy = reach.Evidence(evidence.passages, 6000, 'plain', origin=evidence.origin, framing=evidence.framing)
        list(DwindyCore(backend, options=GenerationOptions(max_tokens=5)).chat('q', evidence=roomy))
        user = backend.requests[-1][-1].content
        self.assertIn('Source 1 article="History of Python"', user)
        self.assertIn(' sentence="As of June 2026, Python 3.14.6 is the latest stable release."', user)
        self.assertIn(WEB_SENTENCE_GUIDANCE, backend.requests[-1][0].content)

    def test_abstention_reuses_not_useful_and_offline_notice(self):
        replay = ReplayTransport(combined_body('microsoft_ceo'))
        decision, evidence, notice = reach.decide('Who is the current CEO of Microsoft?', 'auto',
                                                  backend=reach.WikipediaBackend(transport=replay))
        self.assertEqual((decision.used, decision.reason, evidence, notice), (True, 'not_useful', None, reach.HONESTY_NOTICE))
        self.assertEqual(decision.sources, ())

    def test_v1_unit_still_replays_for_diagnostics(self):
        with patch.object(reach, 'EVIDENCE_UNIT', 'results'):
            decision, evidence, _ = reach.decide('What is the latest version of Android?', 'auto',
                                                 backend=reach.WikipediaBackend(transport=ReplayTransport(combined_body('android_version'))))
        self.assertEqual(evidence.origin, 'web')
        self.assertGreater(sum(len(p.text) for p in evidence.passages), MAX_CHARS)


@unittest.skipIf(pathspec is None, 'requires the optional dwindy[project] dependency')
class ReachV2NoticeTests(unittest.TestCase):
    def test_frozen_notice_rows(self):
        from dwindy.project import synchronize
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        shutil.copytree(EXTRA, root/'extra')
        synchronize(materialize(root, documents_manifest='extra/collection.toml'))

        def run(row):
            backend = FakeBackend(limit=20000)
            config = ApiConfig(retrieval_index_path=str(root/'index.sqlite3') if row['index'] else None)
            body = dict(message=row['message'])
            if row['retrieval'] is not None:
                body['retrieval'] = row['retrieval']
            with no_network(allow_loopback=True) as attempts, TestClient(create_app(Config(Path('unused.gguf'), max_tokens=5), config, backend=backend),
                                                                         base_url='http://127.0.0.1', client=('127.0.0.1', 1)) as client:
                client.post('/v1/chat', json=body)
            return dict(notice=reach.HONESTY_NOTICE in backend.requests[-1][0].content, network_calls=len(attempts))
        result = evaluate_notice(run)
        self.assertEqual(result['correct'], 8, [r for r in result['rows'] if not r['correct']])


if __name__ == '__main__':
    unittest.main()
