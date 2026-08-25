// tempestweb.js — client orchestrator shared by both modes.  PHASE W3/A1/B1.
//
// Wires a transport to the DOM renderer: builds the initial tree under `root`,
// registers a patch handler that applies each tick's batch via dom.js, and binds
// delegated events via events.js. Mode-specific transports (transport-wasm.js /
// transport-ws.js) implement the same `Transport` interface and plug in here
// unchanged — the renderer and event capture are identical across both modes.

import {
  applyPatches,
  buildElement,
  syncContainerGestures,
  positionAnchoredOverlays,
  repaintCanvases,
} from "./dom.js";
import { bindEvents } from "./events.js";
import { installRouter } from "./router.js";
import { installLayoutStyles } from "./layouts.js";
import { installCameras } from "./camera-widgets.js";
import { installFocusTrap } from "./focus.js";
import { installListEvents } from "./lists.js";
import { installPageViews } from "./pages.js";
import { installMedia } from "./media.js";
import { installBaseTheme } from "./theme.js";
import { installVirtualization } from "./virtualize.js";

/**
 * Is patch debugging on for this page?
 *
 * Read per batch rather than captured once, because the flag exists to be flipped
 * from the console on a page that is *already* misbehaving — a value sampled at
 * mount time could never be turned on in time to see the batch that broke.
 *
 * @returns {boolean}  True when `globalThis.__tempestweb_debug` is truthy.
 */
function patchDebugOn() {
  return Boolean(globalThis.__tempestweb_debug);
}

/**
 * Render a compact outline of the DOM tree the client currently holds.
 *
 * A patch path is a walk of child indices, so the only thing that explains a
 * failed walk is the *shape* the client has: which node sits at each step and how
 * many children it holds. The outline prints exactly that and nothing else — an
 * `outerHTML` dump of a real screen is unreadable and can be megabytes.
 *
 * @param {Element | null} el     The subtree root.
 * @param {number} [maxDepth]     How deep to descend (default 4).
 * @param {number} [depth]        Current depth, for the indent.
 * @returns {string}              One indented `tag[key] (N children)` line per node.
 */
function outlineTree(el, maxDepth = 4, depth = 0) {
  if (el == null) return "<empty>";
  const tag = el.tagName ? el.tagName.toLowerCase() : "?";
  const key = el.getAttribute ? el.getAttribute("data-tw-key") : null;
  const label = key ? `${tag}[${key}]` : tag;
  const line = `${"  ".repeat(depth)}${depth}:${label} (${el.children.length})`;
  if (depth >= maxDepth || el.children.length === 0) return line;
  const children = Array.from(el.children).map((child) =>
    outlineTree(child, maxDepth, depth + 1),
  );
  return [line, ...children].join("\n");
}

/**
 * Is this patch a **root** Replace — an empty path with a replacement node (and
 * none of the other patch fields)?
 * @param {import("./transport.js").Patch} patch  The patch to classify.
 * @returns {boolean}  True for a whole-tree replacement at path `[]`.
 */
function isRootReplace(patch) {
  return (
    Array.isArray(patch.path) &&
    patch.path.length === 0 &&
    "node" in patch &&
    !("index" in patch) &&
    !("order" in patch) &&
    !("set_props" in patch) &&
    !("unset_props" in patch)
  );
}

/**
 * Apply a tree patch batch, following a root Replace so the caller's root
 * reference stays live.
 *
 * A Replace at path `[]` swaps the whole tree: it detaches the old root element
 * and mounts a fresh one. `applyPatches`/`applyReplace` mutate the DOM correctly,
 * but the *reference* the mount holds would still point at the detached old tree
 * — so every later patch in this or a future batch would resolve against a stale
 * subtree and throw `patch path out of range`. This helper rebuilds + swaps the
 * root itself and returns the current root so the mount can keep tracking it;
 * all non-root patches apply in place.
 *
 * A patch that cannot be applied stops the batch: the remaining patches are
 * index-relative to a tree that no longer matches, so applying them would only
 * mutate the wrong nodes. `onError` decides what happens next (the mount asks
 * for a resync).
 *
 * @param {HTMLElement} tree       The current root element.
 * @param {import("./transport.js").Patch[]} patches  The tree patch batch.
 * @param {HTMLElement} mountRoot  The mount host (insertion parent fallback).
 * @param {(error: Error, patch: import("./transport.js").Patch) => void} onError
 *        Called with the first patch that failed.
 * @returns {HTMLElement}          The current root element after the batch.
 */
function applyTreePatches(tree, patches, mountRoot, onError) {
  let current = tree;
  for (const patch of patches) {
    if (isRootReplace(patch)) {
      const fresh = buildElement(patch.node);
      if (current.parentNode) {
        current.parentNode.replaceChild(fresh, current);
      } else {
        mountRoot.insertBefore(fresh, mountRoot.firstChild);
      }
      current = fresh;
    } else {
      let failed = false;
      applyPatches(current, [patch], (error, badPatch) => {
        failed = true;
        onError(error, badPatch);
      });
      if (failed) break;
    }
  }
  return current;
}

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
 * **Broken stream (resync).** A patch the renderer cannot apply means the tree
 * here no longer matches the one the patches were computed against. The batch
 * stops there and, when the transport supports it (Mode B), a resync is
 * requested: the server answers with the whole scene as a root replace. Without
 * it the mount would keep applying index-relative patches to a tree it knows is
 * wrong, and the screen would drift further with every tick.
 *
 * **Runtime wiring.** On mount the MD3 base stylesheet is injected once (it styles
 * bare Button/Input/Checkbox widgets and their interaction states, while an app's
 * inline Style still overrides it — see theme.js). When the transport implements
 * `onNavigate` (Mode B, imperative navigation), it is mirrored onto the browser
 * URL; Mode A transports omit it (the bridge wires pushState directly), so that is
 * a no-op there. A frame is scheduled after mount, after each patch batch and on
 * window resize to recompute what only exists once the browser has laid out: a
 * virtualized list's off-window scroll space, and each Canvas's pixel buffer,
 * which is sized to the box layout gave it so a chart is not a stretched bitmap.
 *
 * @param {HTMLElement} root  The host element to mount into.
 * @param {import("./transport.js").Transport} transport  The patch/event seam.
 * @param {import("./transport.js").Node} [initialNode]  The serialized initial
 *        tree (Mode A). Omit to mount from the first root-`Replace` patch (Mode B).
 * @returns {MountHandle}     A handle to unmount the app.
 */
