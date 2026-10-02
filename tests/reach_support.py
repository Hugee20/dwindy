"""Shared M10 test support: recorded-response replay and a guard against any real network use."""
from contextlib import contextmanager
import json
from pathlib import Path
import socket
from unittest.mock import patch
import urllib.parse

RECORDED = Path(__file__).parent/'reach'/'recorded'


def combined_body(name):
    """The backend's single request returns extracts and snippets together; replay both recorded halves."""
    record = json.loads((RECORDED/(name + '.json')).read_text(encoding='utf-8'))
    query = dict(pages=record['extracts']['body']['query']['pages'])
    query['search'] = record['snippets']['body']['query']['search']
    return dict(batchcomplete=True, query=query)


class ReplayTransport:
    """Records every outbound URL; returns a recorded body or raises a configured ReachError."""
    def __init__(self, body=None, error=None):
        self.body, self.error, self.urls = body, error, []

    def __call__(self, url):
        self.urls.append(url)
        if self.error:
            from dwindy.reach import ReachError
            raise ReachError(self.error)
        return self.body

    def sent_queries(self):
        return [urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)['gsrsearch'][0] for u in self.urls]


@contextmanager
def no_network(allow_loopback=False):
    """Any connection attempt outside loopback (or at all) fails the test immediately."""
    attempts = []
    original = socket.socket.connect

    def guarded(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if allow_loopback and host in ('127.0.0.1', '::1', 'localhost'):
            return original(sock, address)
        attempts.append(address)
        raise AssertionError(f'Unexpected network connection to {address!r}')
    with patch.object(socket.socket, 'connect', guarded):
        yield attempts
