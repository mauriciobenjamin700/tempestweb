// livereload.js — dev-only auto-reload over Server-Sent Events.
//
// Injected into the served index.html by the dev server (`tempestweb dev`) and
// NEVER bundled into a production build. It opens an EventSource to the dev
// server's `/__livereload` endpoint; when a watched file changes the server
// rebuilds the artifact and emits a `reload` event, and this reloads the tab so
// the fresh bundle (Mode A) or fresh app (Mode B) takes effect.
//
// JSDoc-typed, pure JS, no build step — same conventions as the rest of client/.

/**
 * Connect to the dev server's livereload stream and reload on each `reload`
 * event. The browser's EventSource reconnects automatically if the dev server
 * restarts, so a server bounce just resumes the stream.
 *
 * @param {string} [url]  The SSE endpoint. Defaults to "/__livereload".
 * @returns {EventSource}  The open EventSource (so callers can close it in tests).
 */
export function connectLiveReload(url = "/__livereload") {
  const source = new EventSource(url);
  source.addEventListener("reload", () => {
    // A rebuild completed server-side before this event fired; reload to pick it
    // up. location.reload() re-fetches index.html and every (cache-busted) asset.
    globalThis.location.reload();
  });
  return source;
}

connectLiveReload();
