// sw-bridge.js — route service-worker messages to page-side sync handlers.  P2.
//
// The service worker can drain the push queue itself, but the read-side pull
// needs an auth token that lives only in the page — so after a Background Sync
// the worker posts a message and the page (which has the token) runs the pull.
// This is the page half of that bridge: it subscribes to the SW message channel
// and dispatches each known message type to an injected handler.
//
// Message contract (posted by client/sw/sw.js):
//   OFFLINE_QUEUE_DRAINED  — the worker drained the push queue; refresh counts.
//   OFFLINE_PULL           — reconcile now by pulling remote changes.
//   REPLAY_OFFLINE_QUEUE   — fallback: the worker couldn't drain; the page should.
//   DEEP_LINK              — a notification click routed here (handled elsewhere).

/** The message types the service worker posts to the page. */
export const SW_MESSAGES = Object.freeze({
  DRAINED: "OFFLINE_QUEUE_DRAINED",
  PULL: "OFFLINE_PULL",
  REPLAY: "REPLAY_OFFLINE_QUEUE",
  DEEP_LINK: "DEEP_LINK",
});

/**
 * Subscribe to service-worker messages and dispatch them to handlers by type.
 *
 * Degrades gracefully: returns a no-op teardown when service workers are
 * unavailable. Unknown message types are ignored.
 *
 * @param {Record<string, (data: Object) => void>} [handlers]
 *        Map of message `type` → handler (e.g. `{ [SW_MESSAGES.PULL]: fn }`).
 * @param {Object} [deps]
 * @param {ServiceWorkerContainer} [deps.container]
 *        Override navigator.serviceWorker (tests).
 * @returns {() => void} A teardown that removes the listener.
 */
export function installSyncBridge(handlers = {}, deps = {}) {
  const container =
    deps.container ??
    (typeof navigator !== "undefined" && navigator.serviceWorker
      ? navigator.serviceWorker
      : null);
  if (!container || typeof container.addEventListener !== "function") {
    return () => {};
  }
  const onMessage = (event) => {
    const data = event && event.data;
    if (!data || typeof data.type !== "string") return;
    const handler = handlers[data.type];
    if (typeof handler === "function") handler(data);
  };
  container.addEventListener("message", onMessage);
  return () => container.removeEventListener("message", onMessage);
}
