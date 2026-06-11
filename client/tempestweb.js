// tempestweb.js — client orchestrator shared by both modes.  PHASE W3/A1/B1.
//
// Wires a transport to the DOM renderer: builds the initial tree under `root`,
// registers a patch handler that applies each tick's batch via dom.js, and binds
// delegated events via events.js. Mode-specific transports (transport-wasm.js /
// transport-ws.js) implement the same `Transport` interface and plug in here
// unchanged — the renderer and event capture are identical across both modes.

import { applyPatches, buildElement } from "./dom.js";
import { bindEvents } from "./events.js";

/**
 * @typedef {Object} MountHandle
 * @property {HTMLElement} root  The mounted root element (the initial tree's host).
 * @property {() => void} unmount  Tear down: unbind events and clear the tree.
 */

/**
 * Mount a tempestweb app onto `root` using the given transport.
 *
 * Steps, in order:
 *  1. Build the initial DOM subtree from `initialNode` and append it to `root`.
 *  2. Bind delegated DOM events so user interactions flow to `transport.sendEvent`.
 *  3. Register the transport's patch callback to apply each batch to the tree.
 *
 * Patches target the mounted subtree, so a patch `path` of `[]` is the
 * `initialNode`'s element (the first child of `root`), `[0]` its first child, etc.
 *
 * @param {HTMLElement} root  The host element to mount into.
 * @param {import("./transport.js").Transport} transport  The patch/event seam.
 * @param {import("./transport.js").Node} initialNode  The serialized initial tree.
 * @returns {MountHandle}     A handle to unmount the app.
 */
export function mount(root, transport, initialNode) {
  const tree = buildElement(initialNode);
  root.appendChild(tree);

  const unbind = bindEvents(root, transport);

  transport.onPatches((patches) => {
    // Patch paths are rooted at the mounted tree, not at `root`'s wrapper.
    applyPatches(tree, patches);
  });

  return {
    root,
    unmount() {
      unbind();
      if (tree.parentNode === root) {
        root.removeChild(tree);
      }
    },
  };
}
