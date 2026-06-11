// tempestweb.js — client orchestrator shared by both modes.  PHASE W3/A1/B1.
//
// Wires a transport to the DOM renderer: builds the initial tree, applies patch
// batches via dom.js, and binds events via events.js. Mode-specific transports
// (transport-wasm.js / transport-ws.js) plug in here.

import { applyPatches, buildElement } from "./dom.js";
import { bindEvents } from "./events.js";

/**
 * Mount a tempestweb app onto `root` using the given transport.
 * @param {HTMLElement} root
 * @param {import("./transport.js").Transport} transport
 * @param {import("./transport.js").Node} initialNode
 * @returns {void}
 */
export function mount(root, transport, initialNode) {
  throw new Error("W3/A1: mount not implemented");
}
