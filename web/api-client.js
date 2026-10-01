// Internal browser transport shared by both presentations; no model policy.
export class ApiError extends Error {
  constructor(code, message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

export function apiBase(value = location.origin) {
  const url = new URL(value, location.href);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new ApiError('configuration', 'Use an HTTP(S) API base without credentials, query or fragment.');
  }
  return url.href.replace(/\/$/, '');
}

const protocolError = () => new ApiError('protocol', 'The response stream was invalid or incomplete. Start a new conversation.');

// Network chunks are not SSE frames. Support UTF-8 splits and every SSE line ending.
export async function* readEvents(body) {
  if (!body) throw protocolError();
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8', {fatal: true});
  let buffer = '', event = '', data = [];
  try {
    while (true) {
      const {value, done} = await reader.read();
      try { buffer += decoder.decode(value, {stream: !done}); } catch { throw protocolError(); }
      if (buffer.length + data.join('\n').length > 1048576) throw protocolError();
      while (true) {
        const match = /[\r\n]/.exec(buffer);
        if (!match || (!done && match[0] === '\r' && match.index === buffer.length - 1)) break;
        const line = buffer.slice(0, match.index);
        const width = buffer.slice(match.index, match.index + 2) === '\r\n' ? 2 : 1;
        buffer = buffer.slice(match.index + width);
        if (!line) {
          if (data.length) {
            let payload;
            try { payload = JSON.parse(data.join('\n')); } catch { throw protocolError(); }
            yield {event, data: payload};
          }
          event = ''; data = [];
        } else if (!line.startsWith(':')) {
          const colon = line.indexOf(':');
          const field = colon < 0 ? line : line.slice(0, colon);
          const content = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
          if (field === 'event') event = content;
          if (field === 'data') data.push(content);
        }
      }
      if (done) {
        if (buffer || data.length || event) throw protocolError();
        return;
      }
    }
  } finally {
    try { await reader.cancel(); } finally { reader.releaseLock(); }
  }
}

async function responseError(response) {
  let body;
  try { body = await response.json(); } catch { /* Untrusted/non-API error page. */ }
  return new ApiError(typeof body?.error?.code === 'string' ? body.error.code : 'http_error',
    typeof body?.error?.message === 'string' ? body.error.message : `Request failed (${response.status}).`, response.status);
}

export class ChatClient {
  #base; #token; #fetch; #controller = null;
  conversationId = null;
  uncertain = false;

  constructor({base, token = '', fetchImpl = globalThis.fetch.bind(globalThis)} = {}) {
    this.#base = apiBase(base);
    this.#token = token;
    this.#fetch = fetchImpl;
  }

  #request(path, options = {}) {
    const headers = {...options.headers};
    if (this.#token) headers.Authorization = `Bearer ${this.#token}`;
    return this.#fetch(`${this.#base}/v1/${path}`, {
      ...options, headers, credentials: 'omit', cache: 'no-store', redirect: 'error',
    });
  }

  async health(signal) {
    const response = await this.#request('health', {signal});
    if (!response.ok) throw await responseError(response);
    return response.json();
  }

  stop() { this.#controller?.abort(); }

  async reset() {
    if (this.#controller) throw new ApiError('conversation_busy', 'Wait for this request to stop before resetting.', 409);
    if (this.conversationId) {
      const response = await this.#request(`conversations/${encodeURIComponent(this.conversationId)}`, {method: 'DELETE'});
      if (response.status !== 204 && response.status !== 404) throw await responseError(response);
    }
    this.conversationId = null;
    this.uncertain = false;
  }

  async *chat(message) {
    if (this.#controller) throw new ApiError('conversation_busy', 'A request is already active.', 409);
    if (this.uncertain) throw new ApiError('uncertain', 'Start a new conversation before sending again.');
    if (typeof message !== 'string' || !message.trim()) throw new ApiError('invalid_request', 'Enter a message.');
    const controller = new AbortController();
    this.#controller = controller;
    let settled = false, started = false;
    try {
      const response = await this.#request('chat', {method: 'POST', signal: controller.signal,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message, conversation_id: this.conversationId, stream: true})});
      if (!response.ok) {
        const failure = await responseError(response);
        settled = failure.status < 500 || ['backend_busy', 'conversation_capacity', 'unavailable', 'inference_failed'].includes(failure.code);
        if (failure.code === 'conversation_not_found') this.uncertain = true;
        throw failure;
      }
      if (!response.headers.get('content-type')?.startsWith('text/event-stream')) throw protocolError();
      for await (const item of readEvents(response.body)) {
        const data = item.data;
        if (!data || typeof data !== 'object') throw protocolError();
        if (item.event === 'started' && !started) {
          if (typeof data.conversation_id !== 'string' || !/^[\w-]{32}$/.test(data.conversation_id) || !Number.isInteger(data.dropped_turns) || data.dropped_turns < 0) throw protocolError();
          if (this.conversationId && this.conversationId !== data.conversation_id) throw protocolError();
          this.conversationId = data.conversation_id;
          started = true;
        } else if (item.event === 'delta' && started) {
          if (typeof data.text !== 'string') throw protocolError();
        } else if (item.event === 'completed' && started) {
          if (typeof data.finish_reason !== 'string' || !['prompt_tokens', 'text_tokens'].every(k =>
            Number.isInteger(data.usage?.[k]) && data.usage[k] >= 0)) throw protocolError();
          settled = true;
        } else if (item.event === 'error' && started) {
          if (typeof data.error?.code !== 'string' || typeof data.error.message !== 'string') throw protocolError();
          // Shutdown may race with Core commit. Treat unavailable as uncertain.
          settled = ['inference_failed', 'context_limit'].includes(data.error.code);
          throw new ApiError(data.error.code, data.error.message);
        } else throw protocolError();
        yield item;
        if (item.event === 'completed') return;
      }
      throw protocolError();
    } finally {
      if (!settled) this.uncertain = true;
      controller.abort();
      this.#controller = null;
    }
  }
}
