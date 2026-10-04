import '../dwindy-chat.js';
import {assert, rejects, response, start, done, frame, id} from './api-client.test.js';

export async function waitFor(predicate) {
  for (let i = 0; i < 300; i++) { if (predicate()) return; await new Promise(r => setTimeout(r, 10)); }
  throw Error('Timed out waiting for component');
}

async function fixture(run, {fetchImpl, attributes = {presentation: 'inline'}} = {}) {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({url, options});
    if (fetchImpl) return fetchImpl(url, options);
    if (url.endsWith('/health')) return new Response(JSON.stringify({status: 'ready', busy: false}));
    if (options.method === 'DELETE') return new Response(null, {status: 204});
    return response();
  };
  const chat = document.createElement('dwindy-chat');
  for (const [k, v] of Object.entries(attributes)) chat.setAttribute(k, v);
  document.body.append(chat);
  try {
    await waitFor(() => chat.shadowRoot.querySelector('link').sheet !== null);
    await run(chat, calls);
  } finally { chat.remove(); globalThis.fetch = original; }
}

function send(chat, text) {
  chat.$('textarea').value = text;
  chat.$('form').requestSubmit();
}
async function complete(chat) { await waitFor(() => chat.$('.status').textContent.startsWith('Complete')); }

export const tests = [
  ['connect applies destination and token before health, even when default API is unavailable', () => fixture(async (chat, calls) => {
    calls.length = 0;
    await chat.connect('http://127.0.0.1:8999', 'new-token');
    assert(calls.length > 0);
    assert(calls.every(c => c.url.startsWith('http://127.0.0.1:8999/v1/') && c.options.headers.Authorization === 'Bearer new-token'));
    send(chat, 'hello'); await complete(chat);
    const post = calls.find(c => c.options.method === 'POST');
    assert(!JSON.parse(post.options.body).conversation_id);
  }, {fetchImpl: async (url, options) => {
    if (!url.startsWith('http://127.0.0.1:8999/')) return new Response('{}', {status: 404});
    assert(options.headers.Authorization === 'Bearer new-token');
    return url.endsWith('/health') ? new Response('{"persistence_enabled":false}') : response();
  }})],
  ['connect detaches old conversation without contacting its endpoint or leaking credentials', () => fixture(async (chat, calls) => {
    chat.bearerToken = 'old-token';
    send(chat, 'old turn'); await complete(chat);
    calls.length = 0;
    await chat.connect('http://127.0.0.1:8999', 'new-token');
    assert(chat.$('.messages').children.length === 0);
    send(chat, 'new turn'); await complete(chat);
    assert(calls.every(c => c.url.startsWith('http://127.0.0.1:8999/v1/') && c.options.headers.Authorization === 'Bearer new-token'));
    assert(!calls.some(c => c.options.method === 'DELETE'));
    assert(!JSON.parse(calls.find(c => c.options.method === 'POST').options.body).conversation_id);
  })],
  ['connect validates before mutation and preserves same-settings ephemeral reset', () => fixture(async (chat, calls) => {
    send(chat, 'old turn'); await complete(chat);
    calls.length = 0;
    await rejects(() => chat.connect('ftp://127.0.0.1', 'token'));
    await rejects(() => chat.connect('http://127.0.0.1:8999', 'bad\ntoken'));
    assert(calls.length === 0 && chat.$('.messages').children.length === 2);
    await chat.connect(location.origin);
    assert(calls.some(c => c.options.method === 'DELETE' && c.url.endsWith(id)));
    assert(chat.$('.messages').children.length === 0);
  })],
  ['local passages UI reports supply without claiming correctness', () => fixture(async (chat,calls) => {
    await waitFor(() => !chat.$('.retrieval-setting').hidden);
    assert(!chat.$('.use-retrieval').checked);
    chat.$('.use-retrieval').checked = true;
    send(chat,'local question'); await complete(chat);
    assert(JSON.parse(calls.find(c => c.options.method === 'POST').options.body).retrieval === 'auto');
    assert(chat.$('.retrieval-status').textContent.includes('1 local passages supplied'));
    assert(chat.$('.retrieval-status').textContent.includes('does not verify'));
  }, {fetchImpl: async url => url.endsWith('/health') ? new Response('{"retrieval_enabled":true}') :
      response(frame('started',{conversation_id:id,dropped_turns:0,retrieval:{status:'supplied',sources:[{}]}}) + frame('delta',{text:'OK'}) + done)})],
  ['project index relabels the retrieval option; plain indexes keep the M6 label', async () => {
    for (const [health, label] of [[{retrieval_enabled: true, project_snapshot: {project_id: 'p', name: 'P', snapshot_id: 's', indexed_at: 't', freshness: 'not_checked'}}, 'Use local project context'],
                                   [{retrieval_enabled: true}, 'Use local documents']]) {
      await fixture(async chat => {
        await waitFor(() => !chat.$('.retrieval-setting').hidden);
        assert(chat.$('.retrieval-setting').textContent.trim() === label);
        assert(!chat.$('.use-retrieval').checked);
      }, {fetchImpl: async url => url.endsWith('/health') ? new Response(JSON.stringify(health)) : response()});
    }
  }],
  ['Reach has a deployment-gated opt-in and exact supplied source links', () => fixture(async (chat,calls) => {
    await waitFor(() => !chat.$('.reach-setting').hidden);
    assert(!chat.$('.use-reach').checked);
    chat.$('.use-reach').checked = true;
    send(chat, 'latest python'); await complete(chat);
    const post=JSON.parse(calls.find(c=>c.options.method==='POST').options.body);
    assert(post.reach === 'auto');
    const receipt = chat.$('.assistant:last-child .reach-receipt');
    assert(receipt.textContent.includes('latest version python'));
    assert(receipt.textContent.includes('does not verify'));
    assert(chat.shadowRoot.querySelectorAll('.reach-receipt').length === 1);
    assert(receipt.parentElement.classList.contains('bubble'));
    assert(!chat.$('.reach-status'));
    const link=chat.$('.assistant:last-child .reach-receipt a');
    assert(link.textContent === 'Referenced from Wikipedia — <Python>');
    assert(link.href === 'https://en.wikipedia.org/wiki/Python' && link.rel.includes('noopener'));
    assert(!chat.shadowRoot.querySelector('Python'));
    await chat.resetConversation(); assert(!chat.$('.reach-receipt'));
  }, {fetchImpl: async (url,options) => options.method === 'DELETE' ? new Response(null,{status:204}) : url.endsWith('/health') ? new Response('{"reach_enabled":true,"reach_default":"off"}') :
      response(frame('started', {conversation_id: id, dropped_turns: 0, reach: {state:'supplied',attempted:true,reason:'supplied',provider:'wikipedia',
        query: 'latest version python', sources: [{title: '<Python>', url: 'https://en.wikipedia.org/wiki/Python'}]}}) +
        frame('delta', {text: 'OK'}) + done)})],
  ['Reach status stays separate from local status and never invents a supplied link', async () => {
    for (const state of ['disabled','not_attempted','unavailable','not_supplied']) {
      await fixture(async chat => {
        send(chat,'hello'); await complete(chat);
        const receipt = chat.$('.reach-receipt');
        assert(!!receipt === !['disabled', 'not_attempted'].includes(state));
        assert(!chat.shadowRoot.querySelector('.reach-receipt a'));
        assert(chat.$('.retrieval-status').hidden);
        assert(chat.$('.reach-setting').hidden);
      }, {fetchImpl: async url=>url.endsWith('/health')?new Response('{}'):
        response(frame('started',{conversation_id:id,dropped_turns:0,reach:{state,attempted:false,reason:'control',sources:[]}})+frame('delta',{text:'OK'})+done)});
    }
  }],
  ['auto default starts checked, opt-out sends false, and status stays truthful', async () => {
    const statuses = [{mode: 'auto', attempted: false, status: 'not_used', reason: 'conversational', sources: []},
                      {mode: 'auto', attempted: true, status: 'not_used', reason: 'weak_match', sources: []},
                      {mode: 'auto', attempted: true, status: 'unavailable', reason: 'retrieval_busy', sources: []}];
    let turn = 0;
    await fixture(async (chat, calls) => {
      await waitFor(() => !chat.$('.retrieval-setting').hidden);
      assert(chat.$('.use-retrieval').checked);
      send(chat, 'hello'); await complete(chat);
      assert(chat.$('.retrieval-status').hidden);
      send(chat, 'general question'); await complete(chat);
      assert(chat.$('.retrieval-status').textContent === 'Local material checked; none used.');
      send(chat, 'project question'); await complete(chat);
      assert(chat.$('.retrieval-status').textContent === 'Local project information was unavailable.');
      chat.$('.use-retrieval').checked = false;
      send(chat, 'off'); await complete(chat);
      const bodies = calls.filter(c => c.options.method === 'POST').map(c => JSON.parse(c.options.body).retrieval);
      assert(JSON.stringify(bodies) === JSON.stringify(['auto', 'auto', 'auto', false]));
    }, {fetchImpl: async url => url.endsWith('/health') ? new Response('{"retrieval_enabled":true,"retrieval_default":"auto"}') :
        response(frame('started', {conversation_id: id, dropped_turns: 0, ...(turn < 3 ? {retrieval: statuses[turn++]} : {})}) + frame('delta', {text: 'OK'}) + done)});
  }],
  ['persistent new preserves saved ID remotely and manual resume uses it', () => fixture(async (chat, calls) => {
    await waitFor(() => !chat.$('.persistence').hidden);
    assert(chat.$('.persistence').open);
    send(chat, 'first'); await complete(chat);
    assert(chat.$('.conversation-id').value === id);
    await chat.newConversation();
    assert(!calls.some(c => c.options.method === 'DELETE'));
    assert(chat.$('.messages').children.length === 0);
    chat.resumeConversation(id);
    send(chat, 'resumed'); await complete(chat);
    assert(JSON.parse(calls.filter(c => c.options.method === 'POST').at(-1).options.body).conversation_id === id);
    chat.$('.delete').click();
    assert(!chat.$('.delete-confirm').hidden);
    assert(!calls.some(c => c.options.method === 'DELETE'));
    chat.$('.confirm-delete').click();
    await waitFor(() => chat.$('.conversation-id').value === '');
    assert(calls.some(c => c.options.method === 'DELETE'));
  }, {fetchImpl: async (url, options) => url.endsWith('/health') ? new Response('{"persistence_enabled":true}') :
      options.method === 'DELETE' ? new Response(null, {status: 204}) : response()})],
  ['floating persistence controls start in a compact keyboard disclosure', () => fixture(async chat => {
    chat.setAttribute('open', '');
    await waitFor(() => !chat.$('.persistence').hidden);
    assert(!chat.$('.persistence').open && chat.$('.persistence summary').textContent === 'Saved conversation');
    assert(chat.$('.resume-id').closest('label'));
  }, {attributes: {}, fetchImpl: async () => new Response('{"persistence_enabled":true}')})],
  ['component sends and retains ID over separate turns', () => fixture(async (chat, calls) => {
    send(chat, 'first'); await complete(chat); send(chat, 'second'); await complete(chat);
    const posts = calls.filter(c => c.options.method === 'POST');
    assert(posts.length === 2 && JSON.parse(posts[1].options.body).conversation_id === id);
    assert(chat.$('.messages').children.length === 4);
  })],
  ['model HTML remains literal text', () => fixture(async chat => {
    send(chat, '<script>evil()</script>'); await complete(chat);
    assert(chat.$('.assistant .content').textContent === '<img src=x onerror=evil()>');
    assert(!chat.$('.assistant .content').querySelector('img'));
    assert(!chat.$('.user .content').querySelector('script'));
  }, {fetchImpl: async url => url.endsWith('/health') ? new Response('{}') : response(start + frame('delta', {text: '<img src=x onerror=evil()>'}) + done)})],
  ['host selectors do not cross shadow boundary', () => fixture(async chat => {
    const style = document.createElement('style');
    style.textContent = 'button {background:rgb(255,0,255)!important;border:20px solid red!important} textarea {font-size:60px!important} h2 {font-size:60px!important}';
    document.head.append(style);
    try {
      assert(getComputedStyle(chat.$('.send')).backgroundColor !== 'rgb(255, 0, 255)');
      assert(getComputedStyle(chat.$('textarea')).fontSize === '15px');
      assert(getComputedStyle(chat.$('h2')).fontSize === '18px');
    } finally { style.remove(); }
  })],
  ['small personalization contract', () => fixture(async chat => {
    chat.setAttribute('display-name', '<b>Helper</b>'); chat.setAttribute('placeholder', 'Your question');
    chat.setAttribute('hide-branding', ''); chat.setAttribute('hide-avatar', '');
    chat.style.setProperty('--dwindy-primary', '#123456');
    chat.style.setProperty('--dwindy-accent', '#abcdef');
    assert(chat.$('h2').textContent === '<b>Helper</b>' && !chat.$('h2').querySelector('b'));
    assert(chat.$('.branding').hidden && chat.$('.header-avatar').hidden);
    assert(chat.$('textarea').placeholder === 'Your question');
    assert(getComputedStyle(chat.$('h2')).color === 'rgb(18, 52, 86)');
    assert(getComputedStyle(chat.$('.send')).backgroundColor === 'rgb(171, 205, 239)');
  })],
  ['host artwork local-only and shared', () => fixture(async chat => {
    chat.setAttribute('avatar-src', '/custom.png');
    assert(chat.$('.header-avatar').src === location.origin + '/custom.png');
    chat.setAttribute('avatar-src', 'https://external.invalid/tracker.png');
    assert(chat.$('.header-avatar').src.endsWith('dwindy-idle.png'));
  })],
  ['working only while processing; stop requires fresh conversation', async () => {
    let streamController;
    await fixture(async chat => {
      send(chat, 'hello'); await waitFor(() => streamController);
      const base = chat.getAttribute('api-base');
      await rejects(() => chat.connect('http://127.0.0.1:8999', 'new-token'));
      assert(chat.getAttribute('api-base') === base);
      assert(chat.$('.header-avatar').src.endsWith('dwindy-working.png'));
      chat.$('.send').click();
      await waitFor(() => chat.$('.send').textContent === 'Send');
      assert(chat.$('.send').disabled && !chat.$('.reset').disabled);
      assert(chat.$('.header-avatar').src.endsWith('dwindy-idle.png'));
      assert(chat.$('textarea').value === 'hello');
      await chat.resetConversation(); assert(!chat.$('.send').disabled);
    }, {fetchImpl: async (url, options) => {
      if (url.endsWith('/health')) return new Response('{}');
      if (options.method === 'DELETE') return new Response(null, {status: 204});
      return new Response(new ReadableStream({start(controller) {
        streamController = controller;
        controller.enqueue(new TextEncoder().encode(start));
        options.signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')));
      }}), {headers: {'Content-Type': 'text/event-stream'}});
    }});
  }],
  ['reset uses DELETE before clearing transcript', () => fixture(async (chat, calls) => {
    send(chat, 'hello'); await complete(chat);
    await chat.resetConversation();
    assert(calls.some(c => c.options.method === 'DELETE' && c.url.endsWith(id)));
    assert(!chat.$('.messages').children.length && !chat.$('.empty').hidden);
  })],
  ['failed deletion retains transcript', () => fixture(async chat => {
    send(chat, 'hello'); await complete(chat);
    await rejects(() => chat.resetConversation());
    assert(chat.$('.messages').children.length === 2 && !chat.$('.error').hidden);
  }, {fetchImpl: async (url, options) => url.endsWith('/health') ? new Response('{}') :
    options.method === 'DELETE' ? new Response('{}', {status: 409}) : response()})],
  ['expired conversation shown explicitly with draft preserved', () => fixture(async chat => {
    send(chat, 'hello'); await waitFor(() => !chat.$('.error').hidden);
    assert(chat.$('.send').disabled && chat.$('textarea').value === 'hello');
    assert(chat.$('.error').textContent.includes('expired'));
  }, {fetchImpl: async url => url.endsWith('/health') ? new Response('{}') :
    new Response(JSON.stringify({error: {code: 'conversation_not_found', message: 'expired'}}), {status: 404})})],
  ['modal opening, initial state, Escape and focus return', () => fixture(async chat => {
    await waitFor(() => chat.$('dialog').open);
    assert(chat.$('dialog').matches(':modal'));
    assert(chat.shadowRoot.activeElement === chat.$('textarea'));
    assert(chat.$('.launcher').getAttribute('aria-expanded') === 'true');
    chat.$('dialog').dispatchEvent(new Event('cancel', {cancelable: true}));
    await waitFor(() => chat.shadowRoot.activeElement === chat.$('.launcher'));
    assert(!chat.hasAttribute('open'));
  }, {attributes: {open: '', position: 'bottom-left'}})],
  ['Enter sends; Shift and composition do not', () => fixture(async (chat, calls) => {
    const input = chat.$('textarea'); input.value = 'hello';
    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', shiftKey: true, bubbles: true, cancelable: true}));
    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', isComposing: true, bubbles: true, cancelable: true}));
    assert(!calls.some(c => c.options.method === 'POST'));
    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));
    await complete(chat);
  })],
  ['completed announcement, no per-token live transcript', () => fixture(async chat => {
    send(chat, 'hello'); await complete(chat);
    assert(chat.$('.announcement').textContent.includes('hi 🌿'));
    assert(!chat.$('.messages').hasAttribute('aria-live'));
    assert(chat.$('textarea').labels.length === 1);
  })],
  ['changing endpoint does not forward old token', () => fixture(async (chat, calls) => {
    chat.bearerToken = 'private';
    chat.setAttribute('api-base', 'http://127.0.0.1:8999');
    send(chat, 'hello'); await complete(chat);
    const post = calls.find(c => c.options.method === 'POST');
    assert(!post.options.headers.Authorization);
    chat.setAttribute('api-base', 'http://127.0.0.1:8998');
    assert(chat.getAttribute('api-base') === 'http://127.0.0.1:8999');
    await rejects(async () => { chat.bearerToken = 'different'; });
  })],
  ['display retention is bounded without API history replay', () => fixture(async (chat, calls) => {
    for (let n = 0; n < 52; n++) { send(chat, `turn ${n}`); await complete(chat); }
    assert(chat.$('.messages').children.length === 100 && !chat.$('.pruned').hidden);
    const last = JSON.parse(calls.filter(c => c.options.method === 'POST').at(-1).options.body);
    assert(Object.keys(last).length === 3 && last.conversation_id === id);
  })],
  ['component removal aborts pending request', async () => {
    let aborted = false;
    await fixture(async chat => {
      send(chat, 'hello'); chat.remove();
      await waitFor(() => aborted);
    }, {fetchImpl: async (url, options) => {
      if (url.endsWith('/health')) return new Response('{}');
      return new Promise((resolve, reject) => options.signal.addEventListener('abort', () => {
        aborted = true; reject(new DOMException('Aborted', 'AbortError'));
      }));
    }});
  }],
];
