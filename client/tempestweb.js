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
 * **Deferred initial node (Mode B).** In Mode A the caller has the initial
 * `view()` tree in hand (Pyodide built it locally) and passes it as `initialNode`.
 * In Mode B the server sends the initial scene as the first patch batch — a single
 * `Replace` at the root path `[]` carrying the whole tree (see
 * `scene_to_initial_patches`). For that case omit `initialNode` (or pass `null`):
 * `mount` consumes the first batch's leading root-`Replace` as the initial tree and
 * applies any remaining patches (e.g. overlay inserts) to it. This keeps a single
 * `transport.onPatches` registration and avoids swapping an already-mounted root
 * out from under the renderer.
 *
 * @param {HTMLElement} root  The host element to mount into.
 * @param {import("./transport.js").Transport} transport  The patch/event seam.
 * @param {import("./transport.js").Node} [initialNode]  The serialized initial
 *        tree (Mode A). Omit to mount from the first root-`Replace` patch (Mode B).
 * @returns {MountHandle}     A handle to unmount the app.
 */
export function mount(root, transport, initialNode = null) {
  /** @type {HTMLElement | null} */
  let tree = null;
  if (initialNode != null) {
    tree = buildElement(initialNode);
    root.appendChild(tree);
  }

  const unbind = bindEvents(root, transport);

  transport.onPatches((patches) => {
    let rest = patches;
    if (tree == null) {
      // Deferred initial mount (Mode B): the first batch's leading patch is the
      // root Replace carrying the whole tree. Build it as the initial subtree
      // instead of replacing an existing one, then apply the remaining patches.
      const first = patches[0];
      if (first == null || !("node" in first)) {
        throw new TypeError(
          "tempestweb: expected a root Replace as the first patch when mounting " +
            "without an initial node",
        );
      }
      tree = buildElement(first.node);
      root.appendChild(tree);
      rest = patches.slice(1);
    }
    if (rest.length > 0) {
      // Patch paths are rooted at the mounted tree, not at `root`'s wrapper.
      applyPatches(tree, rest);
    }
  });

  return {
    root,
    unmount() {
      unbind();
      if (tree != null && tree.parentNode === root) {
        root.removeChild(tree);
      }
    },
  };
}
