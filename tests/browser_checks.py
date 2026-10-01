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

from dwindy.api import create_app
from dwindy.config import Config, load_config
from dwindy.server import ApiConfig
from browser_driver import launch_browser
from test_api_http import live_server
from test_terminal import FakeBackend

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def static_server():
    class Files(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
        def translate_path(self, path):
            target = (ROOT / unquote(urlsplit(path).path).lstrip("/")).resolve()
            if not any(target.is_relative_to(ROOT / folder) for folder in ("web", "assets")):
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


def run(args):
    with static_server() as static, launch_browser(args.browser) as browser:
        version = browser.call("Browser.getVersion")["product"]
        browser.navigate(static + "/web/tests/index.html")
        browser.wait("Array.isArray(globalThis.testResults)", timeout=60)
        results = browser.evaluate("globalThis.testResults")
        failures = [item for item in results if not item["pass"]]
        print(json.dumps({"browser": version, "browser_tests": len(results), "failures": failures}), flush=True)
        assert not failures
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
