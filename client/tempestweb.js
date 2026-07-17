// tempestweb.js — client orchestrator shared by both modes.  PHASE W3/A1/B1.
//
// Wires a transport to the DOM renderer: builds the initial tree under `root`,
// registers a patch handler that applies each tick's batch via dom.js, and binds
// delegated events via events.js. Mode-specific transports (transport-wasm.js /
// transport-ws.js) implement the same `Transport` interface and plug in here
// unchanged — the renderer and event capture are identical across both modes.

import { applyPatches, buildElement } from "./dom.js";
import { bindEvents } from "./events.js";
import { installRouter } from "./router.js";
import { installBaseTheme } from "./theme.js";
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
 * **Deferred initial node (Mode B).** In Mode A the caller has the initial
 * `view()` tree (Pyodide built it locally) and passes it as `initialNode`. In Mode
 * B the server sends the initial scene as the first patch batch — a root `Replace`
 * at path `[]` — so omit `initialNode` (or pass `null`) and `mount` consumes that
 * leading root-`Replace` as the initial tree, then applies the rest.
 *
 * **Overlay layer (E.3).** A scene is a root tree plus a z-ordered overlay layer
 * (dialogs/sheets/toasts). The core addresses overlays with the reserved leading
 * path step `"overlay"`; those patches are routed to a separate `data-tw-overlays`
 * host appended after the tree (so overlays float above it), with the `"overlay"`
 * step stripped; everything else applies to the tree. Overlay events bubble to
 * `root`, so the delegated event binding covers them too. The overlay host is
 * created lazily on the first overlay patch, so an app with no overlays adds no
 * extra DOM.
 *
 * **Runtime wiring.** On mount the MD3 base stylesheet is injected once (it styles
 * bare Button/Input/Checkbox widgets and their interaction states, while an app's
 * inline Style still overrides it — see theme.js). When the transport implements
 * `onNavigate` (Mode B, imperative navigation), it is mirrored onto the browser
 * URL; Mode A transports omit it (the bridge wires pushState directly), so that is
 * a no-op there. A frame is scheduled after mount and after each patch batch to
 * recompute the off-window scroll space of any virtualized list, once the browser
 * has laid the window out so item heights can be measured.
 *
 * @param {HTMLElement} root  The host element to mount into.
 * @param {import("./transport.js").Transport} transport  The patch/event seam.
 * @param {import("./transport.js").Node} [initialNode]  The serialized initial
 *        tree (Mode A). Omit to mount from the first root-`Replace` patch (Mode B).
 * @returns {MountHandle}     A handle to unmount the app.
 */
export function mount(root, transport, initialNode = null) {
  installBaseTheme();

  /** @type {HTMLElement | null} */
  let tree = null;
  if (initialNode != null) {
    tree = buildElement(initialNode);
    root.appendChild(tree);
  }

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
  const router = installRouter(transport);
  if (typeof transport.onNavigate === "function") {
    transport.onNavigate((path) => router.navigateTo(path));
  }
  scheduleFrame(virtualization.refresh);

  transport.onPatches((patches) => {
    let batch = patches;
    if (tree == null) {
      const first = patches[0];
      if (first == null || !("node" in first)) {
        throw new TypeError(
          "tempestweb: expected a root Replace as the first patch when mounting " +
            "without an initial node",
        );
      }
      tree = buildElement(first.node);
      root.appendChild(tree);
      batch = patches.slice(1);
    }
    const treePatches = [];
    const overlayPatches = [];
    for (const patch of batch) {
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
    scheduleFrame(virtualization.refresh);
  });

  return {
    root,
    unmount() {
      unbind();
      virtualization.dispose();
      router.dispose();
      if (tree != null && tree.parentNode === root) {
        root.removeChild(tree);
      }
      if (overlayRoot !== null && overlayRoot.parentNode === root) {
        root.removeChild(overlayRoot);
      }
    },
  };
}

/**
 * Run `fn` after the browser has laid out (rAF when available, else a microtask).
 * @param {() => void} fn
 * @returns {void}
 */
function scheduleFrame(fn) {
  if (typeof globalThis.requestAnimationFrame === "function") {
    globalThis.requestAnimationFrame(() => fn());
  } else {
    Promise.resolve().then(fn);
  }
}
