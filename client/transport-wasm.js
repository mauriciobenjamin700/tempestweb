// transport-wasm.js — Mode A transport over pyodide.ffi.  PHASE A1.
//
// In Mode A the Python reconciler runs in the SAME browser tab (on Pyodide), so
// this transport is an in-process bridge — no network. It adapts the Python
// `WasmTransport` (tempestweb/transports/wasm.py) to the shared `Transport`
// interface from transport.js that the DOM renderer (tempestweb.js) consumes:
//
//   - Patches out (Python -> client): the Python side calls `deliver(batchJson)`
//     with the batch as JSON text; this transport decodes it and forwards it to
//     the registered `onPatches` handler.
//   - Events in (client -> Python): `sendEvent(ev)` calls the Python side's
//     `push_event`, which enqueues it for the runtime's event loop.
//   - Repair (client -> Python): `requestResync()` pushes a `resync` event the
//     runtime serves itself, answering with the whole scene as a root Replace.
//
// The pyodide.ffi specifics (proxying Python callables, converting a Python list
// of dicts into a JS array of objects) are handled in the `bridge` adapter built
// by public/index.html. This file is bridge-agnostic so it is unit-testable with
// a plain fake bridge under jsdom (no Pyodide). See ../docs/contract.md.

import { createWireDecoder } from "./wire.js";

/**
 * @typedef {Object} WasmBridge
 * The thin seam over pyodide.ffi the bootstrap supplies. Every value crossing it
 * is a plain string or a plain JSON-able object, so this transport never touches
 * a Pyodide proxy directly.
 * @property {(handler: (batchJson: string) => void) => void} onDeliver
 *           Register the JS callback the Python `WasmTransport` invokes with each
 *           patch batch, as the JSON **text** Python encoded. Called exactly once
 *           by the transport at creation. The text is decoded here rather than in
 *           the generated bootstrap so a frame that cannot be parsed reaches the
 *           repair path instead of throwing out of the glue (issue #160) — and so
 *           a batch buffered before this transport existed is still decoded with
 *           the resync available.
 * @property {(event: import("./transport.js").TWEvent) => void} pushEvent
 *           Hand a wire event to the Python side (its `push_event`).
 * @property {() => void} [close]
 *           Optional teardown hook (e.g. destroy pyodide proxies).
 */

/**
 * Create a Mode A (WASM) transport bridging the JS client to in-process Python.
 *
 * Registers the sink the Python side calls with each patch batch, decodes the
 * JSON text it carries, and repairs the tree with one resync when a batch cannot
 * be decoded. Batches that arrive before the renderer has registered its handler
 * (e.g. the initial mount race) are buffered and flushed in order once
 * onPatches() lands.
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

  /**
   * Ask the Python side to re-send the whole scene.
   *
   * @returns {void}
   */
  const requestResync = () => {
    if (closed) return;
    bridge.pushEvent({ type: "resync", key: "", payload: {} });
  };

  const decode = createWireDecoder(requestResync, "the Mode A bridge");

  bridge.onDeliver((batchJson) => {
    if (closed) return;
    const decoded = decode(batchJson);
    if (!decoded.ok) return;
    if (patchHandler) {
      patchHandler(decoded.value);
    } else {
      pending.push(decoded.value);
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
     * Ask the Python side to re-send the whole scene.
     *
     * The DOM is only correct while every patch has applied in order, so a batch
     * the renderer could not apply leaves a tree no later index-relative patch
     * fits — without this the Mode A client had no repair and stayed truncated
     * for the rest of the page's life, every following tick failing the same way.
     *
     * The request travels as an ordinary wire event, exactly like Mode B's: the
     * runtime serves `resync` itself instead of routing it to an app handler, so
     * the empty `key` never has to resolve to a widget.
     *
     * @returns {void}
     */
    requestResync,

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
