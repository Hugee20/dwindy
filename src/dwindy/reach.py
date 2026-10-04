"""Reach: deployment-gated external information for freshness-dependent questions.

Only the current user message may contribute to the outbound query, and only after protected
material is removed. No retries, caching, redirects, page fetching, crawling or model calls.
Provider results are untrusted, transient evidence. Supply receipts come from the actual
Core packet, never model-written provenance or factual verification.
"""
import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import html
import json
import re
import socket
import ssl
import time
import threading
import urllib.error
import urllib.parse
import urllib.request

from .evidence import Evidence, Passage, Source
from .retrieval import STOPWORDS, query_terms, words

# The complete Reach cue table (frozen cap: 25 entries, tests/reach/README.md). A closed list of
# high-certainty phrases; ambiguous requests do not trigger Reach.
CUES = {
    "freshness": ("latest", "newest", "newer", "most recent", "recently", "right now", "this week",
                  "news", "headlines", "exchange rate", "stock price", "current price", "current version",
                  "is current", "who is the current", "who currently"),
    "explicit_search": ("search the web", "search online", "search the internet", "look up online",
                        "look it up online", "can you search for", "check wikipedia"),
}
# "who ... now" is the one structural cue (counted as an entry): a who-question asking about now.
WHO_NOW = "who now"
BOUNDS = dict(timeout_seconds=5.0, max_body_bytes=524288, max_results_supplied=3,
              max_result_chars=1600, max_query_chars=200, max_query_terms=12)
PROVIDERS = ("wikipedia",)
API_URL = "https://en.wikipedia.org/w/api.php"
RESULT_URL_PREFIX = "https://en.wikipedia.org/wiki/"
USER_AGENT = "Dwindy/1.0 (local-first assistant; Wikipedia information)"
# Frozen in tests/reach/rubric.md.
HONESTY_NOTICE = ("This question may depend on current information that could not be verified here. "
                  "If your answer relies on knowledge that may be outdated, say so plainly and do not "
                  "present it as current.")
# Adopted offline notice remains separate from practical Reach's deterministic status.
HONESTY_ADOPTED = True

FRESHNESS_TERMS = frozenset("latest newest newer recent recently current currently now today right week".split())
# A query is usable only with a real subject: freshness words and generic fillers never count (fail closed).
NOT_A_SUBJECT = FRESHNESS_TERMS | frozenset(
    "about on regarding any anything something info information update updates please tell".split())
CREDENTIAL = re.compile(r"\b(?:password|passcode|passphrase|pin|token|secret|api\s*key|key)\b\s*(?:is|was|=|:)?\s*\S+", re.IGNORECASE)
PROTECTED = (
    re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE),                       # URLs, with any tokens in them
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),                                     # emails
    CREDENTIAL,                                                                       # credential words and values
    re.compile(r"\b(?:sk|pk|rk)[-_]\S+|\b(?=\w*\d)(?=\w*[A-Za-z])\w{16,}\b"),        # API-key-shaped tokens
    re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),                                      # IP addresses
    re.compile(r"\+?\d(?:[\s-]?\d){6,}"),                                             # phones, cards, long IDs
)


class ReachError(Exception):
    def __init__(self, code="reach_unavailable"):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class WebResult:
    title: str
    url: str
    text: str


@dataclass(frozen=True)
class ReachDecision:
    state: str
    reason: str
    attempted: bool = False
    provider: str | None = None
    query: str | None = None
    candidates: tuple = field(default=())
    admitted: tuple = field(default=())
    notice: bool = False

    def metadata(self, actual=None):
        """Finalize from Core's actual supplied IDs, never from candidates or model words."""
        selected = {p.source.chunk_id: p for p in self.admitted}
        supplied = []
        if actual and actual.get('status') == 'supplied':
            for source in actual['sources']:
                p = selected.get(source['chunk_id'])
                if p is None or source != p.source.mapping():
                    raise ValueError('Core supply is not an admitted WEB entry')
                supplied.append(p)
        state, reason = self.state, self.reason
        if self.admitted:
            state, reason = ('supplied', 'supplied') if supplied else ('not_supplied', 'budget_exhausted')
        sources = {}
        for p in supplied:
            sources.setdefault(p.source.source_path, dict(provider='wikipedia', title=p.source.name,
                                                         url=p.source.source_path))
        result = dict(state=state, reason=reason, attempted=self.attempted,
                      supplied=bool(supplied), sources=list(sources.values()),
                      admitted_entry_ids=list(selected), supplied_entry_ids=[p.source.chunk_id for p in supplied],
                      candidate_count=len(self.candidates), notice=self.notice)
        if self.provider:
            result['provider'] = self.provider
        if self.attempted:
            result['query'] = self.query
        return result


