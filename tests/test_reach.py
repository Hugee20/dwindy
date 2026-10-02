from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ssl
import sys
import threading
import time
import unittest
import unittest.mock
from pathlib import Path

from reach_support import ReplayTransport, combined_body, no_network
from test_terminal import FakeBackend
from dwindy import reach
from dwindy.backend import GenerationOptions, Message
from dwindy.core import DwindyCore
from dwindy.evidence import GUIDANCE, WEB_GUIDANCE

sys.path.insert(0, str(Path(__file__).parent))
from reach.evaluate import CUE_TABLE_CAP, REACH_BOUNDS, evaluate_contract, evaluate_privacy

NOW = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)


@contextmanager
def provider(spec):
    """A loopback HTTP server answering every request with one frozen contract response."""
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def do_GET(self):
            hits.append(self.path)
            if spec.get('delay_seconds'):
                time.sleep(min(spec['delay_seconds'], 8))
            body = (json.dumps(spec['body_json']).encode() if 'body_json' in spec else
                    b'x' * spec['body_bytes'] if 'body_bytes' in spec else spec.get('body_text', '').encode())
            try:
                self.send_response(spec['status'])
                self.send_header('Content-Type', spec['content_type'])
                if spec.get('location'):
                    self.send_header('Location', spec['location'])
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                pass  # The client stopped reading, as intended for oversized bodies.
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f'127.0.0.1:{server.server_port}', hits
    finally:
        server.shutdown(); server.server_close()


def render(results):
    backend = FakeBackend(limit=20000)
    evidence = reach.Evidence(reach.passages(results, ''), 6000, 'plain', origin='web', framing='framing')
    list(DwindyCore(backend, options=GenerationOptions(max_tokens=5)).chat('q', evidence=evidence))
    return '\n'.join(m.content for m in backend.requests[-1])


def contract_run(row):
    spec, observed = row['response'], {}
    context = reach.tls_context()
    observed['verification_disabled'] = not (context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname)
    with provider(spec) as (address, hits), no_network(allow_loopback=True) as external:
        stats, start = {}, time.monotonic()
        url = (f'https://{address}/w/api.php' if spec.get('tls_error') else f'http://{address}/w/api.php')
        backend = reach.WikipediaBackend(transport=lambda _: reach.fetch(url, context=context, stats=stats, _allow_http=True))
        try:
            results = backend.search('latest stable version python')
            observed.update(outcome='results' if results else 'no_results', results=len(results),
                            urls=[r.url for r in results], texts=[r.text for r in results])
            if results:
                observed['model_input'] = render(results)
        except reach.ReachError as error:
            observed.update(outcome='failure', reason=error.code)
        observed['elapsed_seconds'] = time.monotonic() - start
        observed['bytes_read'] = stats.get('bytes_read', 0)
        observed['followed_redirect'] = len(hits) > 1 or bool(external)
    return observed


