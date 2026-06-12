// transport-ws.test.js — Mode B WebSocket client transport (jsdom).
//
// jsdom ships no WebSocket, so we inject a FakeWebSocket that lets the test play
// the server side: deliver `patches`/`native_call` envelopes down to the client
// and capture the `event`/`native_result` envelopes the client sends up. The
// wire shapes are the real goldens from tests/fixtures/.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./setup.js";
import { createWebSocketTransport } from "../../client/transport-ws.js";

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