def _phrase(tokens, phrase):
    target = phrase.split()
    return any(tokens[i:i+len(target)] == target for i in range(len(tokens) - len(target) + 1))


def detect(message):
    """(freshness, explicit_search) for a message; self-contained tasks never trigger."""
    from .context_policy import classify
    if classify(message) == "self_contained":
        return False, False
    tokens = words(message)
    fresh = any(_phrase(tokens, cue) for cue in CUES["freshness"]) or (
        bool(tokens) and tokens[0] == "who" and "now" in tokens)
    return fresh, any(_phrase(tokens, cue) for cue in CUES["explicit_search"])


def project_directed(message, project_name=None):
    from .context_policy import classify
    return classify(message, project_name) == "directed"


def minimize(message, *, host_texts=(), project_name=None):
    """(query, reason). Fail closed: protected material is removed before usefulness is judged."""
    if project_directed(message, project_name):
        return None, "project_directed"
    cleaned = message
    for pattern in PROTECTED:
        cleaned = pattern.sub(" ", cleaned)
    host = {t for text in host_texts for t in words(text) if t not in STOPWORDS}
    terms = [t for t in query_terms(cleaned) if t not in host and len(t) > 1]
    terms = terms[-BOUNDS["max_query_terms"]:]  # Long messages usually end with the question.
    query = " ".join(terms)
    while len(query) > BOUNDS["max_query_chars"]:
        terms = terms[1:]
        query = " ".join(terms)
    if not any(t not in NOT_A_SUBJECT and not t.isdigit() for t in terms):
        return None, "query_unusable"
    return query, None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Redirects are never followed.