export function mount(root, transport, initialNode = null) {
  installBaseTheme();
  installLayoutStyles();

  /** @type {HTMLElement | null} */
  let tree = null;
  if (initialNode != null) {
    tree = buildElement(initialNode);
    root.appendChild(tree);
  }

  let overlayRoot = null;
  /**
   * Empty the overlay layer, for a batch that re-sends the whole scene.
   *
   * A resync carries every open overlay as an insert, and an insert *adds*: a
   * dialog that was open before the repair came back a second time, stacked on
   * the first, and each later resync added another. Only a resync clears the
   * layer — an ordinary root Replace from the diff does not re-send overlays it
   * did not change, so clearing there would delete a dialog nothing would put
   * back.
   *
   * @returns {void}
   */
  const clearOverlays = () => {
    if (overlayRoot === null) return;
    while (overlayRoot.firstChild) overlayRoot.removeChild(overlayRoot.firstChild);
  };
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
  const listEvents = installListEvents(root, transport);
  const focusTrap = installFocusTrap(root);
  const cameras = installCameras(root, transport);
  const pageViews = installPageViews(root, transport);
  const router = installRouter(transport);
  if (typeof transport.onNavigate === "function") {
    transport.onNavigate((path) => router.navigateTo(path));
  }
  /**
   * Recompute what only exists after layout: a virtualized list's off-window
   * scroll space, every Canvas's pixel buffer (which is sized to the box the
   * layout gave it, not to the widget's declared size), and the position of any
   * overlay anchored to a widget key.
   * @returns {void}
   */
  const afterLayout = () => {
    virtualization.refresh();
    repaintCanvases(root);
    positionAnchoredOverlays(root);
    syncContainerGestures(root);
    focusTrap.sync();
    cameras.sync();
  };
  scheduleFrame(afterLayout);

  /** Resizing changes every Canvas's box, so their buffers are stale. */
  const onResize = () => scheduleFrame(afterLayout);
  if (typeof globalThis.addEventListener === "function") {
    globalThis.addEventListener("resize", onResize);
  }

  let resyncPending = false;

  /**
   * Handle a patch the renderer could not apply: ask for a whole fresh scene.
   *
   * The DOM is only correct while every patch has applied in order, so once one
   * fails the tree cannot be repaired by the patches that follow — they are
   * index-relative to a tree that no longer exists. A resync (one root replace)
   * is the only repair, and it is requested once until it arrives, so a broken
   * stream cannot turn into a request flood.
   *
   * A transport with no `requestResync` cannot be repaired at all: the failure is
   * reported loudly rather than swallowed, because the screen from that moment on
   * is silently missing whatever the failed batch carried. With
   * `globalThis.__tempestweb_debug` on, the tree the client holds is dumped next
   * to the patch that could not land.
   *
   * @param {Error} error   The failure the patch raised.
   * @param {import("./transport.js").Patch} patch  The patch that failed.
   * @returns {void}
   */
  const onPatchFailure = (error, patch) => {
    if (typeof console !== "undefined" && console.error) {
      console.error("tempestweb: patch could not be applied", error, patch);
      if (patchDebugOn()) {
        console.error("tempestweb: client tree at failure\n" + outlineTree(tree));
      }
    }
    if (resyncPending) return;
    if (typeof transport.requestResync !== "function") {
      if (typeof console !== "undefined" && console.error) {
        console.error(
          "tempestweb: this transport cannot request a resync, so the tree " +
            "stays out of sync with Python until the page reloads",
        );
      }
      return;
    }
    resyncPending = true;
    transport.requestResync();
  };

  let batchSeq = 0;

  transport.onPatches((patches) => {
    batchSeq += 1;
    if (patchDebugOn() && typeof console !== "undefined" && console.log) {
      console.log(`tempestweb: patch batch #${batchSeq}`, patches);
    }
    let batch = patches;
    const isResync = resyncPending && patches.some(isRootReplace);
    if (patches.some(isRootReplace)) resyncPending = false;
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
      tree = applyTreePatches(tree, treePatches, root, onPatchFailure);
    }
    if (isResync) clearOverlays();
    if (overlayPatches.length > 0) {
      applyPatches(overlayHost(), overlayPatches, onPatchFailure);
    }
    scheduleFrame(afterLayout);
  });

  // Installed last, and deliberately: installMedia reports the viewport
  // immediately, and in Mode C that report rebuilds the tree in-process. With no
  // patch sink registered yet those patches were dropped while the runtime's own
  // tree advanced — the DOM stayed at the pre-report render (measured: a Mode C
  // app painted `0 x 0` until the first resize) and every later diff was
  // computed against a tree the DOM did not have.
  const media = installMedia(transport);

  return {
    root,
    unmount() {
      if (typeof globalThis.removeEventListener === "function") {
        globalThis.removeEventListener("resize", onResize);
      }
      unbind();
      virtualization.dispose();
      listEvents.dispose();
      focusTrap.dispose();
      cameras.dispose();
      pageViews.dispose();
      media.dispose();
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
