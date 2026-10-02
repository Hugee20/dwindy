import './dwindy-chat.js';
import {apiBase} from './api-client.js';
const chat = document.querySelector('dwindy-chat');
const base = document.querySelector('#api-base');
const token = document.querySelector('#api-token');
const status = document.querySelector('#connection-status');
base.value = location.origin;
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
