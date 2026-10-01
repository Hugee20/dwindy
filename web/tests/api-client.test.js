import {ChatClient, readEvents, apiBase} from '../api-client.js';
export function assert(value, message = 'Assertion failed') { if (!value) throw Error(message); }
export async function rejects(fn, code) {
  try { await fn(); } catch (e) { if (code) assert(e.code === code, `${e.code} != ${code}`); return e; }
  throw Error('Expected rejection');
}
export const id = 'A'.repeat(32);
export const frame = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
export const start = frame('started', {conversation_id: id, dropped_turns: 0});
export const done = frame('completed', {finish_reason: 'stop', usage: {prompt_tokens: 3, text_tokens: 2}});
export const answer = start + frame('delta', {text: 'hi 🌿\nthere'}) + done;
export function response(text = answer, split = 3) {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream({start(c) {
    for (let i = 0; i < bytes.length; i += split) c.enqueue(bytes.slice(i, i + split)); c.close();
  }}), {headers: {'Content-Type': 'text/event-stream'}});
}
const drain = async stream => { const events = []; for await (const e of stream) events.push(e); return events; };
const errorResponse = (status, code) => new Response(JSON.stringify({error: {code, message: 'Safe error'}}), {status});

export const tests = [
  ['invalid UTF-8 is a protocol error', async () => {
    const body = new ReadableStream({start(c) { c.enqueue(new Uint8Array([255])); c.close(); }});
    await rejects(() => drain(readEvents(body)), 'protocol');
  }],
  ['ID payload must be a string', async () => {
    const client = new ChatClient({fetchImpl: async () => response(frame('started', {conversation_id: [id], dropped_turns: 0}) + done)});
    await rejects(() => drain(client.chat('hi')), 'protocol');
  }],
  ['fragmented UTF-8 and SSE', async () => {
    for (const n of [1, 2, 5, 10000]) {
      const events = await drain(readEvents(response(answer, n).body));
      assert(events.length === 3 && events[1].data.text === 'hi 🌿\nthere');
    }
  }],
  ['CRLF, CR, comments and multiline data', async () => {
    for (const newline of ['\r\n', '\r', '\n']) {
      const text = ': comment\nevent: delta\ndata: {"text":\ndata: "x"}\n\n'.replaceAll('\n', newline);
      const events = await drain(readEvents(response(text, 1).body));
      assert(events[0].data.text === 'x');
    }
  }],
  ['reject malformed and truncated frames', async () => {
    for (const text of ['event: delta\ndata: nope\n\n', 'event: delta\ndata: {}\n'])
      await rejects(() => drain(readEvents(response(text).body)), 'protocol');
  }],
  ['retain ID and send unchanged text/settings', async () => {
    const calls = [];
    const client = new ChatClient({base: 'http://localhost:8000', token: 'private', fetchImpl: async (url, options) => {
      calls.push({url, options}); return response();
    }});
    await drain(client.chat('  /reset  ')); await drain(client.chat('two'));
    assert(client.conversationId === id);
    assert(JSON.parse(calls[0].options.body).message === '  /reset  ');
    assert(JSON.parse(calls[1].options.body).conversation_id === id);
    assert(calls[0].options.credentials === 'omit' && calls[0].options.redirect === 'error');
    assert(calls[0].options.headers.Authorization === 'Bearer private');
  }],
  ['busy errors do not retry or lose ID', async () => {
    let calls = 0;
    const client = new ChatClient({fetchImpl: async () => { calls++; return errorResponse(503, 'backend_busy'); }});
    client.conversationId = id;
    await rejects(() => drain(client.chat('hi')), 'backend_busy');
    assert(calls === 1 && !client.uncertain && client.conversationId === id);
  }],
  ['EOF without completion is uncertain', async () => {
    const client = new ChatClient({fetchImpl: async () => response(start)});
    await rejects(() => drain(client.chat('hi')), 'protocol');
    assert(client.uncertain && client.conversationId === id);
    await rejects(() => drain(client.chat('again')), 'uncertain');
  }],
  ['reject wrong event ordering', async () => {
    for (const text of [done, start + start, frame('delta', {text: 'x'}), start + frame('tool', {})]) {
      const client = new ChatClient({fetchImpl: async () => response(text)});
      await rejects(() => drain(client.chat('hi')), 'protocol'); assert(client.uncertain);
    }
  }],
  ['server error preserves address without committing UI success', async () => {
    const client = new ChatClient({fetchImpl: async () => response(start + frame('error', {error: {code: 'inference_failed', message: 'failed'}}))});
    await rejects(() => drain(client.chat('hi')), 'inference_failed');
    assert(!client.uncertain && client.conversationId === id);
  }],
  ['shutdown error is uncertain', async () => {
    const client = new ChatClient({fetchImpl: async () => response(start + frame('error', {error: {code: 'unavailable', message: 'stopping'}}))});
    await rejects(() => drain(client.chat('hi')), 'unavailable'); assert(client.uncertain);
  }],
  ['early consumer close cancels stream and blocks continuation', async () => {
    const client = new ChatClient({fetchImpl: async () => response()});
    const stream = client.chat('hi'); await stream.next(); await stream.return();
    assert(client.uncertain);
  }],
  ['abort before headers requires reset and makes no replay', async () => {
    let calls = 0;
    const client = new ChatClient({fetchImpl: async (_, {signal}) => {
      calls++; return new Promise((_, reject) => signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
    }});
    const pending = drain(client.chat('hi')); client.stop();
    await rejects(() => pending); assert(client.uncertain && calls === 1);
    await client.reset(); assert(!client.uncertain);
  }],
  ['reset clears only after delete 204 or 404', async () => {
    for (const status of [204, 404, 409, 500]) {
      let url;
      const client = new ChatClient({fetchImpl: async u => { url = u; return new Response(null, {status}); }});
      client.conversationId = id; client.uncertain = true;
      if ([204, 404].includes(status)) { await client.reset(); assert(!client.conversationId && !client.uncertain); }
      else { await rejects(() => client.reset()); assert(client.conversationId === id && client.uncertain); }
      assert(url.endsWith(`/conversations/${id}`));
    }
  }],
  ['expired conversation never silently recreates', async () => {
    const client = new ChatClient({fetchImpl: async () => errorResponse(404, 'conversation_not_found')});
    client.conversationId = id;
    await rejects(() => drain(client.chat('hi')), 'conversation_not_found'); assert(client.uncertain);
  }],
  ['instances retain separate state', async () => {
    const a = new ChatClient({fetchImpl: async () => response()}); const b = new ChatClient();
    await drain(a.chat('hi')); assert(a.conversationId === id && b.conversationId === null);
  }],
  ['overlap rejected', async () => {
    const client = new ChatClient({fetchImpl: async () => response()}); const stream = client.chat('hi');
    await stream.next(); await rejects(() => drain(client.chat('second')), 'conversation_busy');
    await rejects(() => client.reset(), 'conversation_busy'); await stream.return();
  }],
  ['invalid endpoint and empty input rejected', async () => {
    for (const base of ['file:///a', 'https://user:pass@example.org', 'https://example.org/?token=x'])
      await rejects(async () => apiBase(base), 'configuration');
    const client = new ChatClient(); await rejects(() => drain(client.chat('  ')), 'invalid_request');
  }],
];
