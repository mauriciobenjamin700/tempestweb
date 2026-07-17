// transport-ws.test.js — Mode B WebSocket client transport (jsdom).
//
// jsdom ships no WebSocket, so we inject a FakeWebSocket that lets the test play
// the server side: deliver `patches`/`native_call` envelopes down to the client
// and capture the `event`/`native_result` envelopes the client sends up. The
// wire shapes are the real goldens from tests/fixtures/.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./setup.js";
import { createWebSocketTransport, backoffDelay } from "../../client/transport-ws.js";

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
