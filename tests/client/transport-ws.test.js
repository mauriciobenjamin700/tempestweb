// transport-ws.test.js — Mode B WebSocket client transport (jsdom).
//
// jsdom ships no WebSocket, so we inject a FakeWebSocket that lets the test play
// the server side: deliver `patches`/`native_call` envelopes down to the client
// and capture the `event`/`native_result` envelopes the client sends up. The
// wire shapes are the real goldens from tests/fixtures/.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture, freshDom } from "./setup.js";
import { THEME_MODE_ATTR } from "../../client/theme.js";
import {
  createWebSocketTransport,
  backoffDelay,
  newSessionId,
  withSession,
} from "../../client/transport-ws.js";

/** Minimal WebSocket double the test drives as the server. */
class FakeWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = 0; // CONNECTING
    this.sent = [];
    this._listeners = {};
    // Open on the next microtask, like a real socket.
    queueMicrotask(() => {
      this.readyState = 1; // OPEN
      this._emit("open", {});
    });
  }
  addEventListener(type, fn) {
    (this._listeners[type] ||= []).push(fn);
  }
  _emit(type, event) {
    for (const fn of this._listeners[type] || []) fn(event);
  }
  send(data) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    this.readyState = 3; // CLOSED
    this._emit("close", {});
  }
  /** Test helper: deliver one server->client envelope. */
  serverSend(envelope) {
    this._emit("message", { data: JSON.stringify(envelope) });
  }
}

test("ws transport delivers patch batches to onPatches", async () => {
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  await transport.ready;

  const batches = [];
  transport.onPatches((p) => batches.push(p));

  const patches = fixture("patches_count_0_to_1.json");
  socket.serverSend({ kind: "patches", data: patches });

  assert.equal(batches.length, 1);
  assert.equal(batches[0][0].set_props.content, "Count: 1");
});

test("ws transport buffers patches sent before onPatches is set", async () => {
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  await transport.ready;

  socket.serverSend({ kind: "patches", data: fixture("patches_count_0_to_1.json") });

  const batches = [];
  transport.onPatches((p) => batches.push(p)); // attaches late
  assert.equal(batches.length, 1);
});

test("ws transport sends events as event envelopes", async () => {
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  await transport.ready;

  transport.sendEvent({ type: "click", key: "inc", payload: {} });

  assert.equal(socket.sent.length, 1);
  assert.deepEqual(socket.sent[0], {
    kind: "event",
    data: { type: "click", key: "inc", payload: {} },
  });
});

test("ws transport routes a navigate envelope to onNavigate", async () => {
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  await transport.ready;

  const paths = [];
  transport.onNavigate((p) => paths.push(p));

  socket.serverSend({ kind: "navigate", path: "/settings" });

  assert.deepEqual(paths, ["/settings"]);
});

test("ws transport answers native_call with native_result", async () => {
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", {
    WebSocketImpl: Impl,
    onNativeCall: async (capability) => {
      assert.equal(capability, "geolocation.get");
      return { lat: -23.5, lon: -46.6 };
    },
  });
  await transport.ready;

  socket.serverSend({
    kind: "native_call",
    call_id: "c1",
    capability: "geolocation.get",
    args: {},
  });
  // Let the async handler resolve.
  await new Promise((r) => setTimeout(r, 0));

  assert.deepEqual(socket.sent[0], {
    kind: "native_result",
    call_id: "c1",
    ok: true,
    value: { lat: -23.5, lon: -46.6 },
  });
});

test("ws transport reports a failing native_call as ok:false", async () => {
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", {
    WebSocketImpl: Impl,
    onNativeCall: async () => {
      throw new Error("PermissionDenied");
    },
  });
  await transport.ready;

  socket.serverSend({ kind: "native_call", call_id: "c2", capability: "camera.capture" });
  await new Promise((r) => setTimeout(r, 0));

  assert.deepEqual(socket.sent[0], {
    kind: "native_result",
    call_id: "c2",
    ok: false,
    error: "PermissionDenied",
  });
});

// --- the built-in native bridge (no onNativeCall override) -----------------
//
// Regression for issue #60: the Mode B shell never passed an onNativeCall, so
// every proxied capability answered "no native handler" and the whole native
// surface was dead in Mode B — silently, since the failure only surfaces inside
// the Python handler's await. The transport now falls back to dispatch(), the
// same registry Mode A runs, so a plain shell needs no wiring.

test("ws transport runs a native_call through the built-in bridge", async () => {
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  await transport.ready;

  socket.serverSend({
    kind: "native_call",
    call_id: "c3",
    capability: "network.state",
    args: {},
  });
  await new Promise((r) => setTimeout(r, 0));

  assert.equal(socket.sent[0].kind, "native_result");
  assert.equal(socket.sent[0].call_id, "c3");
  assert.equal(socket.sent[0].ok, true);
  assert.equal(typeof socket.sent[0].value.online, "boolean");
});

