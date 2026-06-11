// transport-sse.js — Mode B transport over Server-Sent Events + HTTP POST. PHASE B5.
//
// SSE is unidirectional, so the duplex Transport interface is split across two
// HTTP channels carrying the SAME wire format as transport-ws.js:
//   server -> client: an EventSource stream of { kind:"patches", ... } /
//                      { kind:"native_call", ... } envelopes (one per SSE event),
//                      plus named "ping" heartbeat events.
//   client -> server: each { kind:"event"|"native_result", ... } envelope is
//                      POSTed to a per-session URL.
//
// Reconnection is handled by the browser's EventSource (it resends the last seen
// id via the Last-Event-ID header); the server replays the missed ticks. The
// same DOM renderer runs above this transport as in every other mode.

/**
 * @typedef {import("./transport.js").Patch} Patch
 * @typedef {import("./transport.js").TWEvent} TWEvent
 */

/**
 * Create an SSE + POST transport (Mode B, B5).
 *
 * @param {Object} config
 * @param {string} config.session
 *        Stable per-client session id; both URLs are derived from it.
 * @param {string} [config.streamUrl]
 *        SSE GET URL. Defaults to `/sse?session=<session>`.
 * @param {string} [config.postUrl]
 *        Event POST URL. Defaults to `/sse/<session>`.
 * @param {(capability: string, args: Object) => (Promise<*>|*)} [config.onNativeCall]
 *        Optional handler that runs a proxied native capability and resolves
 *        with its JSON-able value (or throws to signal failure).
 * @param {typeof EventSource} [config.EventSourceImpl]
 *        EventSource constructor (injectable for tests/jsdom).
 * @param {typeof fetch} [config.fetchImpl]
 *        fetch implementation (injectable for tests/jsdom).
 * @returns {import("./transport.js").Transport & {
 *            sendNativeResult: (callId: string, ok: boolean, payload: *) => void
 *          }}
 */
export function createSSETransport(config) {
  const session = config.session;
  const streamUrl =
    config.streamUrl || `/sse?session=${encodeURIComponent(session)}`;
  const postUrl = config.postUrl || `/sse/${encodeURIComponent(session)}`;
  const onNativeCall = config.onNativeCall || null;
  const EventSourceImpl = config.EventSourceImpl || globalThis.EventSource;
  const fetchImpl = config.fetchImpl || globalThis.fetch;

  const source = new EventSourceImpl(streamUrl);

  /** @type {((patches: Patch[]) => void) | null} */
  let patchHandler = null;
  /** @type {((path: string) => void) | null} */
  let navigateHandler = null;
  /** @type {Patch[][]} */
  const pendingBatches = [];

  /**
   * POST one envelope back to the server (client -> server leg).
   * @param {Object} envelope
   * @returns {Promise<void>}
   */
  async function post(envelope) {
    await fetchImpl(postUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(envelope),
    });
  }

  /**
   * Reply to a native_call with its result (or error).
   * @param {string} callId
   * @param {boolean} ok
   * @param {*} payload  The value when ok, otherwise the error string.
   * @returns {void}
   */
  function sendNativeResult(callId, ok, payload) {
    const envelope = { kind: "native_result", call_id: callId, ok };
    if (ok) envelope.value = payload;
    else envelope.error = String(payload);
    void post(envelope);
  }

  /**
   * Run a proxied native_call and POST back its native_result.
   * @param {{call_id: string, capability: string, args: Object}} envelope
   * @returns {Promise<void>}
   */
  async function handleNativeCall(envelope) {
    if (!onNativeCall) {
      sendNativeResult(envelope.call_id, false, "no native handler");
      return;
    }
    try {
      const value = await onNativeCall(envelope.capability, envelope.args || {});
      sendNativeResult(envelope.call_id, true, value);
    } catch (err) {
      sendNativeResult(envelope.call_id, false, err && err.message ? err.message : err);
    }
  }

  source.addEventListener("message", (event) => {
    const envelope = JSON.parse(event.data);
    if (envelope.kind === "patches") {
      if (patchHandler) patchHandler(envelope.data);
      else pendingBatches.push(envelope.data);
    } else if (envelope.kind === "native_call") {
      void handleNativeCall(envelope);
    } else if (envelope.kind === "navigate") {
      if (navigateHandler) navigateHandler(envelope.path);
    }
  });

  // Named heartbeat: keep the connection warm, nothing to apply.
  source.addEventListener("ping", () => {});

  return {
    /**
     * Register the patch-batch callback; flushes any buffered batches.
     * @param {(patches: Patch[]) => void} handler
     * @returns {void}
     */
    onPatches(handler) {
      patchHandler = handler;
      while (pendingBatches.length > 0) handler(pendingBatches.shift());
    },

    /**
     * Register the callback invoked when the app navigates (view → URL).
     * @param {(path: string) => void} handler
     * @returns {void}
     */
    onNavigate(handler) {
      navigateHandler = handler;
    },

    /**
     * Send a user event back to the Python side (via HTTP POST).
     * @param {TWEvent} event
     * @returns {void}
     */
    sendEvent(event) {
      void post({ kind: "event", data: event });
    },

    sendNativeResult,

    /**
     * Close the EventSource.
     * @returns {Promise<void>}
     */
    async close() {
      source.close();
    },
  };
}
