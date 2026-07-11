// transport-ws.js — Mode B transport over WebSocket.  PHASE B1.
//
// Carries the wire format from ../docs/contract.md over one bidirectional
// WebSocket. Every frame is a JSON envelope tagged by `kind`:
//   server -> client: { kind:"patches", data:[Patch...] }
//                      { kind:"native_call", call_id, capability, args }
//   client -> server: { kind:"event", data:Event }
//                      { kind:"native_result", call_id, ok, value|error }
//
// Implements the Transport interface from transport.js. The same DOM renderer
// and Style->CSS translator run above it as in Mode A; only this file differs.

import { subscribeDispatch, unsubscribeDispatch } from "./native/index.js";

/**
 * @typedef {import("./transport.js").Patch} Patch
 * @typedef {import("./transport.js").TWEvent} TWEvent
 */

/**
 * Create a WebSocket-backed transport (Mode B).
 *
 * @param {string} url
 *        The ws:// or wss:// endpoint (e.g. "ws://127.0.0.1:8000/ws").
 * @param {Object} [options]
 * @param {(capability: string, args: Object) => (Promise<*>|*)} [options.onNativeCall]
 *        Optional handler that runs a proxied native capability and resolves
 *        with its JSON-able value (or throws to signal failure). The transport
 *        replies with the matching `native_result` envelope automatically.
 * @param {typeof WebSocket} [options.WebSocketImpl]
 *        WebSocket constructor to use (injectable for tests/jsdom).
 * @returns {import("./transport.js").Transport & {
 *            sendNativeResult: (callId: string, ok: boolean, payload: *) => void,
 *            ready: Promise<void>
 *          }}
 */
export function createWebSocketTransport(url, options = {}) {
  const WebSocketImpl = options.WebSocketImpl || globalThis.WebSocket;
  const onNativeCall = options.onNativeCall || null;
  const socket = new WebSocketImpl(url);

  /** @type {((patches: Patch[]) => void) | null} */
  let patchHandler = null;
  /** @type {((path: string) => void) | null} */
  let navigateHandler = null;
  /** @type {Patch[][]} */
  const pendingBatches = [];
  let closed = false;

  const ready = new Promise((resolve, reject) => {
    socket.addEventListener("open", () => resolve());
    socket.addEventListener("error", (event) => reject(event));
  });

  /**
   * Send one JSON envelope, guarding against a closed socket.
   * @param {Object} envelope
   * @returns {void}
   */
  function send(envelope) {
    if (closed || socket.readyState !== 1 /* OPEN */) return;
    socket.send(JSON.stringify(envelope));
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
    send(envelope);
  }

  /**
   * Run a proxied native_call and reply with its native_result.
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

  socket.addEventListener("message", (event) => {
    const envelope = JSON.parse(event.data);
    if (envelope.kind === "patches") {
      if (patchHandler) patchHandler(envelope.data);
      else pendingBatches.push(envelope.data);
    } else if (envelope.kind === "native_call") {
      void handleNativeCall(envelope);
    } else if (envelope.kind === "native_subscribe") {
      subscribeDispatch(envelope, (payload) =>
        send({ kind: "native_event", sub_id: envelope.sub_id, ...payload }),
      );
    } else if (envelope.kind === "native_unsubscribe") {
      unsubscribeDispatch(envelope.sub_id);
    } else if (envelope.kind === "navigate") {
      if (navigateHandler) navigateHandler(envelope.path);
    }
  });

  socket.addEventListener("close", () => {
    closed = true;
  });

  return {
    /**
     * Register the patch-batch callback; flushes any batches buffered before
     * the handler was attached.
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
     * Send a user event back to the Python side.
     * @param {TWEvent} event
     * @returns {void}
     */
    sendEvent(event) {
      send({ kind: "event", data: event });
    },

    sendNativeResult,

    ready,

    /**
     * Close the WebSocket.
     * @returns {Promise<void>}
     */
    async close() {
      closed = true;
      if (socket.readyState === 0 || socket.readyState === 1) socket.close();
    },
  };
}
