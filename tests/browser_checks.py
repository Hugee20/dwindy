"""Run browser tests and public-API UI smoke with a local Chromium executable.

--config selects an explicit real GGUF smoke; otherwise uses a fake backend.
Nothing is downloaded. No baseline evaluation is run or modified.
"""
import argparse
import base64
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit
from unittest.mock import patch

from dwindy.api import create_app
from dwindy.config import Config, load_config
from dwindy.server import ApiConfig
from browser_driver import launch_browser
from test_api_http import live_server
from test_terminal import FakeBackend

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def static_server(*, web_only=False):
    root = ROOT / 'web' if web_only else ROOT
    class Files(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
        def translate_path(self, path):
            target = (root / unquote(urlsplit(path).path).lstrip("/")).resolve()
            allowed = (root,) if web_only else (ROOT / 'web', ROOT / 'assets')
            if not any(target.is_relative_to(folder) for folder in allowed):
                return str(ROOT / "web" / "not-found")
            return str(target)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Files)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown(); server.server_close(); thread.join()


def submit(browser, message):
    browser.evaluate("chat.$('textarea').value = " + json.dumps(message) + "; chat.$('form').requestSubmit()")


def completed(browser):
    browser.wait("chat.$('.status').textContent.startsWith('Complete') || !chat.$('.error').hidden", timeout=180)
    error = browser.evaluate("chat.$('.error').hidden ? null : chat.$('.error').textContent")
    if error: raise AssertionError(error)
    return browser.evaluate("chat.$('.assistant:last-child .content').textContent")


def standalone_connection_check(browser, static):
    """Exercise the real standalone form on a separate allowed, authenticated origin."""
    token = "standalone-regression-token-0123456789"
    with patch.dict(os.environ, {"DWINDY_API_TOKEN": token}):
        app = create_app(Config(Path("unused.gguf"), max_tokens=5),
            ApiConfig(allowed_origins=(static,)), backend=FakeBackend(limit=10000))
    browser.call("Page.enable")
    script = browser.call("Page.addScriptToEvaluateOnNewDocument", source="""
        globalThis.connectionRequests = [];
        const originalFetch = globalThis.fetch.bind(globalThis);
        globalThis.fetch = (url, options = {}) => {
            connectionRequests.push({url: String(url), method: options.method || 'GET',
                authorization: options.headers?.Authorization || null, body: options.body || null});
            if (String(url).startsWith('http://127.0.0.1:8000/v1/'))
                return Promise.resolve(new Response('{}', {status: 404}));
            return originalFetch(url, options);
        };
    """)["identifier"]
    try:
        with live_server(app) as (client, server, thread):
            api = str(client.base_url).rstrip("/")
            assert api != static
            browser.navigate(static + "/web/index.html")
            browser.wait("!!document.querySelector('dwindy-chat')?.shadowRoot?.querySelector('link')?.sheet")
            browser.evaluate("globalThis.chat = document.querySelector('dwindy-chat')")
            browser.wait("!chat.$('.error').hidden")  # Controlled unavailable default API.
            assert browser.evaluate("document.querySelector('#api-base').value") == 'http://127.0.0.1:8000'
            assert browser.evaluate("connectionRequests.every(c => c.url.startsWith('http://127.0.0.1:8000/v1/'))")

            def connect(value):
                browser.evaluate("connectionRequests.length = 0; document.querySelector('#api-base').value = " +
                    json.dumps(api) + "; document.querySelector('#api-token').value = " + json.dumps(value) +
                    "; document.querySelector('#connection-status').textContent = ''; document.querySelector('#connection-form').requestSubmit()")
                browser.wait("!document.querySelector('#connection-form button').disabled && !!document.querySelector('#connection-status').textContent")
                return browser.evaluate("document.querySelector('#connection-status').textContent")

            status = connect(token)
            calls = browser.evaluate("connectionRequests")
            assert status.startswith("Connection updated."), {"status": status, "requests": calls}
            assert calls and all(c['url'].startswith(api + '/v1/') and
                c['authorization'] == 'Bearer ' + token for c in calls), calls
            assert browser.evaluate("document.querySelector('#api-token').value") == ''
            submit(browser, 'Fresh connection')
            assert completed(browser) == 'ok'
            assert browser.evaluate("JSON.parse(connectionRequests.find(c => c.method === 'POST').body).conversation_id || null") is None
            first_id = next(iter(app.state.dwindy.conversations))

            assert not connect('wrong-token').startswith('Connection updated.')
            assert first_id in app.state.dwindy.conversations
            calls = browser.evaluate('connectionRequests')
            assert calls and all(c['authorization'] == 'Bearer wrong-token' for c in calls)
            assert not any(c['method'] == 'DELETE' for c in calls)
            assert connect(token).startswith('Connection updated.')
            submit(browser, 'New authenticated turn')
            assert completed(browser) == 'ok'
            assert len(app.state.dwindy.conversations) == 2
            assert connect(token).startswith('Connection updated.')
            assert len(app.state.dwindy.conversations) == 1  # Same-settings ephemeral reset.
            return {"static_origin": static, "api_origin": api, "form_connection": True,
                "new_destination_and_token_only": True, "wrong_token_rejected": True,
                "fresh_chat": True, "same_connection_reset": True}
    finally:
        browser.call("Page.removeScriptToEvaluateOnNewDocument", identifier=script)


