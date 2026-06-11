// transport-wasm.js — Mode A transport over pyodide.ffi.  PHASE A1.
//
// In Mode A the Python reconciler runs in the SAME browser tab (on Pyodide), so
// this transport is an in-process bridge — no network. It adapts the Python
// `WasmTransport` (tempestweb/transports/wasm.py) to the shared `Transport`
// interface from transport.js that the DOM renderer (tempestweb.js) consumes:
//
//   - Patches out (Python -> client): the Python side calls `deliver(patches)`;
//     this transport forwards each batch to the registered `onPatches` handler.
//   - Events in (client -> Python): `sendEvent(ev)` calls the Python side's
//     `push_event`, which enqueues it for the runtime's event loop.
//
// The pyodide.ffi specifics (proxying Python callables, converting a Python list
// of dicts into a JS array of objects) are handled in the `bridge` adapter built
// by public/index.html. This file is bridge-agnostic so it is unit-testable with
// a plain fake bridge under jsdom (no Pyodide). See ../docs/contract.md.

/**
 * @typedef {Object} WasmBridge
 * The thin seam over pyodide.ffi the bootstrap supplies. Every value crossing it
 * is already plain JSON-able (the FFI converts Python dicts/lists to JS
 * objects/arrays), so this transport never touches a Pyodide proxy directly.
 * @property {(handler: (patches: import("./transport.js").Patch[]) => void) => void} onDeliver
 *           Register the JS callback the Python `WasmTransport` invokes with each
 *           patch batch. Called exactly once by the transport at creation.
 * @property {(event: import("./transport.js").TWEvent) => void} pushEvent
 *           Hand a wire event to the Python side (its `push_event`).
 * @property {() => void} [close]
 *           Optional teardown hook (e.g. destroy pyodide proxies).
 */

/**
 * Create a Mode A (WASM) transport bridging the JS client to in-process Python.
 *
 * @param {WasmBridge} bridge  The pyodide.ffi adapter from the bootstrap.
 * @returns {import("./transport.js").Transport}
 */
export function createWasmTransport(bridge) {
  if (!bridge || typeof bridge.onDeliver !== "function" || typeof bridge.pushEvent !== "function") {
    throw new TypeError("createWasmTransport: bridge must provide onDeliver() and pushEvent()");
  }

  /** @type {((patches: import("./transport.js").Patch[]) => void) | null} */
  let patchHandler = null;
  /** @type {import("./transport.js").Patch[][]} */
  const pending = [];
  let closed = false;

  // Register the sink the Python side calls with each patch batch. Batches that
  // arrive before the renderer has registered its handler (e.g. the initial
  // mount race) are buffered and flushed in order once onPatches() lands.
  bridge.onDeliver((patches) => {
    if (closed) return;
    if (patchHandler) {
      patchHandler(patches);
    } else {
      pending.push(patches);
    }
  });

  return {
    /**
     * Register the callback that receives each tick's patch batch.
     * @param {(patches: import("./transport.js").Patch[]) => void} handler
     */
    onPatches(handler) {
      patchHandler = handler;
      while (pending.length > 0) {
        handler(pending.shift());
      }
    },

    /**
     * Send a user event back to the Python side (in-process, no network).
     * @param {import("./transport.js").TWEvent} event
     */
    sendEvent(event) {
      if (closed) return;
      bridge.pushEvent(event);
    },

    /**
     * Tear down the transport.
     * @returns {Promise<void>}
     */
    async close() {
      if (closed) return;
      closed = true;
      patchHandler = null;
      pending.length = 0;
      if (typeof bridge.close === "function") bridge.close();
    },
  };
}