test("ws transport surfaces the capability error code, not 'no native handler'", async () => {
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  await transport.ready;

  socket.serverSend({
    kind: "native_call",
    call_id: "c4",
    capability: "nope.thing",
    args: {},
  });
  await new Promise((r) => setTimeout(r, 0));

  assert.deepEqual(socket.sent[0], {
    kind: "native_result",
    call_id: "c4",
    ok: false,
    error: "unknown_capability",
    message: "nope.thing",
  });
});

// --- reconnect + outbound buffer (WS resilience) ---------------------------

/** A WebSocket double whose open/close the test drives explicitly. */
class ManualWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = 0; // CONNECTING
    this.sent = [];
    this._listeners = {};
  }
  addEventListener(type, fn) {
    (this._listeners[type] ||= []).push(fn);
  }
  _emit(type, event) {
    for (const fn of this._listeners[type] || []) fn(event);
  }
  send(data) {
    this.sent.push(JSON.parse(data));
  }
  open() {
    this.readyState = 1;
    this._emit("open", {});
  }
  close() {
    this.readyState = 3;
    this._emit("close", {});
  }
  error() {
    this._emit("error", { type: "error" });
  }
  serverSend(envelope) {
    this._emit("message", { data: JSON.stringify(envelope) });
  }
}

/** Build a transport with controllable sockets + a captured timer queue. */
function reconnectingHarness(overrides = {}) {
  const sockets = [];
  const timers = [];
  const Impl = class extends ManualWebSocket {
    constructor(url) {
      super(url);
      sockets.push(this);
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", {
    WebSocketImpl: Impl,
    setTimeoutImpl: (fn, ms) => {
      timers.push({ fn, ms });
      return timers.length - 1;
    },
    clearTimeoutImpl: (id) => {
      timers[id] = null;
    },
    random: () => 0,
    ...overrides,
  });
  return { transport, sockets, timers };
}

test("backoffDelay: exponential growth, capped, with jitter bounds", () => {
  const cfg = { baseMs: 500, maxMs: 30000, factor: 2 };
  assert.equal(backoffDelay(0, { ...cfg, random: () => 0 }), 250, "min jitter");
  assert.equal(backoffDelay(0, { ...cfg, random: () => 1 }), 500, "max jitter");
  assert.equal(backoffDelay(3, { ...cfg, random: () => 1 }), 4000, "500*2^3");
  assert.equal(backoffDelay(20, { ...cfg, random: () => 1 }), 30000, "capped");
});

test("ws transport reconnects after an unexpected close", async () => {
  const { transport, sockets, timers } = reconnectingHarness();
  sockets[0].open();
  await transport.ready;

  let reconnected = 0;
  transport.onReconnect(() => (reconnected += 1));

  sockets[0].close();
  assert.equal(timers.filter(Boolean).length, 1, "a reconnect was scheduled");

  timers[0].fn(); // fire the backoff timer → new socket
  assert.equal(sockets.length, 2, "a fresh socket was opened");

  sockets[1].open();
  assert.equal(reconnected, 1, "onReconnect fired on the resumed connection");
});

test("ws transport buffers events while offline and flushes on reopen", async () => {
  const { transport, sockets, timers } = reconnectingHarness();
  sockets[0].open();
  await transport.ready;

  sockets[0].close();
  transport.sendEvent({ type: "click", key: "a", payload: {} }); // buffered
  timers[0].fn();
  transport.sendEvent({ type: "click", key: "b", payload: {} }); // buffered (CONNECTING)
  assert.equal(sockets[1].sent.length, 0, "nothing sent while not OPEN");

  sockets[1].open(); // flush
  assert.equal(sockets[1].sent.length, 2);
  assert.deepEqual(
    sockets[1].sent.map((e) => e.data.key),
    ["a", "b"],
    "buffered in order",
  );
});

test("ws transport does not reconnect after an explicit close", async () => {
  const { transport, sockets, timers } = reconnectingHarness();
  sockets[0].open();
  await transport.ready;

  await transport.close();
  assert.equal(timers.filter(Boolean).length, 0, "no reconnect scheduled");
  assert.equal(sockets.length, 1, "no new socket");
});

test("ws transport caps the outbox and drops the oldest (logged)", async () => {
  const warnings = [];
  const originalWarn = console.warn;
  console.warn = (...args) => warnings.push(args);
  try {
    const { transport, sockets } = reconnectingHarness({ maxOutbox: 2 });
    sockets[0].open();
    await transport.ready;
    sockets[0].close();

    transport.sendEvent({ type: "click", key: "1", payload: {} });
    transport.sendEvent({ type: "click", key: "2", payload: {} });
    transport.sendEvent({ type: "click", key: "3", payload: {} }); // drops "1"

    assert.equal(warnings.length, 1, "drop was logged");

    // The buffered survivors flush on a fresh open (default socket auto-reconnect
    // is driven by the harness timer; re-open the current socket to flush).
    sockets[0].open();
    assert.deepEqual(
      sockets[0].sent.map((e) => e.data.key),
      ["2", "3"],
      "oldest dropped, newest kept",
    );
  } finally {
    console.warn = originalWarn;
  }
});

test("ws transport rejects ready on error only when reconnect is disabled", async () => {
  const sockets = [];
  const Impl = class extends ManualWebSocket {
    constructor(url) {
      super(url);
      sockets.push(this);
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", {
    WebSocketImpl: Impl,
    reconnect: false,
  });
  sockets[0].error();
  await assert.rejects(transport.ready);
});

