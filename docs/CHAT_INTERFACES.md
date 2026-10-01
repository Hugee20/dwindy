# Chat interfaces through M7

The standalone page and embeddable widget share one dependency-free `<dwindy-chat>`
custom element with open Shadow DOM. The floating presentation uses a native modal
`dialog`; the standalone presentation is inline. Both call only the public HTTP API.
No Node, npm, build step, framework, CDN, external font, Markdown renderer or runtime
frontend dependency is needed. There is no browser persistence, account system or SDK.

## Optional local documents (M6)

When health reports `retrieval_enabled: true`, both presentations expose a small, labeled
"Use local documents" checkbox. It starts unchecked, is held only in component memory,
and is disabled during a request. Each enabled request sends `retrieval: true` to the same
public chat endpoint. An unchecked request keeps the previous request body shape.
When health also reports a `project_snapshot` (M7), the same checkbox is labeled
"Use local project context"; its behavior is otherwise identical.

The current turn's status reports "N local passages supplied. This does not verify the
answer.", "No matching local passages found.", or that matching passages did not fit the
budget. Status uses a live region and textContent; model/document text is never interpreted
as HTML. A failed/cancelled request can have supplied passages without producing a completed
answer. The status is cleared before another request or transcript reset.

There is no ingestion control, source browser, document link renderer, persistent evidence
trail or verified-grounding badge. Existing credentials, CORS, cancellation, persistence,
personalization and idle/working mascot behavior are unchanged. See [retrieval](RETRIEVAL.md).

## Run the standalone page

From a source checkout with the existing optional API dependencies installed:

```powershell
.\.venv\Scripts\python.exe -m dwindy.server --config config.local.toml --chat-root .
```

Open `http://127.0.0.1:8000/chat/`. The server redirects to
`/dwindy/web/index.html`. The normal API remains unchanged. `--chat-root` must explicitly
point to a directory containing the `web/` and `assets/` trees; the files are not
automatically discovered or bundled into the Python wheel. Hosting is disabled when
the argument is omitted. No browser is automatically launched.

The page defaults to its own origin as API base. Connection settings allow a different
HTTP(S) base and an optional bearer token. In ephemeral mode, reconnection first deletes the old conversation
using its old credentials. In persistent mode it detaches without deleting saved turns. It will not silently abandon a failed deletion or send old
credentials to a new destination. If the old server is unreachable or its token revoked,
reload the page to abandon local state; the old server conversation remains until expiry
or explicit deletion by an authorized client. A token input is cleared after connection.
Browser/password-manager behavior is outside Dwindy's control; Dwindy does not save it.

Static hosting publicly exposes only the six required HTML/JS/CSS files and the four
used PNGs, plus the entry redirect. GET/HEAD of those exact paths bypasses bearer
authentication so a browser can bootstrap. Host, Origin and exposure policy checks still
apply. `/v1/*` and `/openapi.json` retain M3 authentication. There is no directory listing,
repository mount, test-page hosting, arbitrary file route, or config/model-file exposure.
Resolved assets outside the selected bundle are rejected. Static responses include
no-store, no-referrer, nosniff and a restrictive content policy. The official page allows
HTTP(S) connection destinations because the user can explicitly choose an API base.

## Copy into another web application

Copy the six runtime files from `web/` and the four runtime assets below, preserving
their relative layout. Serve them from the host application's existing static directory:

```text
vendor/dwindy/
  web/
    index.html
    standalone.js
    standalone.css
    api-client.js
    dwindy-chat.js
    dwindy-chat.css
  assets/
    branding/dwindy-lockup.png
    branding/dwindy-wordmark.png
    chatheads/dwindy-idle.png
    chatheads/dwindy-working.png
```

An embedded-only deployment needs the component JS/CSS, api-client.js, wordmark and
two chatheads. Keeping the complete small bundle also permits standalone use. Module,
stylesheet and default asset URLs resolve relative to the module, not the page route.
No server-side Python code or Dwindy-specific host framework package is involved.

