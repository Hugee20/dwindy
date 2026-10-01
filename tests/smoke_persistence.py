"""Synthetic process-restart smoke, independent of the frozen M1 evaluation.

Uses an isolated temporary database and unchanged user-supplied model config.
Optional --browser verifies manual browser resume through the public API.
"""
import argparse
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def model_rss(process):
    # Windows venv launchers may be a tiny parent of the actual interpreter.
    import psutil
    parent = psutil.Process(process.pid)
    return max(p.memory_info().rss for p in [parent, *parent.children(recursive=True)])


def serve(args):
    import uvicorn
    from dwindy.api import create_app
    from dwindy.config import load_config
    from dwindy.server import ApiConfig
    app = create_app(load_config(args.config), ApiConfig(port=args.port, database_path=args.database,
                     retrieval_index_path=args.retrieval_index), chat_root=ROOT)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port,
        loop="asyncio", http="h11", ws="none", proxy_headers=False, access_log=False,
        log_level="error", timeout_graceful_shutdown=1))
    def stop():
        # Do not block in stdin: native runtime initialization can flush C stdio.
        while not Path(args.stop_file).exists():
            time.sleep(.05)
        server.should_exit = True
    threading.Thread(target=stop, daemon=True).start()
    server.run()
    assert app.state.dwindy.backend._model is None
    if args.database:
        assert app.state.dwindy.store.connection is None
    if args.retrieval_index:
        assert app.state.dwindy.index.connection is None


@contextmanager
def server(config, database, folder, retrieval_index=None):
    import httpx
    with closing(socket.socket()) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    stop_file = Path(folder) / (str(port) + ".stop")
    command = [sys.executable, str(Path(__file__).resolve()), "--serve", "--config", str(config), "--port", str(port), "--stop-file", str(stop_file)]
    if database:
        command += ["--database", str(database)]
    if retrieval_index:
        command += ["--retrieval-index", str(retrieval_index)]
    with open(Path(folder) / "server.log", "w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        headers = {}
        if os.environ.get("DWINDY_API_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["DWINDY_API_TOKEN"]
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers=headers, timeout=180, trust_env=False) as client:
                deadline = time.monotonic() + 120
                last = "not attempted"
                while True:
                    if process.poll() is not None:
                        raise AssertionError("Server exited; inspect temporary server log")
                    try:
                        health = client.get("/v1/health", timeout=1)
                        last = f"{health.status_code}: {health.text}"
                        if health.status_code == 200:
                            break
                    except httpx.HTTPError as exc:
                        last = str(exc)
                    if time.monotonic() >= deadline:
                        log.flush()
                        raise AssertionError("Server startup timed out: " + last + "\n" +
                                             (Path(folder) / "server.log").read_text(encoding="utf-8")[-3000:])
                    time.sleep(.1)
                yield client, process
        finally:
            if process.poll() is None:
                stop_file.touch()
                try:
                    process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise AssertionError("Clean shutdown timed out")
            if process.returncode != 0:
                log.flush()
                raise AssertionError("Server/cleanup failed: " + (Path(folder) / "server.log").read_text(encoding="utf-8")[-3000:])


def run(args):
    config = Path(args.config).resolve()
    results = {}
    with tempfile.TemporaryDirectory(prefix="dwindy-persistence-smoke-") as folder:
        database = Path(folder) / "conversation.db"
        print("Starting persistent server process...", flush=True)
        with server(config, database, folder) as (client, process):
            assert client.get("/v1/health").json()["persistence_enabled"]
            first = client.post("/v1/chat", json={"message": "Remember the code word CEDAR. Reply only OK.", "stream": True})
            first.raise_for_status()
            events = [line[7:] for line in first.text.splitlines() if line.startswith("event: ")]
            assert events[0] == "started" and events[-1] == "completed" and "delta" in events
            payloads = [json.loads(line[6:]) for line in first.text.splitlines() if line.startswith("data: ")]
            key = payloads[0]["conversation_id"]
            results["first_text"] = "".join(p.get("text", "") for p in payloads)
            results["first_pid"] = process.pid
            try:
                import psutil
                results["persistent_model_process_rss_bytes_after_turn"] = model_rss(process)
            except ImportError:
                pass
        with closing(sqlite3.connect(database)) as db:
            before = db.execute("SELECT user_text,assistant_text FROM turns").fetchall()
            assert len(before) == 1
        renamed = database.with_suffix(".closed")
        database.rename(renamed)
        renamed.rename(database)
        results["database_bytes_after_one_turn"] = database.stat().st_size
        with server(config, database, folder) as (client, process):
            assert process.pid != results["first_pid"]
            if args.browser:
                from browser_driver import launch_browser
                from browser_checks import submit, completed
                with launch_browser(args.browser) as browser:
                    results["browser"] = browser.call("Browser.getVersion")["product"]
                    browser.navigate(str(client.base_url).rstrip("/") + "/chat/")
                    browser.wait("!!document.querySelector('dwindy-chat')?.shadowRoot?.querySelector('link')?.sheet")
                    browser.evaluate("globalThis.chat = document.querySelector('dwindy-chat')")
                    if os.environ.get("DWINDY_API_TOKEN"):
                        browser.evaluate("chat.bearerToken = " + json.dumps(os.environ["DWINDY_API_TOKEN"]))
                        browser.evaluate("chat.newConversation()")
                    browser.wait("!chat.$('.persistence').hidden")
                    browser.evaluate("chat.resumeConversation(" + json.dumps(key) + ")")
                    submit(browser, "What is the code word? Reply with just that word.")
                    results["restored_recall"] = completed(browser)
                    browser.evaluate("chat.newConversation()")
                    assert browser.evaluate("chat.$('.conversation-id').value") == ""
            else:
                reply = client.post("/v1/chat", json={"conversation_id": key, "message": "What is the code word? Reply with just that word."})
                reply.raise_for_status()
                results["restored_recall"] = reply.json()["text"]
            assert "CEDAR" in results["restored_recall"]
            with closing(sqlite3.connect(database)) as db:
                rows = db.execute("SELECT user_text,assistant_text FROM turns ORDER BY turn_number").fetchall()
                assert rows[:1] == before and len(rows) == 2
            assert client.delete("/v1/conversations/" + key).status_code == 204
        with server(config, None, folder) as (client, process):
            assert not client.get("/v1/health").json()["persistence_enabled"]
            assert client.post("/v1/chat", json={"message": "gone", "conversation_id": key}).status_code == 404
            reply = client.post("/v1/chat", json={"message": "Reply only HELLO."})
            reply.raise_for_status()
            ephemeral_key = reply.json()["conversation_id"]
            results["ephemeral_reply"] = reply.json()["text"]
            try:
                import psutil
                results["ephemeral_model_process_rss_bytes_after_turn"] = model_rss(process)
            except ImportError:
                pass
        with server(config, database, folder) as (client, process):
            for absent in (key, ephemeral_key):
                assert client.post("/v1/chat", json={"message": "gone", "conversation_id": absent}).status_code == 404
        results.update(restart_restoration=True, deletion_survives_restart=True, ephemeral_restart_forgets=True,
                       windows_rename_after_close=True, clean_model_and_database_shutdown=True)
    results["temporary_directory_removed"] = True
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--database", help=argparse.SUPPRESS)
    parser.add_argument("--retrieval-index", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--stop-file", help=argparse.SUPPRESS)
    args = parser.parse_args()
    serve(args) if args.serve else run(args)