// --- reconnect hardening (0.56.1) -----------------------------------------

test("all handlers are re-attached on the reconnected socket", async () => {
  const { transport, sockets, timers } = reconnectingHarness();
  sockets[0].open();
  await transport.ready;

  const batches = [];
  transport.onPatches((p) => batches.push(p));

  sockets[0].close();
  timers[0].fn();
  sockets[1].open();

  sockets[1].serverSend({ kind: "patches", data: [{ set_props: { x: 1 } }] });
  assert.equal(batches.length, 1, "message re-attached on the new socket");

  sockets[1].close();
  assert.equal(timers.filter(Boolean).length, 2, "close re-attached (reschedules)");
});

test("chained reconnects grow the backoff (attempt not reset without an open)", async () => {
  const { sockets, timers } = reconnectingHarness();
  sockets[0].open();
  sockets[0].close();
  timers[0].fn();
  sockets[1].close();

  assert.equal(timers[0].ms, 250, "first backoff: 500*2^0*0.5");
  assert.equal(timers[1].ms, 500, "second backoff: 500*2^1*0.5 (grew)");
});

test("a stray extra close never schedules a second reconnect timer", async () => {
  const { sockets, timers } = reconnectingHarness();
  sockets[0].open();
  sockets[0].close();
  assert.equal(timers.filter(Boolean).length, 1);
  sockets[0]._emit("close", {});
  assert.equal(timers.filter(Boolean).length, 1, "guarded: still one timer");
});

test("native_result is NOT buffered across a reconnect (stale call_id)", async () => {
  const { transport, sockets, timers } = reconnectingHarness();
  sockets[0].open();
  await transport.ready;

  sockets[0].close();
  transport.sendNativeResult("dead-call", true, { ok: 1 });
  transport.sendEvent({ type: "click", key: "k", payload: {} });

  timers[0].fn();
  sockets[1].open();

  const kinds = sockets[1].sent.map((e) => e.kind);
  assert.deepEqual(kinds, ["event"], "only the event flushed; native_result dropped");
});

// The half of dark mode the base sheet paints — the page, a field's surface,
// every hover/focus state — needs the mode, because the Theme itself never
// crosses the wire (#148): only the resolved mode does.
test("ws transport marks the document when the server reports a theme mode", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  let socket;
  const Impl = class extends FakeWebSocket {
    constructor(url) {
      super(url);
      socket = this;
    }
  };
  const transport = createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  await transport.ready;

  socket.serverSend({ kind: "theme", mode: "dark" });
  assert.equal(dom.document.documentElement.getAttribute(THEME_MODE_ATTR), "dark");

  socket.serverSend({ kind: "theme", mode: "light" });
  assert.equal(dom.document.documentElement.getAttribute(THEME_MODE_ATTR), "light");
});

// --- session resume (#203) --------------------------------------------------

test("the socket URL carries a session id", () => {
  const sockets = [];
  const Impl = class extends ManualWebSocket {
    constructor(url) {
      super(url);
      sockets.push(this);
    }
  };
  createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl, session: "abc" });
  assert.equal(sockets[0].url, "ws://x/ws?session=abc");
});

test("a reconnect asks for the same session, which is what resumes it", () => {
  const { sockets, timers } = reconnectingHarness({ session: "keep-me" });
  sockets[0].open();
  sockets[0].close();
  timers.find((t) => t)?.fn();

  assert.equal(sockets.length, 2, "the transport reconnected");
  assert.equal(sockets[1].url, "ws://x/ws?session=keep-me");
  assert.equal(
    sockets[0].url,
    sockets[1].url,
    "a reconnect that asked for a different session would start over",
  );
});

test("a url with a query string keeps it and gains the session", () => {
  const sockets = [];
  const Impl = class extends ManualWebSocket {
    constructor(url) {
      super(url);
      sockets.push(this);
    }
  };
  createWebSocketTransport("ws://x/ws?token=sesame", {
    WebSocketImpl: Impl,
    session: "s1",
  });
  assert.equal(sockets[0].url, "ws://x/ws?token=sesame&session=s1");
});

test("withSession escapes an id that would otherwise break the query", () => {
  assert.equal(withSession("/ws", "a b&c=d"), "/ws?session=a%20b%26c%3Dd");
});

test("each transport mints its own session id", () => {
  const sockets = [];
  const Impl = class extends ManualWebSocket {
    constructor(url) {
      super(url);
      sockets.push(this);
    }
  };
  createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  assert.notEqual(sockets[0].url, sockets[1].url, "two clients shared a session id");
});

test("newSessionId works without crypto.randomUUID", () => {
  const saved = globalThis.crypto;
  try {
    Object.defineProperty(globalThis, "crypto", { value: {}, configurable: true });
    const id = newSessionId();
    assert.ok(id.length > 8, `expected a usable id, got ${id}`);
    assert.notEqual(id, newSessionId(), "the fallback repeats itself");
  } finally {
    Object.defineProperty(globalThis, "crypto", { value: saved, configurable: true });
  }
});