```html
<script type="module" src="/vendor/dwindy/web/dwindy-chat.js"></script>

<dwindy-chat
  api-base="http://127.0.0.1:8000"
  display-name="Project Assistant"
  position="bottom-right"
  placeholder="Ask a question">
</dwindy-chat>
```

The **host page's origin** must be allowed by the API, including the exact scheme and
port. For a page at `http://127.0.0.1:8080`:

```toml
allowed_origins = ["http://127.0.0.1:8080"]
```

Pass that API-only TOML explicitly with `--api-config`. `localhost` and `127.0.0.1`
are different origins. Do not use `file://` pages; their null Origin is denied.
The example `web/examples/embedded.html` is an unrelated Garden Club page with
deliberately different host styles. Its initial API address is localhost port 8000.
It does not give the model any knowledge of the sample website.

Server-rendered frameworks can emit this ordinary HTML. Client frameworks can host the
custom element after loading its module, with any framework-required custom-element
configuration. No React/Vue/Angular/Svelte wrappers are supplied or claimed tested.
The element's presentation is selected before insertion; visual attributes may update
later. Reparenting a connected element aborts any active request as part of teardown.

## Personalization contract

| Attribute/property | Behavior |
|---|---|
| `api-base` | HTTP(S) origin/base prefix; defaults to page origin. No embedded URL credentials/query/fragment. |
| `bearerToken` JS setter | Optional memory-only token. No token HTML attribute or getter. |
| `display-name` | Heading, assistant and accessible labels; default Dwindy. Text only. |
| `hide-branding` | Boolean presence hides the component's Powered by Dwindy footer. |
| `hide-avatar` | Boolean presence hides mascot images; launcher uses a neutral symbol. |
| `avatar-src` | Optional same-origin host image, reused for avatar/launcher. Other origins/schemes fall back to canonical artwork. |
| `position` | `bottom-right` (default) or `bottom-left`. |
| `open` | Boolean presence opens the floating dialog. Absence closes it. |
| `presentation` | `floating` (default) or `inline`, selected before attachment. |
| `placeholder` | Composer hint; does not replace its accessible label. |

HTML boolean attributes use presence, so `open="false"` still opens the dialog.
Hiding branding does not implicitly hide the mascot. The canonical standalone page's
outer header is separate from the embedded component's footer branding.

Changing API destination or credentials requires a successful reset or explicit new
conversation first. Persistent new conversation preserves saved turns; reset deletes them. Changing
destination clears the old token; set a new token afterwards, if required. For trusted
local/private integrations, use the setter from host JavaScript after element definition:

```javascript
await customElements.whenDefined('dwindy-chat');
const chat = document.querySelector('dwindy-chat');
chat.bearerToken = tokenEnteredByTheUser; // Never a deployment secret shipped in a bundle.
```

`await chat.resetConversation()` explicitly deletes the current server conversation.
`await chat.newConversation()` preserves saved turns on a persistent server and retains
M4 reset behavior on an ephemeral server. It checks health first; failure preserves the ID.
`chat.resumeConversation(id)` attaches a saved ID while idle and fresh, on a server confirmed
as persistence-enabled. Its existence is validated by the next chat request.
Open/close can use the `open` attribute. No event bus, plugin hooks or replacement
templates are supported. The transport module is internal implementation, not a public SDK.

Four CSS custom properties form the supported color contract. For example, in the host's CSS:

```css
dwindy-chat {
  --dwindy-primary: #304a52;
  --dwindy-on-primary: #ffffff;
  --dwindy-accent: #d7b86b;
  --dwindy-on-accent: #171a10;
}
```

Defaults use primary `#4F5B2A`, white primary foreground, accent `#B8892D` and dark
accent foreground `#171A10`. Background `#D9EFBD` and surface `#F5EFE3` retain the
committed palette. Host authors are responsible for contrast of custom color pairs.
There is no arbitrary CSS injection, theme engine, internal-part styling API or asset-state map.
Open Shadow DOM is style encapsulation, not a security boundary: host scripts can inspect it.

## Assets and truthful state

