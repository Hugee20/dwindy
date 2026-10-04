import {apiBase} from './api-client.js';
const chat = document.querySelector('dwindy-chat');
const base = document.querySelector('#api-base');
const token = document.querySelector('#api-token');
const status = document.querySelector('#connection-status');
// The bundled API hosts this exact path. An independently served web/ bundle
// connects to the documented local API, rather than its static server's port.
base.value = apiBase(location.pathname === '/dwindy/web/index.html'
  ? location.origin : 'http://127.0.0.1:8000');
chat.setAttribute('api-base', base.value);
// Select the connection before upgrading the element and its initial health call.
await import('./dwindy-chat.js');
document.querySelector('#connection-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button'); button.disabled = true;
  try {
    const next = apiBase(base.value);
    await chat.connect(next, token.value);
    token.value = '';
    status.textContent = 'Connection updated. Send a message to begin.';
  } catch (error) { status.textContent = error.message; }
  finally { button.disabled = false; }
});
