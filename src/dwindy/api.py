"""Small local HTTP adapter. Core and model policy remain transport-independent."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
import hmac
import ipaddress
import json
import secrets
import time
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.exceptions import HTTPException
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse, Response

from .backend import Completion, ContextLimitError, TextDelta
from .core import DwindyCore, TurnStarted
from .config import ConfigError
from .server import ApiConfig
from .persistence import ConversationStore, StorageError
from . import capabilities, reach
from .context_policy import ContextDecision, decide
from .evidence import Evidence, Facts
from .retrieval import RetrievalError, RetrievalIndex, match_query

# Host context contract (frozen in tests/tools/README.md); internal, not configuration.
HOST_CONTEXT_MAX_ITEMS, HOST_CONTEXT_MAX_TOTAL_CHARS, HOST_CONTEXT_BUDGET_TOKENS = 8, 4000, 1024


def error(status, code, message, *, retry=False):
    headers = {"Cache-Control": "no-store"}
    if retry:
        headers["Retry-After"] = "1"
    return JSONResponse({"error": {"code": code, "message": message}}, status, headers=headers)


class HostContextItem(BaseModel):
    """Information the host application already authenticated and authorized. Never an action."""
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("label", "text")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Host context labels and text must not be blank.")
        return value


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str
    conversation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{32}$")
    stream: bool = False
    # true = on, false = off, "auto" = context-selection policy; omitted = server default.
    retrieval: bool | Literal["auto"] | None = None
    host_context: list[HostContextItem] | None = Field(default=None, description=(
        "Bearer-authenticated requests only: 1-8 items of host-supplied information for this turn. "
        "Transient data, never instructions or actions."))
    # Selects Reach behavior only where the deployment configured a provider; never grants it.
    reach: bool | Literal["auto"] | None = None

    @field_validator("retrieval", "reach")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Mode must be true, false or \"auto\" when supplied.")
        return value

    @field_validator("host_context")
    @classmethod
    def host_context_bounds(cls, value):
        if value is None or not 1 <= len(value) <= HOST_CONTEXT_MAX_ITEMS:
            raise ValueError("host_context must contain 1-8 items when supplied.")
        if sum(len(item.text) for item in value) > HOST_CONTEXT_MAX_TOTAL_CHARS:
            raise ValueError("host_context text must total at most 4000 characters.")
        return value

    @field_validator("message")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Message must not be blank.")
        return value


class Usage(BaseModel):
    prompt_tokens: int
    text_tokens: int = Field(description="Retokenized raw response text, not sampled-token count.")


class SourceMetadata(BaseModel):
    document_id: str
    chunk_id: str
    name: str
    source_path: str
    content_hash: str
    line_start: int
    line_end: int
    start: int
    end: int
    heading: str
    source_type: str
    project_id: str | None = None
    snapshot_id: str | None = None


class RetrievalMetadata(BaseModel):
    status: Literal["supplied", "no_match", "budget_exhausted", "not_used", "unavailable"]
    sources: list[SourceMetadata]
    mode: Literal["auto"] | None = Field(default=None, description="Present only for automatic context selection.")
    attempted: bool | None = None
    reason: str | None = Field(default=None, description="Fixed context-selection reason code; not a score.")
    query_normalized: bool | None = None


class RetrievalMatch(SourceMetadata):
    text: str
    score: float


class RetrieveReply(BaseModel):
    matches: list[RetrievalMatch]


class ChatReply(BaseModel):
    conversation_id: str
    text: str
    finish_reason: str
    dropped_turns: int
    usage: Usage
    retrieval: RetrievalMetadata | None = None
    capabilities: list[dict] | None = Field(default=None, description=(
        "Deterministic capabilities and host context used for this turn; present only when used."))
    reach: dict | None = Field(default=None, description=(
        "Deterministic Reach state/reason, attempted query, admission IDs, actual supplied IDs and article sources. "
        "Sources describe information supplied to the model, not answer verification."))


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str

    @field_validator("query")
    @classmethod
    def valid_query(cls, value):
        match_query(value)
        return value


class ProjectSnapshot(BaseModel):
    """Identity of a manually synchronized project index; the project root is never exposed."""
    project_id: str
    name: str
    snapshot_id: str
    indexed_at: str
    freshness: Literal["not_checked"]


class HealthReply(BaseModel):
    status: str
    busy: bool
    persistence_enabled: bool
    retrieval_enabled: bool
    retrieval_default: Literal["auto", "off"] | None = None
    project_snapshot: ProjectSnapshot | None = None
    reach_enabled: bool | None = None
    reach_default: Literal["auto", "off"] | None = None
    reach_provider: str | None = None


ERROR_SCHEMA = {"type": "object", "required": ["error"], "properties": {"error": {
    "type": "object", "required": ["code", "message"],
    "properties": {"code": {"type": "string"}, "message": {"type": "string"}}}}}
ERROR_RESPONSES = {status: {"description": description, "content": {"application/json": {"schema": ERROR_SCHEMA}}}
                   for status, description in ((400, "Malformed JSON or Host"), (401, "Bearer token required"),
                       (403, "Origin or exposure policy denied"), (404, "Unknown or expired conversation"),
                       (409, "Conversation busy"), (413, "Request body too large"), (415, "JSON required"),
                       (422, "Invalid request or context limit"), (500, "Inference failed"),
                       (503, "Backend busy, unavailable, or conversation capacity reached"))}


def origin_tuple(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("Invalid origin")
    return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)


class SecurityMiddleware:
    """Reject untrusted Host/Origin, not merely omit CORS response headers."""

    def __init__(self, app, config, token, public_files=()):
        self.app, self.config, self.token = app, config, token
        self.public_files = frozenset(public_files)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {}
        for key, value in scope["headers"]:
            key = key.lower()
            if key in headers and key in (b"host", b"origin", b"authorization"):
                return await error(400, "invalid_headers", "Duplicate security header.")(scope, receive, send)
            headers[key] = value.decode("latin-1")
        host = headers.get(b"host", "")
        try:
            parsed = urlsplit("//" + host)
            parsed.port  # Validate port syntax as well as the hostname.
            valid_host = (parsed.hostname and parsed.hostname.lower() in
                          {h.lower() for h in self.config.allowed_hosts}
                          and not parsed.username and not parsed.password
                          and not parsed.path and not parsed.query and not parsed.fragment)
        except ValueError:
            valid_host = False
        if not valid_host:
            return await error(400, "invalid_host", "Host is not allowed.")(scope, receive, send)
        local = ipaddress.ip_address(self.config.host).is_loopback
        try:
            local_peer = ipaddress.ip_address(scope.get("client", ("", 0))[0]).is_loopback
        except (ValueError, TypeError):
            local_peer = False
        if local and not local_peer:
            return await error(403, "local_only", "Only loopback clients are allowed.")(scope, receive, send)
        if not local and scope["scheme"] != "https":
            return await error(403, "tls_required", "TLS is required.")(scope, receive, send)
        origin = headers.get(b"origin")
        if origin is not None:
            try:
                valid_origin = (origin_tuple(origin) == origin_tuple(scope["scheme"] + "://" + host)
                                or origin in self.config.allowed_origins)
            except ValueError:
                valid_origin = False
            if not valid_origin:
                return await error(403, "origin_denied", "Origin is not allowed.")(scope, receive, send)

        async def cors_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", []))
                if origin is not None:
                    message["headers"] += [(b"access-control-allow-origin", origin.encode("latin-1")),
                                           (b"vary", b"Origin")]
                message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        if scope["method"] == "OPTIONS" and origin is not None:
            method = headers.get(b"access-control-request-method", "")
            requested = {h.strip().lower() for h in headers.get(b"access-control-request-headers", "").split(",") if h.strip()}
            if method not in ("GET", "POST", "DELETE") or requested - {"authorization", "content-type"}:
                return await error(403, "preflight_denied", "Preflight is not allowed.")(scope, receive, cors_send)
            response = Response(status_code=204, headers={
                "Access-Control-Allow-Methods": "GET, POST, DELETE",
                "Access-Control-Allow-Headers": "Authorization, Content-Type"})
            return await response(scope, receive, cors_send)
        public_asset = scope["method"] in ("GET", "HEAD") and scope["path"] in self.public_files
        if self.token is not None and not public_asset:
            auth = headers.get(b"authorization", "")
            supplied = auth[7:] if auth[:7].lower() == "bearer " else ""
            if not hmac.compare_digest(supplied.encode("utf-8"), self.token.encode("ascii")):
                response = error(401, "unauthorized", "A valid bearer token is required.")
                response.headers["WWW-Authenticate"] = "Bearer"
                return await response(scope, receive, cors_send)
        await self.app(scope, receive, cors_send)


@dataclass
class Conversation:
    core: DwindyCore
    touched: float
    active: bool = False


class ApiState:
    """Event-loop-owned leases; all synchronous model work uses one worker."""

    def __init__(self, config, model_config):
        self.config, self.model_config = config, model_config
        self.backend = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dwindy-model")
        self.conversations = {}
        self.busy = False
        self.ready = False
        self.tasks = set()
        self.store = None
        self.index = None
        # A deliberately configured index means the deployment is an assistant for that material.
        self.default_mode = config.retrieval_default or ("auto" if config.retrieval_index_path else "off")
        self.reach_backend = None  # Set only when the deployment configures a provider.
        self.storage_executor = (ThreadPoolExecutor(max_workers=1, thread_name_prefix="dwindy-storage")
                                 if config.database_path is not None or config.retrieval_index_path is not None else None)
        self.storage_lock = asyncio.Lock()
        self.deleting = set()

    async def storage(self, fn, *args, internal=False):
        # External operations never build an unbounded executor queue. At most
        # the single admitted inference finalizer can wait for a short operation.
        if not internal and self.storage_lock.locked():
            raise StorageError("storage_busy")
        async with self.storage_lock:
            future = asyncio.get_running_loop().run_in_executor(self.storage_executor, fn, *args)
            try:
                return await asyncio.shield(future)
            finally:
                if not future.done():
                    await finish_cleanup(future)

    def submit(self, fn, *args):
        return asyncio.get_running_loop().run_in_executor(self.executor, fn, *args)

    def expire(self):
        now = time.monotonic()
        expired = [key for key, entry in self.conversations.items()
                   if not entry.active and now - entry.touched >= self.config.conversation_idle_seconds]
        for key in expired:
            del self.conversations[key]

    def reach_mode(self, body):
        requested = body.reach
        return ("on" if requested is True else "off" if requested is False else "auto" if requested == "auto"
                else self.config.reach_default or "off")

    def mode(self, body):
        requested = body.retrieval
        return "on" if requested is True else "off" if requested is False else "auto" if requested == "auto" else self.default_mode

    def admit(self, body):
        if self.mode(body) == "on" and self.index is None:
            return error(503, "retrieval_disabled", "No local retrieval index is configured.")
        if not self.ready:
            return error(503, "unavailable", "Model is unavailable.", retry=True)
        self.expire()
        key = body.conversation_id
        entry = self.conversations.get(key)
        restoring = key is not None and entry is None and self.store is not None
        if key in self.deleting:
            return error(409, "conversation_busy", "Conversation is being deleted.", retry=True)
        if key is not None and entry is None and not restoring:
            return error(404, "conversation_not_found", "Conversation is unknown or expired.")
        if entry is not None and entry.active:
            return error(409, "conversation_busy", "Conversation has an active request.", retry=True)
        if self.busy:
            return error(503, "backend_busy", "Model has an active request.", retry=True)
        if entry is None:
            if len(self.conversations) >= self.config.max_conversations:
                return error(503, "conversation_capacity", "Conversation limit reached; delete an idle conversation.", retry=True)
            key = key or secrets.token_urlsafe(24)
            entry = Conversation(DwindyCore(self.backend, options=self.model_config.options(),
                                           system_prompt=self.model_config.system_prompt), time.monotonic())
            self.conversations[key] = entry
        self.busy = entry.active = True
        return ChatResponse(self, key, entry, body, restoring=restoring)


async def finish_cleanup(task):
    """A cancelled HTTP task must not cancel or outlive native cleanup."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


