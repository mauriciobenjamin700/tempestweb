// tempestweb.js — client orchestrator shared by both modes.  PHASE W3/A1/B1.
//
// Wires a transport to the DOM renderer: builds the initial tree under `root`,
// registers a patch handler that applies each tick's batch via dom.js, and binds
// delegated events via events.js. Mode-specific transports (transport-wasm.js /
// transport-ws.js) implement the same `Transport` interface and plug in here
// unchanged — the renderer and event capture are identical across both modes.

import { applyPatches, buildElement } from "./dom.js";
import { bindEvents } from "./events.js";
import { installVirtualization } from "./virtualize.js";

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
 * **Overlay layer (E.3).** A scene is a root tree plus a z-ordered overlay layer
 * (dialogs/sheets/toasts). The core addresses overlays with the reserved leading
 * path step `"overlay"` — `["overlay"]` is the layer, `["overlay", i, ...]` is
 * inside overlay `i`. Those patches are routed to a separate `data-tw-overlays`
 * host appended after the tree (so overlays float above it), with the `"overlay"`
 * step stripped; everything else applies to the tree. Overlay events bubble to
 * `root`, so the delegated event binding covers them too.
 *
 * @param {HTMLElement} root  The host element to mount into.
 * @param {import("./transport.js").Transport} transport  The patch/event seam.
 * @param {import("./transport.js").Node} initialNode  The serialized initial tree.
 * @returns {MountHandle}     A handle to unmount the app.
 */
export function mount(root, transport, initialNode) {
  const tree = buildElement(initialNode);
  root.appendChild(tree);

  // Floating overlay layer — a sibling appended after the tree (so overlays float
  // above it). Created lazily on the first overlay patch so an app with no
  // overlays adds no extra DOM.
  let overlayRoot = null;
  const overlayHost = () => {
    if (overlayRoot === null) {
      overlayRoot = document.createElement("div");
      overlayRoot.setAttribute("data-tw-overlays", "");
      root.appendChild(overlayRoot);
    }
    return overlayRoot;
  };

  const unbind = bindEvents(root, transport);
  const virtualization = installVirtualization(root, transport);

  transport.onPatches((patches) => {
    // Partition the batch: overlay-layer patches (path starts with "overlay")
    // apply to the overlay host with that step stripped; the rest target the tree.
    const treePatches = [];
    const overlayPatches = [];
    for (const patch of patches) {
      if (Array.isArray(patch.path) && patch.path[0] === "overlay") {
        overlayPatches.push({ ...patch, path: patch.path.slice(1) });
      } else {
        treePatches.push(patch);
      }
    }
    if (treePatches.length > 0) {
      applyPatches(tree, treePatches);
    }
    if (overlayPatches.length > 0) {
      applyPatches(overlayHost(), overlayPatches);
    }
    // A slid virtualized window replaced a list's children — re-anchor scroll on
    // the next frame (once the new window is laid out) so it doesn't oscillate.
    if (typeof globalThis.requestAnimationFrame === "function") {
      globalThis.requestAnimationFrame(() => virtualization.reanchor());
    } else {
      Promise.resolve().then(() => virtualization.reanchor());
    }
  });

  return {
    root,
    unmount() {
      unbind();
      virtualization.dispose();
      if (tree.parentNode === root) {
        root.removeChild(tree);
      }
      if (overlayRoot !== null && overlayRoot.parentNode === root) {
        root.removeChild(overlayRoot);
      }
    },
  };
}
