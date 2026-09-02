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
//
// Resilience: the socket auto-reconnects with exponential backoff + jitter (a
// dropped connection no longer kills the app). User `event` envelopes issued
// while the socket is not OPEN are buffered and flushed on the next open, and an
// onReconnect hook lets the runtime re-sync after a drop. Connection-scoped
// frames (native_result keyed to a call_id, native_event keyed to a sub_id) are
// NOT buffered — after a reconnect the fresh server never issued that call/sub,
// so replaying them would act on a stale id.
//
// Session resume: the transport carries a stable id in the socket URL
// (`?session=<id>`), so a reconnect lands on the session it left rather than on a
// fresh one. Until this existed, a 400 ms blip reset the user's state — a
// half-filled form, a cart, the selected tab — because the server built fresh
// state per connection. The server answers a resumed socket with one full patch
// batch carrying the scene as it stands, and the buffered events replay against
// the state they were written for.
//
// The id lives in this closure, not in storage: it identifies *this page's*
// connection to the server, and a reload is a new page with a new tree. The
// server keeps a dropped session for a short window (`ws_resume_seconds`) and
// closes it afterwards, so an id nobody comes back for pins nothing.

import { dispatch, subscribeDispatch, unsubscribeDispatch } from "./native/index.js";
import { applyThemeMode } from "./theme.js";
import { createWireDecoder } from "./wire.js";

/**
 * @typedef {import("./transport.js").Patch} Patch
 * @typedef {import("./transport.js").TWEvent} TWEvent
 */

/** Default outbound buffer cap; oldest envelopes are dropped past this. */
const DEFAULT_MAX_OUTBOX = 1000;

/**
 * Compute the backoff delay (ms) for a reconnect attempt.
 *
 * Exponential (`base * factor**attempt`, capped at `max`) with symmetric jitter
 * in `[0.5, 1.0]` of the computed delay, so a fleet of clients doesn't reconnect
 * in lockstep after a shared server blip.
 *
 * @param {number} attempt   Zero-based attempt count since the last open.
 * @param {Object} opts      Backoff config.
 * @param {number} opts.baseMs   First-retry base delay.
 * @param {number} opts.maxMs    Ceiling delay.
 * @param {number} opts.factor   Growth factor per attempt.
 * @param {() => number} opts.random   Uniform [0,1) source (injectable for tests).
 * @returns {number} The delay in milliseconds.
 */
export function backoffDelay(attempt, opts) {
  const raw = opts.baseMs * opts.factor ** attempt;
  const capped = Math.min(opts.maxMs, raw);
  return Math.round(capped * (0.5 + opts.random() * 0.5));
}

/**
 * Create a WebSocket-backed transport (Mode B).
 *
 * @param {string} url
 *        The ws:// or wss:// endpoint (e.g. "ws://127.0.0.1:8000/ws").
 * @param {Object} [options]
 * @param {(capability: string, args: Object) => (Promise<*>|*)} [options.onNativeCall]
 *        Optional **override** for the built-in native bridge: runs a proxied
 *        native capability and resolves with its JSON-able value (or throws to
 *        signal failure). The transport replies with the matching
 *        `native_result` envelope automatically. Omit it and proxied calls go to
 *        `dispatch()` from `native/index.js` — the same registry Mode A uses —
 *        so a plain shell gets the whole native surface with no wiring.
 * @param {typeof WebSocket} [options.WebSocketImpl]
 *        WebSocket constructor to use (injectable for tests/jsdom).
 * @param {string} [options.session]
 *        Stable session id carried in the socket URL, so a reconnect resumes the
 *        server-side session instead of starting a fresh one. Defaults to a newly
 *        minted id, which is what an app wants; pass one only to pin it in a test.
 * @param {boolean} [options.reconnect]
 *        Auto-reconnect on an unexpected close (default true). When false, the
 *        transport behaves like a single-shot socket: `ready` rejects on error
 *        and a close is terminal.
 * @param {Object} [options.backoff]
 *        Backoff tuning: `{baseMs=500, maxMs=30000, factor=2}`.
 * @param {number} [options.maxOutbox]
 *        Max buffered outbound envelopes while offline (default 1000). Past this,
 *        the oldest are dropped (and logged) so a long outage can't grow forever.
 * @param {(fn: () => void, ms: number) => *} [options.setTimeoutImpl]
 *        setTimeout override (injectable for tests).
 * @param {(id: *) => void} [options.clearTimeoutImpl]
 *        clearTimeout override (injectable for tests).
 * @param {() => number} [options.random]
 *        Uniform [0,1) source for jitter (injectable for tests).
 * @returns {import("./transport.js").Transport & {
 *            sendNativeResult: (callId: string, ok: boolean, payload: *) => void,
 *            onReconnect: (handler: () => void) => void,
 *            ready: Promise<void>
 *          }}
 */
/**
 * Mint an id for this page's session.
 *
 * `crypto.randomUUID` is not everywhere (it needs a secure context), so the
 * fallback is a random string of the same shape. The id only has to be unguessable
 * enough that another client cannot name it, and unique enough not to collide —
 * the server checks the owner's fingerprint before handing a session over, so
 * knowing an id is not by itself enough to claim one.
 *
 * @returns {string}  The session id.
 */