Idle/completed uses `dwindy-idle.png`. While a chat request is actively processing,
the header/launcher uses `dwindy-working.png`; completed message avatars return to idle.
A custom avatar remains the host image rather than acquiring invented expression states.
Errors and cancellation use text, not emotional mascot inference. Sad, Pout, Shocked,
Dizzy and Mischievous are not loaded or activated. There are no Reach, tool, document,
provenance, reasoning-visibility or context-compaction indicators.

The original PNGs and PDFs are unchanged. The mark is byte-identical to the idle chathead,
so clients reuse idle instead of fetching a duplicate image. The standalone header uses
the lockup; the component's footer uses the wordmark. Images have empty alternative text
when decorative beside a labelled control or speaker name.

## Streaming and conversation lifecycle

Each component retains one conversation ID in memory and sends only the new message,
that ID, and `stream:true` to POST `/v1/chat`. There is no history reconstruction in JS,
model policy, prompt rewriting, or inference parameter override. Health is checked on
initial standalone attachment or opening the modal; there is no continuous background polling.

The shared fetch client incrementally decodes UTF-8 and parses SSE across arbitrary chunk
and line-ending boundaries. `started` establishes the ID and dropped-turn count, `delta`
appends text, `completed` finalizes the response and `error` reports failure. Responses
with missing completion, malformed framing or unexpected events become uncertain. A reader
is cancelled/released when iteration ends. Redirects are rejected and cookies are omitted.

All user/model strings are text nodes, with whitespace preserved. HTML and Markdown remain
literal text. No generated links, images, code execution, hidden reasoning removal or
automatic retry occurs. Nonempty length-limited answers remain visible with a limit notice.
Dropped-turn notices describe omitted model context, never summarization/compaction.

Stop aborts fetch; it cannot force native inference to end instantly. The UI requires New
conversation after uncertain cancellation because server commit may race with delivery.
Known API busy/validation failures do not cause automatic resubmission. Drafts are restored
after a failed attempt; failed transcript entries are explicitly marked.

In ephemeral mode, New conversation DELETEs a known ID before clearing the transcript. Both 204 and 404 mean
the old address no longer needs retention. On 409 or network failure, the ID/transcript are
retained and the error explains retry. If disconnection happened before the ID arrived,
there is no address the browser can delete. Ephemeral idle expiry handles that orphan;
persistent records remain saved and there is no ID recovery list in M5.
Closing the modal simply hides it and preserves an ongoing request. Removing the component
aborts requests; there is no unreliable unload DELETE or browser persistence. Reload loses
local state; persistent server records survive while cached Core state remains bounded.

Display retention is separate from server context: at most 100 message entries and roughly
200,000 characters across older displayed turns are kept. One answer displays at most
65,536 characters with an explicit display-limit note; receipt continues to completion.
The SSE parser caps buffered input at 1 MiB. These bounds do not change model generation,
Core history, evaluation output or strip reasoning tags. The composer caps input at 60,000
characters; API byte/context limits can still reject a shorter multibyte message.

## Accessibility and browser security

The composer has a persistent label. Enter sends, Shift+Enter inserts a newline, and
IME composition does not submit. Native dialog focus, Escape/Close and launcher restoration
are used. Background host controls are inert while the modal is open; browser chrome can
still receive focus according to normal native-dialog behavior. Inline mode has no modal
focus handling. Controls have visible focus and minimum 44px targets inside the component.

Status/error regions announce transitions. Streaming text itself is not a token-by-token
live region; a separate polite region announces completed answers. The transcript marks
active work with aria-busy. Scrolling follows only when near the bottom, with a Jump to
latest control otherwise. Dynamic viewport units, safe-area margins and mobile styles
support narrow windows. There is no required animation; reduced-motion disables motion.

Browser-held tokens are accessible to host scripts. **Do not publish a deployment-wide
bearer secret in HTML, JavaScript, a URL or public widget configuration.** M4 does not add
public-site accounts or an authentication proxy. Same-origin asset hosting does not grant
special API access. CORS is separate from authentication. Localhost means the browser user's
machine. Public websites reaching a local API may face browser local-network permission,
TLS/mixed-content and Content Security Policy restrictions beyond M3's Origin allowlist.

