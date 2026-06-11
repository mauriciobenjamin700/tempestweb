// transport-wasm.test.js — Mode A transport unit tests (jsdom, no Pyodide).
//
// Drives createWasmTransport with a fake bridge that stands in for the
// pyodide.ffi adapter, proving the in-process patch-out / event-in contract and
// the buffering of patches that arrive before onPatches() is registered.
import { test } from "node:test";
import assert from "node:assert/strict";

import { createWasmTransport } from "../../client/transport-wasm.js";

/** Build a fake pyodide.ffi bridge that records pushed events and exposes deliver. */
function fakeBridge() {
  /** @type {(patches: any[]) => void} */
  let deliver = () => {};
  const pushed = [];
  let closedCalls = 0;
  return {
    bridge: {
      onDeliver(cb) {
        deliver = cb;
      },
      pushEvent(ev) {
        pushed.push(ev);
      },
      close() {
        closedCalls += 1;
      },
    },
    deliver: (patches) => deliver(patches),
    pushed,
    closedCalls: () => closedCalls,
  };
}

test("rejects a bridge without the required methods", () => {
  assert.throws(() => createWasmTransport(null), TypeError);
  assert.throws(() => createWasmTransport({}), TypeError);
  assert.throws(() => createWasmTransport({ onDeliver() {} }), TypeError);
});

test("delivered patch batches reach the onPatches handler", () => {
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  const got = [];
  transport.onPatches((patches) => got.push(patches));

  const batch = [{ path: [0], set_props: { content: "Count: 1" }, unset_props: [] }];
  fb.deliver(batch);

  assert.equal(got.length, 1);
  assert.deepEqual(got[0], batch);
});

test("patches delivered before onPatches() is set are buffered and flushed in order", () => {
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);

  fb.deliver([{ path: [], index: 0 }]);
  fb.deliver([{ path: [0], order: [1, 0] }]);

  const got = [];
  transport.onPatches((patches) => got.push(patches));

  assert.equal(got.length, 2);
  assert.deepEqual(got[0], [{ path: [], index: 0 }]);
  assert.deepEqual(got[1], [{ path: [0], order: [1, 0] }]);
});

test("sendEvent forwards the wire event to the Python side", () => {
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);

  transport.sendEvent({ type: "click", key: "inc", payload: {} });

  assert.equal(fb.pushed.length, 1);
  assert.deepEqual(fb.pushed[0], { type: "click", key: "inc", payload: {} });
});

test("close() stops delivery, drops the handler, and calls the bridge close", async () => {
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  const got = [];
  transport.onPatches((patches) => got.push(patches));

  await transport.close();
  fb.deliver([{ path: [], index: 0 }]);
  transport.sendEvent({ type: "click", key: "inc", payload: {} });

  assert.equal(got.length, 0, "no patches after close");
  assert.equal(fb.pushed.length, 0, "no events after close");
  assert.equal(fb.closedCalls(), 1);
});

test("close() is idempotent", async () => {
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  await transport.close();
  await transport.close();
  assert.equal(fb.closedCalls(), 1);
});