_END = object()


class Disconnected(Exception):
    pass


def storage_error(exc):
    return error(503, exc.code, "Conversation storage failed; no successful completion was acknowledged.",
                 retry=exc.code == "storage_busy")


class ChatResponse(Response):
    def __init__(self, state, key, entry, body, restoring=False):
        super().__init__(content=None)
        self.state, self.key, self.entry, self.body = state, key, entry, body
        self.restoring = restoring

    async def __call__(self, scope, receive, send):
        state = self.state
        owner = asyncio.current_task()
        state.tasks.add(owner)
        stream = None
        pending = None
        disconnected = asyncio.Event()
        headers_sent = False
        http_started = False
        cancelled = False
        exposed = self.body.conversation_id is not None
        transport_send = send
        before = None
        released = False

        def release_lease():
            nonlocal released
            if not released:
                self.entry.active = state.busy = False
                self.entry.touched = time.monotonic()
                released = True

        async def next_and_save():
            item = await state.submit(next, stream, _END)
            if isinstance(item, Completion) and state.store is not None:
                # This task is settled even if disconnect wins the response race.
                await state.submit(stream.close)
                snapshot = self.entry.core.snapshot()
                try:
                    await state.storage(state.store.append, self.key, snapshot, item.finish_reason, internal=True)
                except Exception as exc:
                    if not isinstance(exc, StorageError) or exc.uncertain:
                        state.ready = False
                        state.conversations.pop(self.key, None)
                    else:
                        self.entry.core.restore(before)
                    if not isinstance(exc, StorageError):
                        raise StorageError(uncertain=True) from exc
                    raise
            return item

        async def send(message):
            nonlocal http_started
            if message["type"] == "http.response.start":
                http_started = True
            await transport_send(message)

        async def watch():
            while True:
                if (await receive())["type"] == "http.disconnect":
                    disconnected.set()
                    return

        watcher = asyncio.create_task(watch())

        async def advance():
            nonlocal pending
            if disconnected.is_set():
                raise Disconnected()
            pending = asyncio.create_task(next_and_save())
            await asyncio.wait((pending, watcher), return_when=asyncio.FIRST_COMPLETED)
            if disconnected.is_set():
                raise Disconnected()
            return pending.result()

        async def event(name, data):
            await send({"type": "http.response.body", "body":
                        ("event: " + name + "\ndata: " + json.dumps(data, ensure_ascii=False) + "\n\n").encode("utf-8"),
                        "more_body": True})

        async def reach_step(decision, local_evidence, host):
            """Deployment-gated Reach; the one possible network call runs off the event loop."""
            snapshot = state.index.project_snapshot if state.index is not None else None
            run = lambda: reach.decide(
                self.body.message, state.reach_mode(self.body), backend=state.reach_backend,
                project_name=snapshot["name"] if snapshot else None, host_texts=[text for _, text in host],
                local_supplied=local_evidence is not None,
                local_relevant=reach.local_relevant(decision, local_evidence),
                max_tokens=state.config.retrieval_context_tokens)
            if state.reach_backend is None:
                return run()  # No provider: no network path exists at all.
            return await asyncio.get_running_loop().run_in_executor(None, run)

        async def select_context():
            mode, tokens = state.mode(self.body), state.config.retrieval_context_tokens
            if mode == "on":
                passages = await state.storage(state.index.search, self.body.message, 12)
                return ContextDecision("on", True, "explicit"), Evidence(passages, tokens)
            if mode == "off":
                return ContextDecision("off", False, "off"), None
            if state.index is None:
                return decide(self.body.message, "auto", max_tokens=tokens)
            snapshot = state.index.project_snapshot
            options = dict(project_name=snapshot["name"] if snapshot else None, max_tokens=tokens)
            try:
                return await state.storage(lambda: decide(self.body.message, "auto", search=state.index.search, **options))
            except StorageError as exc:
                if exc.code != "storage_busy" or exc.uncertain:
                    raise
                # The shared storage worker is occupied: decide without waiting, as a busy retrieval.
                def busy(*args):
                    raise RetrievalError("retrieval_busy")
                return decide(self.body.message, "auto", search=busy, **options)

        async def cleanup():
            # A pending next() can still be inside C. Never close or reuse it concurrently.
            if pending is not None:
                with suppress(Exception):
                    await asyncio.shield(pending)
            try:
                if stream is not None and not released:
                    await state.submit(stream.close)
            except Exception:
                state.ready = False  # A failed close cannot establish safe backend reuse.
            finally:
                watcher.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await watcher
                release_lease()
                if not exposed and not self.entry.active:
                    state.conversations.pop(self.key, None)
                state.tasks.discard(owner)

        try:
            if self.restoring:
                try:
                    saved = await state.storage(state.store.load, self.key)
                    if saved is None:
                        state.conversations.pop(self.key, None)
                        await error(404, "conversation_not_found", "Conversation is unknown or deleted.")(scope, receive, send)
                        return
                    self.entry.core.restore(saved)
                except BaseException:
                    state.conversations.pop(self.key, None)
                    raise
            if state.store is not None:
                before = self.entry.core.snapshot()
            decision, evidence = await select_context()
            # Capability facts are computed now, per turn, so the clock is never stale.
            computed = capabilities.select(self.body.message)
            host = [(item.label, item.text) for item in self.body.host_context or ()]
            facts = Facts(tuple((f.name, f.text) for f in computed), tuple(host), HOST_CONTEXT_BUDGET_TOKENS)
            used = [f.metadata for f in computed] + ([dict(name="host_context", items=len(host))] if host else [])
            reach_decision, web_evidence, notice = await reach_step(decision, evidence, host)
            stream = self.entry.core.chat(self.body.message, evidence=web_evidence or evidence, facts=facts, notice=notice)
            started = await advance()
            if not isinstance(started, TurnStarted):
                raise RuntimeError("Missing Core start")
            if self.body.stream:
                await send({"type": "http.response.start", "status": 200, "headers": [
                    (b"content-type", b"text/event-stream; charset=utf-8"),
                    (b"cache-control", b"no-store"), (b"x-accel-buffering", b"no")]})
                headers_sent = True
                start_data = {"conversation_id": self.key, "dropped_turns": started.dropped_turns}
                start_data.update(turn_metadata(decision, started, web_evidence, reach_decision, used))
                await event("started", start_data)
                exposed = True
            pieces = []
            while True:
                item = await advance()
                if isinstance(item, TextDelta):
                    if self.body.stream:
                        await event("delta", {"text": item.text})
                    else:
                        pieces.append(item.text)
                elif isinstance(item, Completion):
                    # Core commits before yielding Completion. Release its guard before delivery.
                    pending = state.submit(stream.close)
                    try:
                        await asyncio.shield(pending)
                    except Exception:
                        state.ready = False
                        raise
                    result = {"finish_reason": item.finish_reason,
                              "usage": {"prompt_tokens": item.prompt_tokens, "text_tokens": item.text_tokens}}
                    # All native work, stream cleanup and optional saving have
                    # settled. A client receiving completion may immediately chat.
                    release_lease()
                    if self.body.stream:
                        await event("completed", result)
                        await send({"type": "http.response.body", "body": b"", "more_body": False})
                    else:
                        result.update(conversation_id=self.key, text="".join(pieces), dropped_turns=started.dropped_turns)
                        result.update(turn_metadata(decision, started, web_evidence, reach_decision, used))
                        await JSONResponse(result, headers={"Cache-Control": "no-store"})(scope, receive, send)
                        exposed = True
                    break
                else:
                    raise RuntimeError("Missing Core completion")
        except Disconnected:
            pass
        except asyncio.CancelledError:
            cancelled = True
        except Exception as exc:
            if isinstance(exc, StorageError) and exc.uncertain:
                state.ready = False
            response = (storage_error(exc) if isinstance(exc, StorageError) else
                        error(422, "context_limit", "Message cannot fit the configured context/output allowance.")
                        if isinstance(exc, ContextLimitError)
                        else error(500, "inference_failed", "Inference failed; the turn was not completed."))
            if released:
                response = error(503, "delivery_uncertain", "The turn completed but completion delivery failed; do not retry automatically.")
            elif isinstance(exc, RetrievalError):
                response = error(503, exc.code, str(exc), retry=exc.code == "retrieval_busy")
            if not disconnected.is_set():
                try:
                    if headers_sent:
                        await event("error", json.loads(response.body))
                        await send({"type": "http.response.body", "body": b"", "more_body": False})
                    else:
                        await response(scope, receive, send)
                except (OSError, asyncio.CancelledError):
                    pass
        finally:
            await finish_cleanup(asyncio.create_task(cleanup()))
        # Graceful shutdown can cancel a connected request. Finish its protocol after
        # cleanup rather than leaving Uvicorn with an incomplete ASGI response.
        if cancelled and not disconnected.is_set():
            response = error(503, "unavailable", "Request cancelled while the server is stopping.", retry=True)
            try:
                if headers_sent:
                    await event("error", json.loads(response.body))
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
                elif not http_started:
                    await response(scope, receive, send)
            except (OSError, asyncio.CancelledError):
                pass