def tls_context():
    """OS-native certificate verification; verification is never disabled."""
    try:
        import truststore
    except ImportError as exc:
        raise ImportError("Reach requires the optional dwindy[reach] dependency (truststore).") from exc
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def fetch(url, *, context, timeout=BOUNDS["timeout_seconds"], max_bytes=BOUNDS["max_body_bytes"],
          stats=None, _allow_http=False):
    """One bounded GET. Returns parsed JSON or raises ReachError.
    stats and _allow_http (loopback plain HTTP) exist only for local contract tests."""
    if not (url.startswith("https://") or (_allow_http and url.startswith("http://127.0.0.1:"))):
        raise ReachError()
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200 or not response.headers.get("Content-Type", "").startswith("application/json"):
                raise ReachError()
            body = bytearray()
            while len(body) <= max_bytes:
                if time.monotonic() > deadline:
                    raise ReachError("reach_timeout")
                chunk = response.read(min(65536, max_bytes + 1 - len(body)))
                if not chunk:
                    break
                body += chunk
            if stats is not None:
                stats["bytes_read"] = len(body)
            if len(body) > max_bytes:
                raise ReachError()
        return json.loads(bytes(body).decode("utf-8"))
    except ReachError:
        raise
    except (socket.timeout, TimeoutError):
        raise ReachError("reach_timeout")
    except urllib.error.URLError as exc:
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()  # 429, 5xx and refused redirects: release the connection.
            raise ReachError('http_' + str(exc.code))
        if isinstance(getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
            raise ReachError("reach_timeout")
        raise ReachError()
    except (OSError, ValueError, UnicodeDecodeError, http_client_errors()):
        raise ReachError()


def http_client_errors():
    import http.client
    return http.client.HTTPException


def _clean(text):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", text)).split())


def _exact_subject_title(title, query):
    terms = set(subject_terms(query))
    return bool(terms) and terms == set(subject_terms(title))


def _selected_text(text, query, title=''):
    """Select verbatim paragraph/sentence windows; query overlap is not verification."""
    limit = BOUNDS['max_result_chars']
    wanted = set(words(query)) - STOPWORDS
    # Only an exact subject identity supplies context; qualified titles do not.
    context = set(words(title)) if _exact_subject_title(title, query) else set()
    windows = []
    for paragraph in text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        start = 0
        boundaries = [m.end() for m in re.finditer(r'(?<=[.!?])\s+', paragraph)]
        while len(paragraph) - start > limit:
            end = max((b for b in boundaries if start < b <= start + limit), default=0)
            if not end:
                end = paragraph.rfind(' ', start, start + limit + 1)
            if end <= start:
                end = start + limit
            windows.append(paragraph[start:end].strip())
            start = end
        if paragraph[start:].strip():
            windows.append(paragraph[start:].strip())
    # max() keeps the first window on ties: original paragraph/window ordering.
    return max(windows, key=lambda text: len(wanted & (context | set(words(text)))), default='')


def parse(body, query_text=''):
    """Select bounded text from complete introductions, or snippets when unavailable."""
    if not isinstance(body, dict):
        raise ReachError()
    query = body.get("query")
    if "error" in body:
        raise ReachError("provider_error")
    if query is None:
        return []
    if not isinstance(query, dict):
        raise ReachError()
    pages = query.get("pages") if isinstance(query.get("pages"), list) else []
    search = query.get('search', [])
    if not isinstance(search, list):
        raise ReachError('invalid_response')
    snippets = {s["title"]: _clean(s.get("snippet", "")) for s in search
                if isinstance(s, dict) and isinstance(s.get("title"), str) and isinstance(s.get("snippet", ""), str)}
    results, seen = [], set()
    ordered = sorted((p for p in pages if isinstance(p, dict)), key=lambda p: p.get("index", 99) if isinstance(p.get("index"), int) else 99)
    for page in ordered:
        title, extract, url = page.get("title"), page.get("extract", ""), page.get("fullurl")
        if not isinstance(title, str) or not isinstance(extract, str) or not isinstance(url, str):
            continue
        if not valid_article_url(url):
            continue  # Only validated provider article URLs are ever reported.
        text = _selected_text(extract if extract.strip() else snippets.get(title, ''), query_text, title)
        if text and title not in seen:
            seen.add(title)
            results.append(WebResult(title, url, text))
    for title, snippet in snippets.items():
        if title not in seen and snippet and not pages:
            seen.add(title)
            url = RESULT_URL_PREFIX + urllib.parse.quote(title.replace(" ", "_"))
            results.append(WebResult(title, url, _selected_text(snippet, query_text, title)))
    return results[:BOUNDS["max_results_supplied"]]


def valid_article_url(url):
    if not isinstance(url, str) or any(ord(c) < 32 for c in url):
        return False
    parsed = urllib.parse.urlsplit(url)
    return (parsed.scheme == 'https' and parsed.netloc == 'en.wikipedia.org'
            and parsed.path.startswith('/wiki/') and len(parsed.path) > 6
            and not parsed.query and not parsed.fragment)


class WikipediaBackend:
    """One bounded request. A timed-out transport retains its slot until it exits.

    Python cannot kill an in-flight native DNS/socket call. No additional work is queued
    while that call is running, including after the caller's five-second deadline.
    """
    name = 'wikipedia'

    def __init__(self, transport=None):
        self._context = None if transport else tls_context()
        self._transport = transport or (lambda url: fetch(url, context=self._context))
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='dwindy-reach')
        self._slot = threading.Lock()
        self._closed = False

    def url(self, query):
        return API_URL + '?' + urllib.parse.urlencode(dict(
            action='query', format='json', formatversion='2', generator='search', gsrsearch=query, gsrlimit=3,
            prop='extracts|info', exintro=1, explaintext=1, exlimit=3, inprop='url',
            list='search', srsearch=query, srlimit=3, srprop='snippet'))

    def search(self, query):
        if not self._slot.acquire(blocking=False):
            raise ReachError('transport_busy')
        if self._closed:
            self._slot.release()
            raise ReachError('provider_closed')
        try:
            future = self._executor.submit(self._transport, self.url(query))
        except RuntimeError:
            self._slot.release()
            raise ReachError('provider_closed')
        future.add_done_callback(lambda _: self._slot.release())
        try:
            body = future.result(timeout=BOUNDS['timeout_seconds'])
        except concurrent.futures.TimeoutError:
            raise ReachError('reach_timeout')
        except ReachError:
            raise
        except Exception:
            raise ReachError('reach_unavailable')
        return parse(body, query)

    def close(self):
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)