class ReachTests(unittest.TestCase):
    def setUp(self):
        # Reach was not adopted in M10; these tests keep verifying the dormant, frozen contract.
        self.enterContext(unittest.mock.patch.object(reach, 'REACH_ADOPTED', True))

    def test_frozen_bounds_and_cue_cap(self):
        self.assertLessEqual(reach.cue_count(), CUE_TABLE_CAP)
        self.assertEqual(reach.BOUNDS, REACH_BOUNDS)
        self.assertEqual(reach.PROVIDERS, ('wikipedia',))
        rubric = (Path(__file__).parent/'reach'/'rubric.md').read_text(encoding='utf-8')
        self.assertIn(reach.HONESTY_NOTICE, ' '.join(rubric.replace('> ', '').split()))
        self.assertIn(reach.RESULTS_FRAMING.split('{time}')[1].strip(), ' '.join(rubric.replace('> ', '').split()))

    def test_frozen_privacy_contract(self):
        def run(case):
            context = case['context']
            query, _ = reach.minimize(case['message'], host_texts=[i['text'] for i in context['host_context']],
                                      project_name=context['project_name'])
            return dict(sent=query is not None, query=query)
        result = evaluate_privacy(run)
        self.assertEqual(result['correct'], 20, [r for r in result['rows'] if not r['correct']])

    def test_frozen_provider_contract(self):
        result = evaluate_contract(contract_run)
        self.assertEqual(result['correct'], 14, [r for r in result['rows'] if not r['correct']])

    def test_off_and_unpermitted_paths_never_touch_the_network(self):
        with no_network() as attempts:
            for mode in ('off', 'on', 'auto'):
                decision, evidence, notice = reach.decide('What is the latest version of Python?', mode)
                self.assertEqual((decision.used, decision.reason, evidence), (False, 'reach_disabled', None))
                self.assertEqual(notice, reach.HONESTY_NOTICE)
            self.assertEqual(reach.decide('What is photosynthesis?', 'off'), (None, None, None))
            replay = ReplayTransport(combined_body('latest_python'))
            backend = reach.WikipediaBackend(transport=replay)
            self.assertFalse(reach.decide('What is the latest version of Python?', 'off', backend=backend)[0].used)
            self.assertFalse(reach.decide('What is the latest release of Lantern Desk?', 'on', backend=backend,
                                          project_name='Lantern Desk')[0].used)
            self.assertFalse(reach.decide("What's the latest on maria@example.com?", 'auto', backend=backend)[0].used)
            self.assertEqual(replay.urls, [])
        self.assertEqual(attempts, [])

    def test_used_reach_is_transparent_bounded_web_evidence(self):
        replay = ReplayTransport(combined_body('android_version'))
        decision, evidence, notice = reach.decide('What is the latest version of Android?', 'auto',
                                                  backend=reach.WikipediaBackend(transport=replay), now=NOW)
        self.assertTrue(decision.used)
        self.assertIsNone(notice)
        self.assertEqual(replay.sent_queries(), [decision.query])
        self.assertEqual(decision.metadata()['provider'], 'wikipedia')
        self.assertTrue(all(s['url'].startswith('https://en.wikipedia.org/wiki/') for s in decision.metadata()['sources']))
        self.assertLessEqual(len(evidence.passages), 3)
        self.assertTrue(any('Android 17' in p.text for p in evidence.passages))
        backend = FakeBackend(limit=20000)
        core = DwindyCore(backend, options=GenerationOptions(max_tokens=5))
        list(core.chat('What is the latest version of Android?', evidence=reach.Evidence(
            evidence.passages, 6000, 'plain', origin='web', framing=evidence.framing)))
        system, user = backend.requests[-1][0].content, backend.requests[-1][-1].content
        self.assertIn(WEB_GUIDANCE, system)
        self.assertNotIn(GUIDANCE, system)
        self.assertTrue(user.startswith('External search results from Wikipedia, retrieved at 2026-10-02'))
        self.assertEqual(core.snapshot()[0], Message('user', 'What is the latest version of Android?'))

    def test_failures_fall_back_to_offline_honesty(self):
        for error in ('reach_unavailable', 'reach_timeout'):
            decision, evidence, notice = reach.decide('Who is the current CEO of Microsoft?', 'auto',
                                                      backend=reach.WikipediaBackend(transport=ReplayTransport(error=error)))
            self.assertEqual((decision.used, decision.reason, evidence, notice), (False, error, None, reach.HONESTY_NOTICE))
            self.assertTrue(decision.query)

    def test_notice_is_transient_and_absent_otherwise(self):
        backend = FakeBackend(limit=20000)
        core = DwindyCore(backend, options=GenerationOptions(max_tokens=5))
        list(core.chat('Who is the current CEO of Microsoft?', notice=reach.HONESTY_NOTICE))
        self.assertEqual(backend.requests[-1][0], Message('system', reach.HONESTY_NOTICE))
        list(core.chat('What is photosynthesis?'))
        self.assertNotIn(reach.HONESTY_NOTICE, str(backend.requests[-1]))
        self.assertEqual(reach.decide('What is photosynthesis?', 'off'), (None, None, None))  # Byte-identical turn.
        self.assertEqual(reach.decide('What is photosynthesis?', 'auto')[0].reason, 'reach_disabled')  # Asked, so reported.


if __name__ == '__main__':
    unittest.main()
