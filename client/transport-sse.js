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

import { dispatch, subscribeDispatch, unsubscribeDispatch } from "./native/index.js";
import { applyThemeMode } from "./theme.js";

/**
 * @typedef {import("./transport.js").Patch} Patch
 * @typedef {import("./transport.js").TWEvent} TWEvent
 */

/** Cap on outbound `event` envelopes buffered while the stream is down. */
const MAX_OUTBOX = 1000;

/**
 * Create an SSE + POST transport (Mode B, B5).
 *
 * A named `ping` heartbeat event keeps the connection warm and carries nothing to
 * apply, so its listener is intentionally empty.
 *
 * @param {Object} config
 * @param {string} config.session
 *        Stable per-client session id; both URLs are derived from it.
 * @param {string} [config.streamUrl]
 *        SSE GET URL. Defaults to `/sse?session=<session>`.
 * @param {string} [config.postUrl]
 *        Event POST URL. Defaults to `/sse/<session>`.
 * @param {(capability: string, args: Object) => (Promise<*>|*)} [config.onNativeCall]
 *        Optional **override** for the built-in native bridge: runs a proxied
 *        native capability and resolves with its JSON-able value (or throws to
 *        signal failure). Omit it and proxied calls go to `dispatch()` from
 *        `native/index.js` — the same registry Mode A uses.
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
  /** Whether the stream is open — i.e. the server holds a session for this id. */
  let streamOpen = false;
  /** @type {Object[]} Outbound `event` envelopes buffered while the stream is down. */
  const outbox = [];

  /**
   * POST one envelope back to the server (client -> server leg).
   *
   * A rejected POST is logged rather than swallowed: the server answers `404`
   * for an unknown session, `401` unauthorized and `413` for an oversized body,
   * and an envelope lost to any of those would otherwise vanish without a trace
   * on either side.
   *
   * @param {Object} envelope
   * @returns {Promise<void>}
   */
  async function post(envelope) {
    const response = await fetchImpl(postUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(envelope),
    });
    if (response && response.ok === false) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn(
          `tempestweb sse: POST ${postUrl} rejected (${response.status}), dropped`,
          envelope.kind,
        );
      }
    }
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
   *
   * With no `onNativeCall` override the call goes to the built-in `dispatch()`,
   * whose result envelope is already the wire shape (`call_id` + `ok` +
   * `value`, or `error` + `message`) and is POSTed verbatim, keeping Mode B's
   * error codes identical to Mode A's.
   *
   * @param {{call_id: string, capability: string, args: Object}} envelope
   * @returns {Promise<void>}
   */
  async function handleNativeCall(envelope) {
    if (!onNativeCall) {
      await post({ kind: "native_result", ...(await dispatch(envelope)) });
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
    } else if (envelope.kind === "native_subscribe") {
      subscribeDispatch(envelope, (payload) =>
        void post({ kind: "native_event", sub_id: envelope.sub_id, ...payload }),
      );
    } else if (envelope.kind === "native_unsubscribe") {
      unsubscribeDispatch(envelope.sub_id);
    } else if (envelope.kind === "navigate") {
      if (navigateHandler) navigateHandler(envelope.path);
    } else if (envelope.kind === "theme") {
      // The half of dark mode that lives in CSS: the base sheet reads this
      // attribute for its token block, so the page, the field surfaces and every
      // hover/focus state follow the app's theme instead of the OS alone.
      applyThemeMode(envelope.mode);
    }
  });

  source.addEventListener("ping", () => {});

  source.addEventListener("open", () => {
    streamOpen = true;
    while (outbox.length > 0) void post(outbox.shift());
  });

  source.addEventListener("error", () => {
    streamOpen = false;
  });

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
     *
     * Events raised before the stream opens are buffered and flushed on `open`,
     * never POSTed blind. The server only materialises the session when it
     * handles the `GET /sse` that opens the stream, so an event that overtakes
     * it — the router's initial `navigate`, or a click on a pre-rendered
     * control — hits `POST /sse/<id>` on an id the server has never seen and is
     * answered `404`, silently losing it. The buffer is capped at
     * {@link MAX_OUTBOX} envelopes so a long outage cannot grow it forever;
     * past that the oldest are dropped (and logged), as in the WebSocket
     * transport. `native_result` frames are never buffered: they can only be
     * produced by a `native_call` that arrived on an already-open stream.
     *
     * @param {TWEvent} event
     * @returns {void}
     */
    sendEvent(event) {
      const envelope = { kind: "event", data: event };
      if (streamOpen) {
        void post(envelope);
        return;
      }
      if (outbox.length >= MAX_OUTBOX) {
        const dropped = outbox.shift();
        if (typeof console !== "undefined" && console.warn) {
          console.warn(
            `tempestweb sse: outbox full (${MAX_OUTBOX}), dropped oldest envelope`,
            dropped && dropped.kind,
          );
        }
      }
      outbox.push(envelope);
    },

    sendNativeResult,

    /**
     * Ask the server to re-send the whole scene.
     *
     * The DOM is only correct while every patch has applied in order, so a batch
     * the renderer could not apply leaves a tree no later index-relative patch
     * fits. This asks for one root replace to start from instead.
     *
     * @returns {void}
     */
    requestResync() {
      void post({ kind: "event", data: { type: "resync", key: "" } });
    },

    /**
     * Close the EventSource.
     * @returns {Promise<void>}
     */
    async close() {
      source.close();
    },
  };
}
