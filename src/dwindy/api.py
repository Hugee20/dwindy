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
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.exceptions import HTTPException
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse, Response

from .backend import Completion, ContextLimitError, TextDelta
from .core import DwindyCore, TurnStarted
from .server import ApiConfig


def error(status, code, message, *, retry=False):
    headers = {"Cache-Control": "no-store"}
    if retry:
        headers["Retry-After"] = "1"
    return JSONResponse({"error": {"code": code, "message": message}}, status, headers=headers)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str
    conversation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{32}$")
    stream: bool = False

    @field_validator("message")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Message must not be blank.")
        return value


class Usage(BaseModel):
    prompt_tokens: int
    text_tokens: int = Field(description="Retokenized raw response text, not sampled-token count.")


class ChatReply(BaseModel):
    conversation_id: str
    text: str
    finish_reason: str
    dropped_turns: int
    usage: Usage


class HealthReply(BaseModel):
    status: str
    busy: bool


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

    def __init__(self, app, config, token):
        self.app, self.config, self.token = app, config, token

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
        if self.token is not None:
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

    def submit(self, fn, *args):
        return asyncio.get_running_loop().run_in_executor(self.executor, fn, *args)

    def expire(self):
        now = time.monotonic()
        expired = [key for key, entry in self.conversations.items()
                   if not entry.active and now - entry.touched >= self.config.conversation_idle_seconds]
        for key in expired:
            del self.conversations[key]

    def admit(self, body):
        if not self.ready:
            return error(503, "unavailable", "Model is unavailable.", retry=True)
        self.expire()
        key = body.conversation_id
        entry = self.conversations.get(key)
        if key is not None and entry is None:
            return error(404, "conversation_not_found", "Conversation is unknown or expired.")
        if entry is not None and entry.active:
            return error(409, "conversation_busy", "Conversation has an active request.", retry=True)
        if self.busy:
            return error(503, "backend_busy", "Model has an active request.", retry=True)
        if entry is None:
            if len(self.conversations) >= self.config.max_conversations:
                return error(503, "conversation_capacity", "Conversation limit reached; delete an idle conversation.", retry=True)
            key = secrets.token_urlsafe(24)
            entry = Conversation(DwindyCore(self.backend, options=self.model_config.options(),
                                           system_prompt=self.model_config.system_prompt), time.monotonic())
            self.conversations[key] = entry
        self.busy = entry.active = True
        return ChatResponse(self, key, entry, body)


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


class ChatResponse(Response):
    def __init__(self, state, key, entry, body):
        super().__init__(content=None)
        self.state, self.key, self.entry, self.body = state, key, entry, body

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
            pending = state.submit(next, stream, _END)
            await asyncio.wait((pending, watcher), return_when=asyncio.FIRST_COMPLETED)
            if disconnected.is_set():
                raise Disconnected()
            return pending.result()

        async def event(name, data):
            await send({"type": "http.response.body", "body":
                        ("event: " + name + "\ndata: " + json.dumps(data, ensure_ascii=False) + "\n\n").encode("utf-8"),
                        "more_body": True})

        async def cleanup():
            # A pending next() can still be inside C. Never close or reuse it concurrently.
            if pending is not None:
                with suppress(Exception):
                    await asyncio.shield(pending)
            try:
                if stream is not None:
                    await state.submit(stream.close)
            except Exception:
                state.ready = False  # A failed close cannot establish safe backend reuse.
            finally:
                watcher.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await watcher
                self.entry.active = state.busy = False
                self.entry.touched = time.monotonic()
                if not exposed:
                    state.conversations.pop(self.key, None)
                state.tasks.discard(owner)

        try:
            stream = self.entry.core.chat(self.body.message)
            started = await advance()
            if not isinstance(started, TurnStarted):
                raise RuntimeError("Missing Core start")
            if self.body.stream:
                await send({"type": "http.response.start", "status": 200, "headers": [
                    (b"content-type", b"text/event-stream; charset=utf-8"),
                    (b"cache-control", b"no-store"), (b"x-accel-buffering", b"no")]})
                headers_sent = True
                await event("started", {"conversation_id": self.key, "dropped_turns": started.dropped_turns})
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
                    if self.body.stream:
                        await event("completed", result)
                        await send({"type": "http.response.body", "body": b"", "more_body": False})
                    else:
                        result.update(conversation_id=self.key, text="".join(pieces), dropped_turns=started.dropped_turns)
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
            response = (error(422, "context_limit", "Message cannot fit the configured context/output allowance.")
                        if isinstance(exc, ContextLimitError)
                        else error(500, "inference_failed", "Inference failed; the turn was not completed."))
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


def create_app(model_config, api_config=None, *, backend=None):
    """Application owns supplied or constructed backend; lifespan closes it once."""
    config = api_config or ApiConfig()
    token = config.validate()
    state = ApiState(config, model_config)

    @asynccontextmanager
    async def lifespan(app):
        try:
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
                state.conversations.clear()
                state.executor.shutdown(wait=True)

    app = FastAPI(title="Dwindy local API", version="1", lifespan=lifespan,
                  docs_url=None, redoc_url=None, responses=ERROR_RESPONSES)
    app.state.dwindy = state
    app.add_middleware(SecurityMiddleware, config=config, token=token)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(exc.status_code, "http_error", "Unknown endpoint or unsupported method.")

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return error(500, "internal_error", "Request failed.")

    @app.get("/v1/health", response_model=HealthReply)
    async def health():
        if not state.ready:
            return error(503, "unavailable", "Model is unavailable.", retry=True)
        return {"status": "ready", "busy": state.busy}

    @app.delete("/v1/conversations/{conversation_id}", status_code=204)
    async def delete(conversation_id: str):
        state.expire()
        entry = state.conversations.get(conversation_id)
        if entry is None:
            return error(404, "conversation_not_found", "Conversation is unknown or expired.")
        if entry.active:
            return error(409, "conversation_busy", "Conversation has an active request.", retry=True)
        del state.conversations[conversation_id]
        return Response(status_code=204)

    @app.post("/v1/chat", response_model=ChatReply, responses={200: {"content": {"text/event-stream": {
        "schema": {"type": "string"}, "example": 'event: delta\ndata: {"text":"Hello"}\n\n'}},
        "description": "JSON by default; stream=true selects started/delta/completed/error SSE events."}},
        openapi_extra={"requestBody": {"required": True, "content": {
        "application/json": {"schema": ChatRequest.model_json_schema()}}}})
    async def chat(request: Request):
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
            body = ChatRequest.model_validate(data)
        except ValidationError:
            return error(422, "invalid_request", "Expected message, optional conversation_id, and optional boolean stream.")
        return state.admit(body)

    return app
