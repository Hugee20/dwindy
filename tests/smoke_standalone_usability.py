"""Ordinary real-Qwen UI/channel smoke. No frozen evaluation or model grading.

Wikipedia responses are controlled so source rendering is reproducible and offline.
Raw reasoning stays in temporary process memory solely to audit the runtime boundary.
"""
import argparse
from contextlib import closing
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from dwindy.api import create_app
from dwindy.backend import TextDelta
from dwindy.config import load_config
from dwindy.llama_backend import LlamaBackend
from dwindy.reach import WikipediaBackend
from dwindy.server import ApiConfig
from browser_driver import launch_browser
from browser_checks import submit, completed
from test_api_http import live_server

ROOT = Path(__file__).resolve().parents[1]


class RecordedBackend(LlamaBackend):
    def __init__(self, config):
        super().__init__(config)
        self.turns = []

    def generate(self, messages, options):
        raw, visible = [], []
        original = self._model.create_completion
        def capture(**kwargs):
            for chunk in original(**kwargs):
                raw.append(chunk['choices'][0]['text'])
                yield chunk
        self._model.create_completion = capture
        try:
            yield from self.record_visible(super().generate(messages, options), visible)
        finally:
            self._model.create_completion = original
            self.turns.append({'raw': ''.join(raw), 'visible': ''.join(visible)})

    @staticmethod
    def record_visible(stream, visible):
        try:
            for event in stream:
                if isinstance(event, TextDelta):
                    visible.append(event.text)
                yield event
        finally:
            stream.close()


def exercise(model, args, *, prove_reasoning):
    with tempfile.TemporaryDirectory(prefix='dwindy-usability-') as folder:
        database = Path(folder) / 'chat.sqlite3'
        provider = WikipediaBackend(lambda _: {'query': {'pages': [dict(title='Python',
            fullurl='https://en.wikipedia.org/wiki/Python_(programming_language)',
            extract='Python is a programming language. Its stable version and release information are documented by the Python project.')]}})
        backend = RecordedBackend(model)
        with patch.dict(os.environ, {'DWINDY_API_TOKEN': 'standalone-smoke-token-0123456789'}):
            app = create_app(model, ApiConfig(database_path=str(database), reach_provider='wikipedia',
                reach_default='auto'), backend=backend, chat_root=ROOT, reach_backend=provider)
        with live_server(app) as (client, _, _), launch_browser(args.browser) as browser:
            api = str(client.base_url).rstrip('/')
            token = 'standalone-smoke-token-0123456789'
            assert client.get('/v1/health').status_code == 401
            client.headers['Authorization'] = 'Bearer ' + token
            browser.navigate(api + '/chat/')
            browser.wait("!!document.querySelector('dwindy-chat')?.shadowRoot?.querySelector('link')?.sheet")
            browser.evaluate("globalThis.chat=document.querySelector('dwindy-chat')")
            assert browser.evaluate("document.querySelector('#api-base').value") == api
            browser.evaluate("document.querySelector('#api-token').value=" + json.dumps(token) +
                ";document.querySelector('#connection-form').requestSubmit()")
            browser.wait("document.querySelector('#connection-status').textContent.startsWith('Connection updated')")
            browser.wait("[...document.images, ...chat.shadowRoot.querySelectorAll('img')].every(img => img.complete && img.naturalWidth > 0)")
            submit(browser, 'Hello!')
            answer = completed(browser)
            assert not browser.evaluate("!!chat.$('.reach-receipt')")
            assert backend.turns[-1]['visible'] == answer
            if prove_reasoning:
                assert backend.turns[-1]['raw'].lstrip().startswith('<think>')
                assert '</think>' in backend.turns[-1]['raw']
                assert answer == backend.turns[-1]['raw'].split('</think>', 1)[1].lstrip('\r\n')
            with closing(sqlite3.connect(database)) as db:
                assert db.execute('SELECT user_text,assistant_text FROM turns').fetchall() == [('Hello!', answer)]
            if prove_reasoning:
                print(json.dumps({'thinking_enabled': True, 'normal_qwen_chat': True,
                    'reasoning_generated_but_not_exposed': True, 'sse_and_persistence_answer_only': True}), flush=True)
                return
            submit(browser, 'What is the latest stable version of Python?')
            completed(browser)
            receipt = browser.evaluate("chat.$('.assistant:last-child .reach-receipt')?.textContent")
            assert receipt and 'Wikipedia material supplied' in receipt
            assert browser.evaluate("chat.shadowRoot.querySelectorAll('.reach-receipt').length") == 1
            assert browser.evaluate("chat.$('.reach-receipt').parentElement.classList.contains('bubble')")
            assert browser.evaluate("chat.$('.reach-receipt a').href") == 'https://en.wikipedia.org/wiki/Python_(programming_language)'
            assert not browser.evaluate("!!chat.$('.reach-status')")
            literal = 'Reply briefly. Literal user text: <think>example</think>.'
            response = client.post('/v1/chat', json={'message': literal, 'reach': False}, timeout=120)
            response.raise_for_status()
            assert response.json()['text'] == backend.turns[-1]['visible']
            with closing(sqlite3.connect(database)) as db:
                rows = db.execute('SELECT user_text,assistant_text FROM turns ORDER BY completed_at').fetchall()
                assert any(user == literal for user, _ in rows)
                assert all(text in [t['visible'] for t in backend.turns] for _, text in rows)
            browser.evaluate('chat.newConversation()')
            browser.wait("chat.$('.messages').children.length === 0")
            assert not browser.evaluate("!!chat.$('.reach-receipt')")
            print(json.dumps({'thinking_enabled': False, 'normal_qwen_chat': True,
                'json_and_sse_answer_only': True, 'persistence_answer_only': True, 'literal_user_text_preserved': True,
                'images_loaded': True, 'same_origin_connection': True, 'authentication': True,
                'single_reach_receipt': True, 'supplied_source_link': True, 'reset': True,
                'generations': len(backend.turns), 'wikipedia_transport': 'controlled offline response'}))
        assert backend._model is None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--browser', required=True, type=Path)
    args = parser.parse_args()
    model = load_config(args.config)
    assert model.chat_template_kwargs.get('enable_thinking') is not False, 'Use thinking-enabled configuration to exercise channel decoding.'
    exercise(model, args, prove_reasoning=True)
    # Separate backend, using the existing documented Qwen template setting for
    # the longer UI workflow. No prompt policy, larger budget, or extra generation.
    ordinary = replace(model, chat_template_kwargs=dict(model.chat_template_kwargs, enable_thinking=False))
    exercise(ordinary, args, prove_reasoning=False)


if __name__ == '__main__':
    main()