class UnavailableBackend:
    name = 'wikipedia'
    def search(self, query):
        raise ReachError('tls_unavailable')
    def close(self):
        pass


def passages(results, retrieved):
    out = []
    for index, result in enumerate(results):
        digest = hashlib.sha256(result.url.encode()).hexdigest()[:32]
        out.append(Passage(Source("web_" + digest, hashlib.sha256((result.url + "\n" + result.text + "\n" + str(index)).encode()).hexdigest()[:32], result.title, result.url,
                                  hashlib.sha256(result.text.encode()).hexdigest(), 0, 0, 0, len(result.text), "", "web"),
                           result.text))
    return tuple(out)


# Admission is bounded lexical coverage, not semantic answer verification.
def select_entries(results, query):
    terms = set(subject_terms(query))
    if not terms:
        return ()
    candidates = passages(results, '')
    exact = tuple(p for p in candidates if _exact_subject_title(p.source.name, query))
    admitted = []
    for p in exact or candidates:
        title_terms = subject_terms(p.source.name)
        title_matches = _exact_subject_title(p.source.name, query)
        if terms <= set(title_terms) and not title_matches:
            continue  # Extra informative title words denote a qualified/different subject.
        text_terms = set(words(p.text))
        if terms <= text_terms or (title_matches and title_terms[0] in text_terms):
            admitted.append(p)
    return tuple(admitted)


def subject_terms(query):
    return list(dict.fromkeys(t for t in words(query) if t not in STOPWORDS and t not in NOT_A_SUBJECT
                              and len(t) > 1 and not t.isdigit()))


def local_relevant(decision, evidence):
    """Whether the M8 policy itself judged local evidence relevant (forced retrieval does not)."""
    return (decision is not None and decision.reason in ("relevant_match", "project_directed")
            and evidence is not None and bool(evidence.passages))


def decide(message, mode, *, backend=None, project_name=None, host_texts=(), local_supplied=False,
           local_relevant=False, max_tokens=768, now=None):
    """Acquire/admit only; Core later determines supply. No provenance instructions to Qwen."""
    fresh, explicit = detect(message)
    if backend is None or mode == 'off':
        state, reason = 'disabled', 'reach_disabled' if backend is None else 'reach_off'
        # Preserve the adopted offline freshness notice, not a Reach success policy.
        notice = (HONESTY_NOTICE if fresh and HONESTY_ADOPTED and not local_relevant
                  and not project_directed(message, project_name) else None)
        if backend is None and not fresh and mode == 'off':
            return None, None, None
        return ReachDecision(state, reason, notice=bool(notice)), None, notice
    def skipped(reason):
        return ReachDecision('not_attempted', reason, provider=backend.name), None, None
    if mode == 'auto' and not (fresh or explicit):
        return skipped('not_fresh')
    if project_directed(message, project_name):
        return skipped('project_directed')
    if local_supplied:
        return skipped('local_context')
    query, reason = minimize(message, host_texts=host_texts, project_name=project_name)
    if query is None:
        return skipped(reason)
    try:
        results = backend.search(query)
    except ReachError as exc:
        attempted = exc.code not in ('transport_busy', 'provider_closed', 'tls_unavailable')
        return ReachDecision('unavailable', exc.code, attempted, backend.name, query), None, None
    candidates = tuple(passages(results, ''))
    admitted = select_entries(results, query)
    decision = ReachDecision('not_supplied', 'admitted' if admitted else 'not_useful' if results else 'no_results',
                             True, backend.name, query, candidates, admitted)
    if not admitted:
        return decision, None, None
    moment = (now or datetime.now()).astimezone()
    framing = f'Wikipedia information retrieved at {moment:%Y-%m-%d %H:%M} server-local time.'
    return decision, Evidence(admitted, max_tokens, 'plain', origin='web', framing=framing), None


def cue_count():
    return sum(len(entries) for entries in CUES.values()) + 1  # Plus the structural who-now cue.
