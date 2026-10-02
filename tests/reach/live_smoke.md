# Optional live-provider smoke (not scored)

This check is separate from the frozen benchmark. It never runs in the automated test suite or
CI. It is run deliberately by a person, with Reach enabled in a scratch deployment, to observe
behavior the replayed snapshot cannot show. Results are recorded in the M10 validation report,
not used for adoption decisions.

## Procedure

1. Configure a scratch API with `reach_provider = "wikipedia"` and `reach_default = "auto"`, and
   no other deployment changes.
2. Ask three freshness questions: "What is the latest version of Python?", "Who is the current
   President of the Philippines?" and "What is the newest Android version?". Then ask one
   control: "What is photosynthesis?".
3. For each, record:
   - the exact minimized query reported in the metadata;
   - whether one request was made, and none for the control;
   - the HTTP status;
   - the elapsed time of the Reach step and the time to first visible text;
   - the result titles and URLs;
   - whether the browser showed "Searched externally for: …".

## What must hold

- **Requests:**
  - HTTPS only, with certificate verification on and never disabled;
  - a User-Agent identifying Dwindy;
  - no cookies stored;
  - no redirects followed.
- **Bounds:** each Reach step finishes within 5 seconds or fails closed to the offline path.
- **Transparency:** the metadata query equals the query actually sent, character for character.
- **Rate limits:** a 429 or other provider error leads to `reach_unavailable` and the offline
  path, never a crash or retry storm.

## Observations already recorded during fixture capture (2026-10-02)

These came from the one-off capture script, not from Dwindy runtime code.

- **TLS trust.** On the reference machine (Windows 11, Python 3.13.0, OpenSSL 3.0.15), verifying
  `en.wikipedia.org` against the Windows certificate store as Python loads it fails with
  "certificate has expired". Verifying against the `certifi` CA bundle succeeds, and so does
  `curl`, which uses Windows' native TLS stack. A standard-library-only client with default
  settings would therefore fail on the reference machine. The trust approach is an
  implementation-phase Capability Density decision. Disabling verification is never acceptable.
- **Rate limiting.** Anonymous requests at about one per second received HTTP 429 after 8
  requests. A pause of about 6 seconds per request, honoring `Retry-After`, completed the capture.
  The reference provider throttles quickly, which matters for deployments serving several users.