def turn_metadata(decision, started, web_evidence, reach_decision, used):
    """Response metadata. Web results never masquerade as local retrieval sources."""
    out = {}
    retrieval = decision.metadata(None if web_evidence is not None else started.retrieval)
    if retrieval is not None:
        out["retrieval"] = retrieval
    if used:
        out["capabilities"] = used
    if reach_decision is not None:
        out["reach"] = reach_decision.metadata(started.retrieval if web_evidence is not None else None)
    return out


def create_app(model_config, api_config=None, *, backend=None, chat_root=None, reach_backend=None):
    """Application owns supplied or constructed backend; lifespan closes it once.
    reach_backend replaces the configured provider in tests; it never enables Reach on its own."""
    config = api_config or ApiConfig()
    token = config.validate()
    files = {}
    if chat_root is not None:
        from .web_ui import frontend_files
        files = frontend_files(chat_root)
    state = ApiState(config, model_config)
    if config.reach_provider is not None:
        try:
            state.reach_backend = reach_backend or reach.WikipediaBackend()
        except (ImportError, OSError):
            state.reach_backend = reach.UnavailableBackend()

    @asynccontextmanager
    async def lifespan(app):
        try:
            if config.retrieval_index_path is not None:
                loading_index = asyncio.get_running_loop().run_in_executor(
                    state.storage_executor, RetrievalIndex, config.retrieval_index_path)
                try:
                    state.index = await asyncio.shield(loading_index)
                except asyncio.CancelledError:
                    state.index = await finish_cleanup(loading_index)
                    raise
            if config.database_path is not None:
                loading_store = asyncio.get_running_loop().run_in_executor(
                    state.storage_executor, ConversationStore, config.database_path, config.database_max_mib)
                try:
                    state.store = await asyncio.shield(loading_store)
                except asyncio.CancelledError:
                    state.store = await finish_cleanup(loading_store)
                    raise
            if backend is None:
                from .llama_backend import LlamaBackend
                loading = state.submit(LlamaBackend, model_config)
                try:
                    state.backend = await asyncio.shield(loading)
                except asyncio.CancelledError:
                    state.backend = await finish_cleanup(loading)
                    raise
            else:
                state.backend = backend
            state.ready = True
            yield
        finally:
            state.ready = False
            for task in tuple(state.tasks):
                task.cancel()
            if state.tasks:
                await finish_cleanup(asyncio.ensure_future(asyncio.gather(*tuple(state.tasks), return_exceptions=True)))
            try:
                if state.backend is not None:
                    await finish_cleanup(state.submit(state.backend.close))
            finally:
                if state.store is not None:
                    await finish_cleanup(asyncio.create_task(state.storage(state.store.close, internal=True)))
                if state.index is not None:
                    await finish_cleanup(asyncio.create_task(state.storage(state.index.close, internal=True)))
                if state.storage_executor is not None:
                    state.storage_executor.shutdown(wait=True)
                if state.reach_backend is not None and hasattr(state.reach_backend, "close"):
                    state.reach_backend.close()
                state.conversations.clear()
                state.executor.shutdown(wait=True)

    app = FastAPI(title="Dwindy local API", version="1", lifespan=lifespan,
                  docs_url=None, redoc_url=None, responses=ERROR_RESPONSES)
    app.state.dwindy = state
    public_files = (*files, "/chat/") if files else ()
    app.add_middleware(SecurityMiddleware, config=config, token=token, public_files=public_files)
    if files:
        from .web_ui import add_frontend
        add_frontend(app, files)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(exc.status_code, "http_error", "Unknown endpoint or unsupported method.")

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return error(500, "internal_error", "Request failed.")

    # Unset project fields are omitted so M3-M6 responses stay byte-for-byte unchanged.
    @app.get("/v1/health", response_model=HealthReply, response_model_exclude_none=True)
    async def health():
        if not state.ready:
            return error(503, "unavailable", "Model is unavailable.", retry=True)
        return {"status": "ready", "busy": state.busy, "persistence_enabled": state.store is not None,
                "retrieval_enabled": state.index is not None,
                "retrieval_default": state.default_mode if state.index is not None else None,
                "project_snapshot": state.index.project_snapshot if state.index is not None else None,
                "reach_enabled": True if config.reach_provider else None,
                "reach_provider": config.reach_provider,
                "reach_default": (config.reach_default or "off") if config.reach_provider else None}

    @app.delete("/v1/conversations/{conversation_id}", status_code=204)
    async def delete(conversation_id: str):
        state.expire()
        entry = state.conversations.get(conversation_id)
        if entry is None and state.store is None:
            return error(404, "conversation_not_found", "Conversation is unknown or expired.")
        if conversation_id in state.deleting or (entry is not None and entry.active):
            return error(409, "conversation_busy", "Conversation has an active request.", retry=True)
        if state.store is not None:
            if not state.ready:
                return error(503, "storage_unavailable", "Conversation storage is unavailable.")
            state.deleting.add(conversation_id)
            if entry is not None:
                entry.active = True
            owner = asyncio.current_task()
            state.tasks.add(owner)
            async def remove():
                try:
                    found = await state.storage(state.store.delete, conversation_id)
                    state.conversations.pop(conversation_id, None)
                    return found
                finally:
                    state.deleting.discard(conversation_id)
                    if entry is not None:
                        entry.active = False
                        entry.touched = time.monotonic()
            try:
                found = await finish_cleanup(asyncio.create_task(remove()))
                if not found and entry is None:
                    return error(404, "conversation_not_found", "Conversation is unknown or deleted.")
            except StorageError as exc:
                if exc.uncertain:
                    state.ready = False
                return storage_error(exc)
            finally:
                state.tasks.discard(owner)
        else:
            del state.conversations[conversation_id]
        return Response(status_code=204)

    @app.post("/v1/chat", response_model=ChatReply, responses={200: {"content": {"text/event-stream": {
        "schema": {"type": "string"}, "example": 'event: delta\ndata: {"text":"Hello"}\n\n'}},
        "description": "JSON by default; stream=true selects started/delta/completed/error SSE events."}},
        openapi_extra={"requestBody": {"required": True, "content": {
        "application/json": {"schema": ChatRequest.model_json_schema()}}}})
    async def chat(request: Request):
        body = await read_body(request, ChatRequest)
        if isinstance(body, Response):
            return body
        if body.host_context is not None and token is None:
            # Without a configured token no caller is authenticated, so host data cannot be trusted.
            return error(403, "host_context_requires_token",
                         "Host context requires a configured API token and bearer authentication.")
        if state.mode(body) == "on":
            try:
                match_query(body.message)
            except ValueError:
                return error(422, "invalid_request", "Retrieval queries must be nonblank and at most 2048 UTF-8 bytes.")
        return state.admit(body)

    @app.post("/v1/retrieve", response_model=RetrieveReply, response_model_exclude_none=True, openapi_extra={"requestBody": {"required": True, "content": {
        "application/json": {"schema": RetrieveRequest.model_json_schema()}}}})
    async def retrieve(request: Request):
        body = await read_body(request, RetrieveRequest)
        if isinstance(body, Response):
            return body
        if state.index is None:
            return error(503, "retrieval_disabled", "No local retrieval index is configured.")
        if not state.ready:
            return error(503, "unavailable", "Server is unavailable.")
        owner = asyncio.current_task()
        state.tasks.add(owner)
        try:
            matches = await state.storage(state.index.search, body.query)
            return {"matches": [p.mapping() for p in matches]}
        except RetrievalError as exc:
            return error(503, exc.code, str(exc), retry=exc.code == "retrieval_busy")
        except StorageError as exc:
            return storage_error(exc)
        finally:
            state.tasks.discard(owner)

    async def read_body(request, schema):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            return error(415, "unsupported_media_type", "Use application/json.")
        chunks, size = [], 0
        try:
            async for chunk in request.stream():
                size += len(chunk)
                if size > config.max_request_bytes:
                    return error(413, "request_too_large", "Request body exceeds the configured limit.")
                chunks.append(chunk)
        except ClientDisconnect:
            return error(400, "incomplete_request", "Request body was not received.")
        try:
            def invalid_constant(value):
                raise ValueError("Non-JSON constant")
            data = json.loads(b"".join(chunks), parse_constant=invalid_constant)
        except (ValueError, UnicodeError, RecursionError):
            return error(400, "invalid_json", "Body must be valid JSON.")
        try:
            body = schema.model_validate(data)
        except ValidationError:
            return error(422, "invalid_request", "Request fields are invalid for this endpoint.")
        return body

    return app