export function newSessionId() {
  const uuid = globalThis.crypto?.randomUUID;
  if (typeof uuid === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `s-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

/**
 * Add a `session` query parameter to a socket URL, preserving what it already has.
 *
 * Built by hand rather than with `URL`, because the URL a caller passes is often
 * relative (`/ws`) and `URL` needs a base for that — and the base would have to
 * come from `location`, which a test does not have.
 *
 * @param {string} url  The socket URL, absolute or relative.
 * @param {string} session  The session id to carry.
 * @returns {string}  The URL with the session parameter appended.
 */
export function withSession(url, session) {
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}session=${encodeURIComponent(session)}`;
}

export function createWebSocketTransport(url, options = {}) {
  const WebSocketImpl = options.WebSocketImpl || globalThis.WebSocket;
  const onNativeCall = options.onNativeCall || null;
  const reconnect = options.reconnect !== false;
  const session = options.session ?? newSessionId();
  const backoff = {
    baseMs: options.backoff?.baseMs ?? 500,
    maxMs: options.backoff?.maxMs ?? 30000,
    factor: options.backoff?.factor ?? 2,
    random: options.random || Math.random,
  };
  const maxOutbox = options.maxOutbox ?? DEFAULT_MAX_OUTBOX;
  const setTimeoutImpl = options.setTimeoutImpl || ((fn, ms) => setTimeout(fn, ms));
  const clearTimeoutImpl = options.clearTimeoutImpl || ((id) => clearTimeout(id));

  /** @type {WebSocket | null} */
  let socket = null;
  /** @type {((patches: Patch[]) => void) | null} */
  let patchHandler = null;
  /** @type {((path: string) => void) | null} */
  let navigateHandler = null;
  /** @type {(() => void) | null} */
  let reconnectHandler = null;
  /** @type {Patch[][]} */
  const pendingBatches = [];
  /** @type {Object[]} Outbound envelopes buffered while the socket isn't OPEN. */
  const outbox = [];
  let userClosed = false;
  let opened = false;
  let attempt = 0;
  /** @type {*} */
  let reconnectTimer = null;

  let resolveReady = () => {};
  let rejectReady = () => {};
  let readySettled = false;
  const ready = new Promise((resolve, reject) => {
    resolveReady = resolve;
    rejectReady = reject;
  });

  /**
   * Flush every buffered outbound envelope while the socket stays OPEN.
   * @returns {void}
   */
  function flushOutbox() {
    while (outbox.length > 0 && socket && socket.readyState === 1) {
      socket.send(JSON.stringify(outbox.shift()));
    }
  }

  /**
   * Send one JSON envelope, buffering it when the socket is not OPEN.
   *
   * A buffered envelope is flushed on the next open. The buffer is capped at
   * `maxOutbox`; once full the oldest envelope is dropped (and logged) so a long
   * outage cannot grow it without bound.
   *
   * Only connection-agnostic user `event` envelopes are buffered. A
   * `native_result` (keyed to a `call_id`) or a `native_event` (keyed to a
   * `sub_id`) is meaningful only to the connection that requested it: after a
   * reconnect the server builds fresh state and never issued that call/sub, so
   * replaying it onto the new connection is at best a no-op and at worst acts on
   * a stale id. Those are dropped when the socket is not OPEN rather than queued.
   *
   * @param {Object} envelope
   * @returns {void}
   */
  function send(envelope) {
    if (socket && socket.readyState === 1) {
      socket.send(JSON.stringify(envelope));
      return;
    }
    if (envelope.kind !== "event") return;
    if (outbox.length >= maxOutbox) {
      const dropped = outbox.shift();
      if (typeof console !== "undefined" && console.warn) {
        console.warn(
          `tempestweb ws: outbox full (${maxOutbox}), dropped oldest envelope`,
          dropped && dropped.kind,
        );
      }
    }
    outbox.push(envelope);
  }

  /**
   * Reply to a native_call with its result (or error).
   * @param {string} callId
   * @param {boolean} ok
   * @param {*} payload  The value when ok, otherwise the error string.
   * @returns {void}
   */
  /**
   * Ask the server to re-send the whole scene.
   *
   * The DOM is only correct while every patch has applied in order, so a frame
   * the client could not decode — or a patch the renderer could not apply —
   * leaves a tree no later index-relative patch fits. This asks for one root
   * replace to start over from.
   *
   * @returns {void}
   */
  function requestResync() {
    send({ kind: "event", data: { type: "resync", key: "" } });
  }

  const decode = createWireDecoder(requestResync, "the WebSocket transport");

  function sendNativeResult(callId, ok, payload) {
    const envelope = { kind: "native_result", call_id: callId, ok };
    if (ok) envelope.value = payload;
    else envelope.error = String(payload);
    send(envelope);
  }

  /**
   * Run a proxied native_call and reply with its native_result.
   *
   * With no `onNativeCall` override the call goes to the built-in `dispatch()`,
   * whose result envelope is already the wire shape (`call_id` + `ok` +
   * `value`, or `error` + `message`) and is sent verbatim — so a Mode B failure
   * keeps the same error code and detail Mode A reports. This mirrors
   * `native_subscribe`, which has always gone straight to `subscribeDispatch`.
   *
   * @param {{call_id: string, capability: string, args: Object}} envelope
   * @returns {Promise<void>}
   */
  async function handleNativeCall(envelope) {
    if (!onNativeCall) {
      send({ kind: "native_result", ...(await dispatch(envelope)) });
      return;
    }
    try {
      const value = await onNativeCall(envelope.capability, envelope.args || {});
      sendNativeResult(envelope.call_id, true, value);
    } catch (err) {
      sendNativeResult(envelope.call_id, false, err && err.message ? err.message : err);
    }
  }

  /**
   * Handle one server->client frame.
   *
   * A `theme` envelope carries the half of dark mode that lives in CSS: the base
   * sheet reads the mode attribute for its token block, so the page, the field
   * surfaces and every hover/focus state follow the app's theme instead of the OS
   * alone. The Theme itself never crosses the wire — only the resolved mode does.
   *
   * @param {{data: string}} event
   * @returns {void}
   */
  function onMessage(event) {
    const decoded = decode(event.data);
    if (!decoded.ok) return;
    const envelope = decoded.value;
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
    } else if (envelope.kind === "theme") {
      applyThemeMode(envelope.mode);
    }
  }

  /**
   * On open: settle `ready` once, reset backoff, flush the outbox, and fire the
   * reconnect hook for every open after the first (a resumed connection).
   * @returns {void}
   */
  function onOpen() {
    const isReconnect = opened;
    opened = true;
    attempt = 0;
    if (!readySettled) {
      readySettled = true;
      resolveReady();
    }
    flushOutbox();
    if (isReconnect && reconnectHandler) reconnectHandler();
  }

  /**
   * On close: schedule a reconnect unless the caller closed us or reconnect is
   * disabled (in which case a close is terminal).
   * @returns {void}
   */
  function onClose() {
    if (userClosed || !reconnect) return;
    scheduleReconnect();
  }

  /**
   * On error before the first open with reconnect disabled, reject `ready`.
   * With reconnect enabled, errors are followed by close → reconnect, so `ready`
   * stays pending until a successful open.
   * @param {*} event
   * @returns {void}
   */
  function onError(event) {
    if (!reconnect && !readySettled) {
      readySettled = true;
      rejectReady(event);
    }
  }

  /**
   * Detach the four listeners from a socket (so a discarded socket can neither
   * re-fire `close` into scheduleReconnect nor deliver a late message).
   * @param {?WebSocket} sock
   * @returns {void}
   */
  function detach(sock) {
    if (!sock || typeof sock.removeEventListener !== "function") return;
    sock.removeEventListener("open", onOpen);
    sock.removeEventListener("message", onMessage);
    sock.removeEventListener("close", onClose);
    sock.removeEventListener("error", onError);
  }

  /**
   * Open a socket and wire its listeners, detaching the previous one first.
   * @returns {void}
   */
  /**
   * The socket URL for this session.
   *
   * @returns {string}  The URL carrying this transport's session id.
   */
  function sessionUrl() {
    return withSession(url, session);
  }

  function connect() {
    detach(socket);
    socket = new WebSocketImpl(sessionUrl());
    socket.addEventListener("open", onOpen);
    socket.addEventListener("message", onMessage);
    socket.addEventListener("close", onClose);
    socket.addEventListener("error", onError);
  }

  /**
   * Schedule the next reconnect attempt with backoff + jitter.
   *
   * A no-op when a reconnect is already pending, so a stray extra `close` can
   * never schedule two timers (which would spawn two competing sockets).
   * @returns {void}
   */
  function scheduleReconnect() {
    if (reconnectTimer !== null) return;
    const delay = backoffDelay(attempt, backoff);
    attempt += 1;
    reconnectTimer = setTimeoutImpl(() => {
      reconnectTimer = null;
      if (!userClosed) connect();
    }, delay);
  }

  connect();

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
     * Register a callback fired after the socket reconnects (any open past the
     * first). The runtime can use it to re-sync state that the fresh server
     * connection re-renders.
     * @param {() => void} handler
     * @returns {void}
     */
    onReconnect(handler) {
      reconnectHandler = handler;
    },

    /**
     * Send a user event back to the Python side.
     * @param {TWEvent} event
     * @returns {void}
     */
    sendEvent(event) {
      send({ kind: "event", data: event });
    },

    requestResync,

    sendNativeResult,

    ready,

    /**
     * Close the WebSocket and cancel any pending reconnect.
     * @returns {Promise<void>}
     */
    async close() {
      userClosed = true;
      if (reconnectTimer !== null) {
        clearTimeoutImpl(reconnectTimer);
        reconnectTimer = null;
      }
      if (socket && (socket.readyState === 0 || socket.readyState === 1)) {
        socket.close();
      }
    },
  };
}
