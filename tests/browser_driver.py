"""Tiny stdlib-only test driver for an explicitly supplied Chromium executable.

This is test tooling, not a Dwindy runtime dependency or general browser SDK.
It talks to a headless browser's loopback-only DevTools endpoint.
"""
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler


class Browser:
    def __init__(self, url):
        endpoint = urlsplit(url)
        self.socket = socket.create_connection((endpoint.hostname, endpoint.port), timeout=180)
        nonce = base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall((f"GET {endpoint.path} HTTP/1.1\r\nHost: {endpoint.hostname}:{endpoint.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        # Read exactly through headers, leaving any subsequent frame on the socket.
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += self._read(1)
        if b" 101 " not in header.split(b"\r\n")[0]:
            raise RuntimeError("Browser debugging handshake failed")
        self.counter = 0

    def _read(self, count):
        result = b""
        while len(result) < count:
            part = self.socket.recv(count - len(result))
            if not part:
                raise RuntimeError("Browser connection closed")
            result += part
        return result

    def _send(self, payload, opcode=1):
        size = len(payload)
        header = bytes([0x80 | opcode])
        if size < 126:
            header += bytes([0x80 | size])
        elif size < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", size)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", size)
        mask = os.urandom(4)
        self.socket.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _receive(self):
        result = b""
        while True:
            first, second = self._read(2)
            size = second & 127
            if size == 126: size = struct.unpack("!H", self._read(2))[0]
            elif size == 127: size = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if second & 128 else None
            payload = self._read(size)
            if mask: payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            opcode = first & 15
            if opcode == 8: raise RuntimeError("Browser closed debugging session")
            if opcode == 9:
                self._send(payload, 10); continue
            if opcode in (0, 1): result += payload
            if first & 128 and opcode in (0, 1): return json.loads(result)

    def call(self, method, **params):
        self.counter += 1
        self._send(json.dumps({"id": self.counter, "method": method, "params": params}).encode())
        while True:
            message = self._receive()
            if message.get("id") == self.counter:
                if "error" in message: raise RuntimeError(message["error"])
                return message.get("result", {})

    def evaluate(self, expression):
        response = self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in response:
            raise AssertionError(response["exceptionDetails"])
        return response.get("result", {}).get("value")

    def wait(self, expression, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.evaluate(expression): return
            time.sleep(0.05)
        raise AssertionError("Timed out: " + expression)

    def navigate(self, url):
        self.call("Page.navigate", url=url)
        self.wait("document.readyState === 'complete'")

    def key(self, key, code=None, modifiers=0):
        values = {"key": key, "code": code or key, "modifiers": modifiers,
                  "windowsVirtualKeyCode": {"Tab": 9, "Escape": 27, "Enter": 13}.get(key, 0)}
        self.call("Input.dispatchKeyEvent", type="keyDown", **values)
        self.call("Input.dispatchKeyEvent", type="keyUp", **values)


@contextmanager
def launch_browser(executable):
    with tempfile.TemporaryDirectory(prefix="dwindy-browser-") as profile:
        process = subprocess.Popen([str(executable), "--headless", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--disable-background-networking", "--remote-debugging-port=0",
            "--remote-debugging-address=127.0.0.1", "--user-data-dir=" + profile, "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        browser = None
        try:
            active = Path(profile) / "DevToolsActivePort"
            deadline = time.monotonic() + 20
            while not active.exists() and time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError("Browser failed to start")
                time.sleep(0.05)
            port = int(active.read_text().splitlines()[0])
            opener = build_opener(ProxyHandler({}))
            with opener.open(f"http://127.0.0.1:{port}/json/list") as response:
                pages = json.load(response)
            browser = Browser(next(p for p in pages if p["type"] == "page")["webSocketDebuggerUrl"])
            yield browser
        finally:
            if browser:
                try: browser.call("Browser.close")
                except (OSError, RuntimeError): pass
                browser.socket.close()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate(); process.wait(timeout=10)
