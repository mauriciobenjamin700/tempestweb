// wire-decode.test.js — a frame the client cannot decode (issue #160).
//
// Python hands every transport its frames as text. A frame that cannot be parsed
// used to throw straight out of the message handler: the batch it carried was
// lost with no log and no repair, and because Python's baseline had already moved
// past it, the next tick's index-relative patches addressed nodes that never
// arrived (`patch path out of range`, one tick later, somewhere unrelated).
//
// The decode now belongs to `client/wire.js`, which pairs the loss with the same
// repair a patch failure gets: one resync, at most once per run of bad frames.
import { test } from "node:test";
import assert from "node:assert/strict";

import { createWireDecoder } from "../../client/wire.js";
import { createWasmTransport } from "../../client/transport-wasm.js";
import { createWebSocketTransport } from "../../client/transport-ws.js";
import { createSSETransport } from "../../client/transport-sse.js";

/**
 * Run `fn` with console.error captured, so a deliberate failure stays quiet.
 * @param {() => any} fn
 * @returns {{result: any, logged: any[][]}}
 */
function quietly(fn) {
  const logged = [];
  const original = console.error;
  console.error = (...args) => logged.push(args);
  try {
    return { result: fn(), logged };
  } finally {
    console.error = original;
  }
}

test("a decodable frame passes through with its value", () => {
  const decode = createWireDecoder(() => {}, "test");
  const { result } = quietly(() => decode('{"kind":"patches","data":[]}'));
  assert.equal(result.ok, true);
  assert.deepEqual(result.value, { kind: "patches", data: [] });
});

test("an undecodable frame reports the loss and asks for one resync", () => {
  let resyncs = 0;
  const decode = createWireDecoder(() => (resyncs += 1), "the test transport");
  const { result, logged } = quietly(() => decode('{"width": NaN}'));

  assert.equal(result.ok, false);
  assert.equal(result.value, undefined);
  assert.equal(resyncs, 1);
  assert.equal(logged.length, 1);
  assert.match(logged[0][0], /the test transport could not decode a frame/);
  assert.match(logged[0][0], /14 chars/);
});

test("a run of undecodable frames still asks for a single resync", () => {
  let resyncs = 0;
  const decode = createWireDecoder(() => (resyncs += 1), "test");
  quietly(() => {
    decode("{oops");
    decode("{oops");
    decode("{oops");
  });
  assert.equal(resyncs, 1, "a resync per failure would spin: it comes back identical");
});

test("a frame that decodes re-arms the repair for the next failure", () => {
  let resyncs = 0;
  const decode = createWireDecoder(() => (resyncs += 1), "test");
  quietly(() => {
    decode("{oops");
    decode("[]");
    decode("{oops");
  });
  assert.equal(resyncs, 2);
});

test("Mode A: a batch that cannot be decoded never reaches the renderer", () => {
  /** @type {(batchJson: string) => void} */
  let deliver = () => {};
  const pushed = [];
  const transport = createWasmTransport({
    onDeliver(cb) {
      deliver = cb;
    },
    pushEvent(ev) {
      pushed.push(ev);
    },
  });
  const batches = [];
  transport.onPatches((p) => batches.push(p));

  quietly(() => deliver('[{"path":[0],"set_props":{"style":{"width":NaN}}}]'));

  assert.equal(batches.length, 0);
  assert.deepEqual(pushed, [{ type: "resync", key: "", payload: {} }]);
});

test("Mode A: a batch buffered before the renderer is decoded with the repair available", () => {
  /** @type {(batchJson: string) => void} */
  let deliver = () => {};
  const pushed = [];
  const transport = createWasmTransport({
    onDeliver(cb) {
      deliver = cb;
    },
    pushEvent(ev) {
      pushed.push(ev);
    },
  });

  quietly(() => deliver("{oops"));

  assert.deepEqual(
    pushed,
    [{ type: "resync", key: "", payload: {} }],
    "buffering the parsed value instead would have thrown in the bootstrap glue, " +
      "before any transport existed to repair through",
  );
});

test("Mode B WebSocket: an undecodable frame asks the server to resync", async () => {
  let socket;
  const Impl = class {
    constructor(url) {
      this.url = url;
      this.readyState = 0;
      this.sent = [];
      this._listeners = {};
      socket = this;
      queueMicrotask(() => {
        this.readyState = 1;
        for (const fn of this._listeners.open || []) fn({});
      });
    }
    addEventListener(type, fn) {
      (this._listeners[type] ||= []).push(fn);
    }
    send(data) {
      this.sent.push(JSON.parse(data));
    }
    close() {}
  };
  const transport = createWebSocketTransport("ws://x/ws", { WebSocketImpl: Impl });
  await transport.ready;

  const batches = [];
  transport.onPatches((p) => batches.push(p));
  quietly(() => {
    for (const fn of socket._listeners.message || []) fn({ data: '{"kind":"patches"' });
  });

  assert.equal(batches.length, 0);
  assert.deepEqual(socket.sent, [{ kind: "event", data: { type: "resync", key: "" } }]);
});

test("Mode B SSE: an undecodable frame posts a resync", () => {
  let source;
  const posted = [];
  const Impl = class {
    constructor(url) {
      this.url = url;
      this._listeners = {};
      source = this;
    }
    addEventListener(type, fn) {
      (this._listeners[type] ||= []).push(fn);
    }
    close() {}
  };
  const transport = createSSETransport({
    session: "s1",
    EventSourceImpl: Impl,
    fetchImpl: async (url, init) => {
      posted.push(JSON.parse(init.body));
      return { ok: true, status: 204 };
    },
  });

  const batches = [];
  transport.onPatches((p) => batches.push(p));
  quietly(() => {
    for (const fn of source._listeners.message || []) fn({ data: "{oops" });
  });

  assert.equal(batches.length, 0);
  assert.deepEqual(posted, [{ kind: "event", data: { type: "resync", key: "" } }]);
});