def standalone_bundle_check(browser):
    """The web/ directory alone contains its images and selects the real API port."""
    script = browser.call('Page.addScriptToEvaluateOnNewDocument', source="""
        globalThis.bundleRequests = [];
        globalThis.fetch = (url) => {
            bundleRequests.push(String(url));
            return Promise.resolve(new Response('{}', {status: 404}));
        };
    """)['identifier']
    try:
        with static_server(web_only=True) as static:
            browser.navigate(static + '/index.html')
            browser.wait("!!document.querySelector('dwindy-chat')?.shadowRoot?.querySelector('link')?.sheet")
            browser.wait("[...document.images, ...document.querySelector('dwindy-chat').shadowRoot.querySelectorAll('img')].every(img => img.complete && img.naturalWidth > 0)")
            assert browser.evaluate("document.querySelector('#api-base').value") == 'http://127.0.0.1:8000'
            assert browser.evaluate("bundleRequests.length > 0 && bundleRequests.every(url => url.startsWith('http://127.0.0.1:8000/v1/'))")
            return {'web_directory_only': True, 'all_images_loaded': True, 'default_api_port': 8000}
    finally:
        browser.call('Page.removeScriptToEvaluateOnNewDocument', identifier=script)


def run(args):
    with static_server() as static, launch_browser(args.browser) as browser:
        version = browser.call("Browser.getVersion")["product"]
        browser.navigate(static + "/web/tests/index.html")
        browser.wait("Array.isArray(globalThis.testResults)", timeout=60)
        results = browser.evaluate("globalThis.testResults")
        failures = [item for item in results if not item["pass"]]
        print(json.dumps({"browser": version, "browser_tests": len(results), "failures": failures}), flush=True)
        assert not failures
        print(json.dumps({"standalone_cross_origin_connection": standalone_connection_check(browser, static)}), flush=True)
        print(json.dumps({'standalone_bundle': standalone_bundle_check(browser)}), flush=True)
        model = load_config(args.config) if args.config else Config(Path("unused.gguf"), max_tokens=5)
        backend = None if args.config else FakeBackend(limit=10000)
        app = create_app(model, ApiConfig(allowed_origins=(static,)), backend=backend, chat_root=ROOT)
        with live_server(app, startup_timeout=120) as (client, server, thread):
            api = str(client.base_url).rstrip("/")
            token = os.environ.get("DWINDY_API_TOKEN", "")
            if token: client.headers["Authorization"] = "Bearer " + token
            browser.navigate(api + "/chat/")
            browser.wait("!!document.querySelector('dwindy-chat')?.shadowRoot?.querySelector('link')?.sheet")
            browser.evaluate("globalThis.chat = document.querySelector('dwindy-chat')")
            if token: browser.evaluate("chat.bearerToken = " + json.dumps(token))
            submit(browser, "Remember the code word CEDAR. Reply only OK.")
            first = completed(browser)
            submit(browser, "What is the code word? Reply with just that word.")
            recall = completed(browser)
            if args.config: assert "CEDAR" in recall
            assert browser.evaluate("chat.$('.messages').children.length") == 4
            browser.evaluate("chat.resetConversation()")
            assert not app.state.dwindy.conversations
            same_origin = {"first": first, "recall": recall, "deletion": True}
            browser.evaluate("document.body.style.zoom = '2'")
            assert browser.evaluate("document.documentElement.scrollWidth <= innerWidth")

            # Copied/host-served widget on a different origin, using unchanged M3 CORS.
            browser.navigate(static + "/web/examples/embedded.html")
            browser.wait("!!document.querySelector('dwindy-chat')?.shadowRoot?.querySelector('link')?.sheet")
            browser.evaluate("globalThis.chat = document.querySelector('dwindy-chat'); chat.setAttribute('api-base', " + json.dumps(api) + ")")
            if token: browser.evaluate("chat.bearerToken = " + json.dumps(token))
            browser.evaluate("chat.$('.launcher').click()")
            browser.wait("chat.$('dialog').open")
            assert browser.evaluate("chat.shadowRoot.activeElement === chat.$('textarea')")
            browser.key("Tab")
            assert browser.evaluate("chat.shadowRoot.activeElement === chat.$('.send')")
            browser.key("Tab")
            # Chromium permits its browser chrome between the last and first control;
            # the host page's interactive elements must remain outside the tab order.
            if browser.evaluate("document.activeElement === document.body"):
                browser.key("Tab")
            assert browser.evaluate("chat.shadowRoot.activeElement === chat.$('.reset')")
            browser.key("Escape")
            browser.wait("chat.shadowRoot.activeElement === chat.$('.launcher')")
            browser.evaluate("chat.$('.launcher').click()")
            browser.wait("chat.$('dialog').open")
            submit(browser, "Reply only HELLO.")
            embedded_answer = completed(browser)
            assert browser.evaluate("getComputedStyle(chat.$('.send')).backgroundColor") != "rgb(37, 55, 131)"
            browser.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
            browser.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
            assert browser.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
            assert browser.evaluate("chat.$('dialog').getBoundingClientRect().width <= innerWidth")
            assert browser.evaluate("chat.$('.panel').getBoundingClientRect().height <= innerHeight")
            ax = browser.call("Accessibility.getFullAXTree")
            assert any(n.get("role", {}).get("value") == "dialog" for n in ax["nodes"])
            if args.screenshot:
                Path(args.screenshot).write_bytes(base64.b64decode(browser.call("Page.captureScreenshot", format="png")["data"]))
            browser.evaluate("chat.resetConversation()")

            if args.config:
                submit(browser, "List the integers from 1 to 100, one per line.")
                browser.wait("chat.$('.assistant:last-child .content').textContent.length > 0", timeout=180)
                assert browser.evaluate("chat.$('.header-avatar').src.endsWith('dwindy-working.png')")
                browser.evaluate("chat.$('.send').click()")
                browser.wait("chat.$('.send').textContent === 'Send'")
                assert browser.evaluate("chat.$('.send').disabled")
                # Wait for cooperative backend cleanup, not an arbitrary fixed sleep.
                from test_api_http import wait_for
                wait_for(lambda: not client.get("/v1/health").json()["busy"], timeout=120)
                browser.evaluate("chat.resetConversation()")
                assert not app.state.dwindy.conversations
                submit(browser, "Reply only FRESH.")
                fresh = completed(browser)
                browser.evaluate("chat.resetConversation()")
            else: fresh = None
            with static_server() as denied_origin:
                browser.navigate(denied_origin + "/web/examples/embedded.html")
                blocked = browser.evaluate("(async () => {try {await fetch(" + json.dumps(api + '/v1/health') + "); return false;} catch {return true;}})()")
                assert blocked
                assert client.get('/v1/health', headers={'Origin': denied_origin}).status_code == 403
            print(json.dumps({"same_origin": same_origin, "cross_origin_answer": embedded_answer,
                "unapproved_origin_blocked": True,
                "standalone_200_percent_css_zoom": True,
                "keyboard_focus": True, "style_isolation": True, "mobile_390px": True,
                "reduced_motion": True, "accessibility_tree_dialog": True,
                "real_model_cancel_reset_recovery": fresh}), flush=True)
        assert not app.state.dwindy.conversations
        if args.config: assert app.state.dwindy.backend._model is None
        print("Server/model cleanup passed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", required=True, type=Path, help="Installed Chrome/Edge executable")
    parser.add_argument("--config", help="Optional explicit real-model configuration")
    parser.add_argument("--screenshot", help="Optional new screenshot path outside version control")
    run(parser.parse_args())
