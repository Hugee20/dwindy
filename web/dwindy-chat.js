import {ChatClient, apiBase} from './api-client.js';

const asset = name => new URL(`../assets/${name}`, import.meta.url).href;
const idle = asset('chatheads/dwindy-idle.png');
const working = asset('chatheads/dwindy-working.png');

export class DwindyChat extends HTMLElement {
  static observedAttributes = ['api-base', 'display-name', 'hide-branding', 'hide-avatar', 'position', 'open', 'placeholder', 'avatar-src'];
  #client; #token = ''; #base; #busy = false; #resetting = false; #health;
  #inline = false; #ready = false; #configuredToken; #styleReady;

  constructor() {
    super();
    const root = this.attachShadow({mode: 'open'});
    // This constant template never includes host configuration or model output.
    root.innerHTML = `
      <link rel="stylesheet">
      <button class="launcher" type="button" aria-haspopup="dialog" aria-controls="dialog" aria-expanded="false">
        <img alt=""><span class="launcher-symbol" aria-hidden="true">✦</span>
      </button>
      <dialog id="dialog" aria-labelledby="heading"></dialog>
      <section class="panel" aria-labelledby="heading">
        <header><div class="identity"><img class="header-avatar" alt=""><div><h2 id="heading"></h2><span class="subtitle">A little room to think.</span></div></div>
          <div class="actions"><button class="reset" type="button">New conversation</button><button class="close" type="button" aria-label="Close chat">×</button></div>
        </header>
        <div class="transcript" role="region" aria-label="Conversation" tabindex="0">
          <div class="empty"><img alt=""><h3>Hello. What’s on your mind?</h3><p>Ask a question, explore an idea, or work through a thought.</p></div>
          <p class="pruned" hidden>Older messages were removed from this display.</p>
          <ol class="messages" aria-label="Messages"></ol>
        </div>
        <button class="latest" type="button" hidden>Jump to latest</button>
        <p class="status" role="status" aria-live="polite" aria-atomic="true">Ready when you are.</p>
        <p class="error" role="alert" hidden></p>
        <form><label for="message">Message <span class="assistant-name"></span></label>
          <div class="composer"><textarea id="message" rows="2" maxlength="60000"></textarea><button class="send" type="submit">Send</button></div>
          <p class="hint">Enter to send · Shift+Enter for a new line</p>
        </form>
        <footer class="branding">Powered by <img alt="Dwindy"></footer>
        <span class="announcement sr-only" role="status" aria-live="polite" aria-atomic="true"></span>
      </section>`;
    const style = root.querySelector('link');
    this.#styleReady = new Promise(resolve => {
      style.addEventListener('load', () => resolve(true), {once: true});
      style.addEventListener('error', () => resolve(false), {once: true});
    });
    style.href = new URL('./dwindy-chat.css', import.meta.url).href;
    this.$('.branding img').src = asset('branding/dwindy-wordmark.png');
    this.$('.launcher').addEventListener('click', () => this.setAttribute('open', ''));
    this.$('.close').addEventListener('click', () => this.removeAttribute('open'));
    this.$('dialog').addEventListener('cancel', event => { event.preventDefault(); this.removeAttribute('open'); });
    this.$('dialog').addEventListener('close', () => {
      this.removeAttribute('open'); this.$('.launcher').setAttribute('aria-expanded', 'false');
      if (this.isConnected) this.$('.launcher').focus();
    });
    this.$('form').addEventListener('submit', event => { event.preventDefault(); this.#submit(); });
    this.$('textarea').addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
        event.preventDefault(); if (!this.#busy) this.#submit();
      }
    });
    this.$('.reset').addEventListener('click', () => this.resetConversation().catch(() => {}));
    this.$('.latest').addEventListener('click', () => this.#scroll());
    this.$('.transcript').addEventListener('scroll', () => {
      if (this.#nearBottom()) this.$('.latest').hidden = true;
    });
  }

  $(selector) { return this.shadowRoot.querySelector(selector); }

  connectedCallback() {
    if (!this.#ready) {
      this.#inline = this.getAttribute('presentation') === 'inline';
      this.setAttribute('data-presentation', this.#inline ? 'inline' : 'floating');
      if (!this.#inline) this.$('dialog').append(this.$('.panel'));
      this.#ready = true;
    }
    try { this.#configure(); } catch (error) { this.#error(error); }
    this.#personalize();
    this.#open();
    if (this.#inline) this.#checkHealth();
  }

  disconnectedCallback() {
    this.#health?.abort();
    this.#client?.stop();
    if (this.$('dialog').open) this.$('dialog').close();
  }

  attributeChangedCallback(name, oldValue, value) {
    if (!this.#ready || oldValue === value) return;
    if (name === 'api-base') {
      try {
        if (this.#busy || this.#resetting || this.#client?.conversationId || this.#client?.uncertain) throw Error('Start a new conversation before changing API destination.');
        apiBase(value || location.origin); // Reject before altering credentials.
        this.#token = ''; // Never forward an old credential to a different destination.
        this.#configure();
      } catch (error) {
        this.#error(error);
        if (value !== oldValue) {
          // Restore without re-entering connection configuration.
          this.#ready = false;
          if (oldValue === null) this.removeAttribute(name); else this.setAttribute(name, oldValue);
          this.#ready = true;
        }
      }
    }
    this.#personalize();
    if (name === 'open') this.#open();
  }

  set bearerToken(value) {
    if (typeof value !== 'string' || /[\r\n]/.test(value)) throw Error('Invalid bearer token.');
    if (this.#busy || this.#resetting || this.#client?.conversationId || this.#client?.uncertain) throw Error('Start a new conversation before changing credentials.');
    this.#token = value;
    if (this.isConnected) this.#configure();
  }

  #configure() {
    const base = apiBase(this.getAttribute('api-base') || location.origin);
    if (this.#client && base === this.#base && this.#configuredToken === this.#token) return;
    this.#health?.abort();
    this.#base = base; this.#configuredToken = this.#token;
    this.#client = new ChatClient({base, token: this.#token});
    this.$('.error').hidden = true;
    this.$('.status').textContent = 'Connection ready to use. Send a message to begin.';
  }

  #personalize() {
    const name = this.getAttribute('display-name')?.trim() || 'Dwindy';
    this.$('h2').textContent = name;
    this.$('.assistant-name').textContent = name;
    this.$('textarea').placeholder = this.getAttribute('placeholder') || `Ask ${name}…`;
    this.$('.launcher').setAttribute('aria-label', `Open ${name} chat`);
    this.$('.branding').hidden = this.hasAttribute('hide-branding');
    this.$('.close').hidden = this.#inline;
    this.$('.launcher').hidden = this.#inline;
    this.#avatars();
  }

  #avatarSource() {
    const custom = this.getAttribute('avatar-src');
    if (custom) {
      try {
        const url = new URL(custom, document.baseURI);
        if (url.origin === location.origin && ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) return url.href;
      } catch { /* Invalid host artwork uses canonical artwork. */ }
    }
    return this.#busy ? working : idle;
  }

  #avatars() {
    const hidden = this.hasAttribute('hide-avatar');
    for (const img of this.shadowRoot.querySelectorAll('.launcher img, .header-avatar, .empty img')) {
      img.hidden = hidden; img.src = this.#avatarSource();
      img.onerror = () => { img.hidden = true; if (img.closest('.launcher')) this.$('.launcher-symbol').hidden = false; };
    }
    this.$('.launcher-symbol').hidden = !hidden;
    for (const img of this.shadowRoot.querySelectorAll('.message-avatar')) {
      img.hidden = hidden;
      img.src = this.getAttribute('avatar-src') ? this.#avatarSource() : idle;
    }
  }

  async #open() {
    if (this.#inline || !this.isConnected) return;
    const dialog = this.$('dialog');
    if (!this.hasAttribute('open')) { if (dialog.open) dialog.close(); return; }
    const styled = await this.#styleReady;
    if (!this.isConnected || !this.hasAttribute('open') || dialog.open) return;
    if (!styled) { this.#error(Error('Chat styles could not load. Check the asset paths and page policy.')); }
    dialog.showModal();
    this.$('.launcher').setAttribute('aria-expanded', 'true');
    this.$('textarea').focus();
    this.#checkHealth();
  }

  async #checkHealth() {
    if (!this.#client || this.#busy || this.#client.uncertain) return;
    this.#health?.abort(); const controller = new AbortController(); this.#health = controller;
    try {
      const health = await this.#client.health(controller.signal);
      if (!controller.signal.aborted && !this.#busy && !this.#client.uncertain)
        this.$('.status').textContent = health.busy ? 'Dwindy is busy with another request.' : 'Ready when you are.';
    } catch (error) { if (!controller.signal.aborted && !this.#busy) this.#error(error); }
  }

  #error(error) {
    const descriptions = {
      unauthorized: 'A valid API token is required. Check your connection settings.',
      conversation_busy: 'The previous request is still finishing. Wait, then try New conversation again.',
      backend_busy: 'Dwindy is busy. Your message was not sent; try again shortly.',
      conversation_capacity: 'The server has reached its conversation limit. Delete an unused conversation or wait for expiry.',
      conversation_not_found: 'This conversation expired or the server restarted. Start a new conversation.',
      context_limit: 'This message cannot fit the model context. Shorten it and try again.',
      request_too_large: 'This message is too large for the API. Shorten it and try again.',
    };
    let text = error.name === 'AbortError' ? 'Stopped. Completion delivery is uncertain.' :
      descriptions[error.code] || (error instanceof TypeError ? 'Cannot reach the API. Check its address, server, allowed Origin and browser network permissions.' : error.message);
    if (this.#client?.uncertain) text += ' Start a new conversation before sending again.';
    this.$('.error').textContent = text;
    this.$('.error').hidden = false;
  }

  #controls() {
    this.$('.transcript').setAttribute('aria-busy', String(this.#busy));
    this.$('textarea').readOnly = this.#busy || this.#resetting;
    this.$('.send').textContent = this.#busy ? 'Stop' : 'Send';
    this.$('.send').disabled = this.#resetting || (!this.#busy && (!this.#client || this.#client.uncertain));
    this.$('.reset').disabled = this.#busy || this.#resetting;
    this.#avatars();
  }

  #nearBottom() {
    const pane = this.$('.transcript');
    return pane.scrollHeight - pane.scrollTop - pane.clientHeight < 72;
  }
  #scroll() { const pane = this.$('.transcript'); pane.scrollTop = pane.scrollHeight; this.$('.latest').hidden = true; }

  #message(role, text) {
    const li = document.createElement('li'); li.className = role;
    if (role === 'assistant') {
      const img = document.createElement('img'); img.className = 'message-avatar'; img.alt = '';
      img.src = this.#avatarSource(); img.hidden = this.hasAttribute('hide-avatar'); li.append(img);
    }
    const bubble = document.createElement('div'); bubble.className = 'bubble';
    const label = document.createElement('span'); label.className = 'sr-only';
    label.textContent = role === 'user' ? 'You: ' : `${this.getAttribute('display-name') || 'Dwindy'}: `;
    const content = document.createElement('span'); content.className = 'content'; content.textContent = text;
    const note = document.createElement('small'); note.className = 'note';
    bubble.append(label, content, note); li.append(bubble); this.$('.messages').append(li);
    return {li, content, note};
  }

  async #submit() {
    if (this.#busy) { this.#client.stop(); this.$('.status').textContent = 'Stopping…'; return; }
    if (this.#resetting || !this.#client || this.#client.uncertain) return;
    const input = this.$('textarea'), message = input.value;
    if (!message.trim()) return;
    this.#health?.abort(); this.#busy = true; this.#controls();
    this.$('.error').hidden = true; this.$('.empty').hidden = true;
    this.$('.status').textContent = 'Generating…';
    const user = this.#message('user', message), assistant = this.#message('assistant', '');
    input.value = ''; this.#scroll();
    let complete = false, dropped = 0;
    try {
      for await (const item of this.#client.chat(message)) {
        if (item.event === 'started') dropped = item.data.dropped_turns;
        if (item.event === 'delta') {
          const follow = this.#nearBottom();
          const available = Math.max(0, 65536 - assistant.content.textContent.length);
          assistant.content.append(document.createTextNode(item.data.text.slice(0, available)));
          if (item.data.text.length > available) assistant.note.textContent = 'Display limit reached; additional text is not shown.';
          if (follow) this.#scroll(); else this.$('.latest').hidden = false;
        }
        if (item.event === 'completed') {
          complete = true;
          if (item.data.finish_reason === 'length') assistant.note.textContent += ' Response reached its output limit.';
          this.$('.status').textContent = dropped ? `Complete. ${dropped} older turn(s) were omitted from model context.` : 'Complete.';
          this.$('.announcement').textContent = `${this.getAttribute('display-name') || 'Dwindy'}: ${assistant.content.textContent}`;
        }
      }
    } catch (error) {
      user.note.textContent = 'Unsuccessful or interrupted attempt.';
      assistant.note.textContent = 'Incomplete response; do not assume this turn was retained.';
      if (!assistant.content.textContent) assistant.content.textContent = 'No completed answer received.';
      input.value = message;
      this.$('.status').textContent = 'Request ended.'; this.#error(error);
    } finally {
      this.#busy = false; this.#controls(); this.#prune();
      if (!complete) this.$('.announcement').textContent = 'No completed answer received.';
    }
  }

  #prune() {
    const list = this.$('.messages');
    while (list.children.length > 100 || (list.textContent.length > 200000 && list.children.length > 2)) {
      list.firstElementChild.remove(); list.firstElementChild?.remove();
      this.$('.pruned').hidden = false;
    }
  }

  async resetConversation() {
    if (!this.#client || this.#busy || this.#resetting) throw Error('Wait for the active operation to finish.');
    this.#resetting = true; this.#controls(); this.#health?.abort();
    try {
      await this.#client.reset();
      this.$('.messages').replaceChildren(); this.$('.empty').hidden = false;
      this.$('.pruned').hidden = true; this.$('.latest').hidden = true; this.$('.error').hidden = true;
      this.$('.announcement').textContent = '';
      this.$('.status').textContent = 'New conversation. Previous context has been cleared.';
    } catch (error) { this.#error(error); throw error; }
    finally { this.#resetting = false; this.#controls(); }
  }
}

if (!customElements.get('dwindy-chat')) customElements.define('dwindy-chat', DwindyChat);