Self-host modules, styles and images. A host CSP must allow those resources and the selected
API in connect-src; no unsafe-eval is used. Standalone hosting does not make Dwindy a public
internet service. No backend secrets are embedded in served files, and frontend behavior
does not log credentials or conversation text.

## Validation

The existing M3/M4 behavioral tests remain; health assertions include the additive persistence flag. Run Python tests with the API test extra installed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The dependency-free browser tests live in `web/tests/`. They are deliberately excluded from
production static hosting. The stdlib-only test driver uses an already installed Chromium
browser over a temporary loopback DevTools connection. It does not install browser packages
or download browsers. Supply the executable explicitly, for example using its installation
path on your machine:

```powershell
$browser = Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe tests\browser_checks.py --browser $browser
.\.venv\Scripts\python.exe tests\browser_checks.py --browser $browser --config eval-results/nonthinking.config.local.toml
```

The first command uses fake inference and actual local HTTP. The second explicitly uses the
existing real-model configuration. Both test same-origin standalone and cross-origin host
deployment, dialog keyboard/focus behavior, CSS isolation, mobile viewport/reduced motion,
and the accessibility tree. Unapproved origins are tested as browser-blocked and HTTP 403.
The real-model path additionally checks recall and Stop/reset/recovery. It prints synthetic
answers; it does not save transcripts or rerun/modify the frozen M1 evaluation. Optional
`--screenshot` writes an explicitly selected screenshot; keep such artifacts outside Git.

M4 was validated on Windows/Python 3.13 with Chrome 154.0.8037.59 and Edge 154.0.4258.37.
Its Python suite passed 89 tests (81 M3 tests plus 8 static/security tests).
Its browser-native suite passed 33 tests in each browser. Additional actual-HTTP checks
exercise both hosting patterns, optional bearer authentication, denied Origin, keyboard
focus, 390px mobile emulation and standalone 200% CSS-zoom reflow.
The tested Qwen3-1.7B Q4_K_M configuration retained CEDAR across standalone requests,
streamed HELLO in the cross-origin widget, and returned FRESH after cancellation/reset.
Server conversations were deleted and the model closed after the test.

Keyboard and accessibility-tree checks do not constitute a full screen-reader audit.
Physical mobile devices, soft keyboards, Firefox and Safari remain unvalidated. The supported
integration contract is framework-neutral; individual framework integrations are not all tested.
Windows/Python's Proactor event loop occasionally logs WinError 10054 when a browser resets
a connection during navigation/abort. The tested requests and server/model cleanup still pass;
M4 does not suppress or alter M3's event loop to hide this diagnostic.


## M5 persistence controls

When health reports `persistence_enabled: true`, the component explains that completed turns
are saved unencrypted on the server. Inline chat shows a small conversation section; the
floating widget uses a collapsed native details/summary disclosure with labeled controls.
The current ID is selectable/copyable, and a Resume ID input attaches an explicitly supplied
32-character ID. Earlier transcript messages are not loaded into the display; the next POST
restores only the server's retained model context. Invalid/unknown IDs never create records.

Save the ID yourself before page reload or starting fresh. New conversation preserves the
old saved transcript but clears this component's address/display. Delete saved conversation
requires an explicit confirmation in the controls and removes all its stored turns. The
programmatic resetConversation method remains destructive without an extra browser prompt.
Changing API destination uses New semantics; old credentials are still cleared before a
new destination is configured. No automatic browser persistence, URL IDs, history list,
conversation search, transcript fetch or frontend redesign is introduced.

After uncertain cancellation, explicitly start fresh; no automatic retry occurs. The old ID
may identify a completed saved turn even if completion was not delivered. Recoverable storage
busy/full errors mean the proposed turn was rolled back; storage_unavailable is treated as
uncertain. Streaming text is provisional until completed. A failed delete preserves the ID
and display. Page reload/element removal does not delete saved conversations.

The health notice reflects the configured server at connection time; an administrator may
change storage mode on a later server restart. Consult server configuration for authoritative
privacy policy. IDs and tokens remain memory-only. All existing branding/personalization,
plain-text rendering, host isolation and public-API security boundaries remain unchanged.
