// dom.js — build a DOM tree from the Node IR and apply patch batches to it. W1.
//
// buildElement(node) turns one serialized Node into a live DOM element (recursing
// into children); applyPatches(root, patches) mutates a tree in place. Given the
// DOM built from node_initial.json, applying patches_all_kinds.json yields the
// expected DOM. Patch kinds are distinguished by key presence (see transport.js):
//   - set_props present       -> Update
//   - node + index present     -> Insert
//   - index only               -> Remove
//   - order present            -> Reorder
//   - node without index       -> Replace
//
// Every element carries `data-tw-key` when its Node has a key, so events.js can
// read the originating widget key via event delegation. Verify against
// ../tests/fixtures/ in tests/client/ (jsdom). No framework.

import { styleToCss } from "./style.js";

/** Attribute holding a widget's stable reconciliation key. */
export const KEY_ATTR = "data-tw-key";
/** Attribute holding a widget's IR type (so patches can re-key/inspect it). */
export const TYPE_ATTR = "data-tw-type";

// Each widget type maps to one HTML tag. Container-like widgets are <div>; Text is
// an inline <span>; Button is a real <button>. Unknown types fall back to <div> so
// a new core widget renders (as a generic box) rather than throwing.
const TAG_BY_TYPE = Object.freeze({
  Column: "div",
  Row: "div",
  Container: "div",
  Stack: "div",
  Text: "span",
  Button: "button",
  Input: "input",
  Checkbox: "input",
  Image: "img",
});

/**
 * Resolve the HTML tag name for an IR widget type.
 * @param {string} type  The widget type ("Column", "Text", "Button", ...).
 * @returns {string}     The HTML tag name (defaults to "div").
 */
function tagForType(type) {
  return TAG_BY_TYPE[type] ?? "div";
}

/**
 * Apply a node's props to an element: style, key/type attributes and text.
 *
 * `content` (Text) and `label` (Button) become the element's text. The `style`
 * prop is translated by {@link styleToCss} into the inline `style` attribute. The
 * widget `key` and `type` are mirrored onto data attributes for event delegation.
 *
 * @param {HTMLElement} el      The target element.
 * @param {string} type         The widget type.
 * @param {?string} key         The widget key, or null.
 * @param {Object} props        The widget props (may include `style`).
 * @returns {void}
 */
function applyNodeShape(el, type, key, props) {
  el.setAttribute(TYPE_ATTR, type);
  if (key != null) {
    el.setAttribute(KEY_ATTR, key);
  } else {
    el.removeAttribute(KEY_ATTR);
  }
  applyProps(el, props ?? {});
}

/**
 * Apply a bag of props onto an element (style + text-bearing props).
 *
 * Used both when first building an element and by Update patches. `style` is
 * (re)translated to CSS; `content`/`label` set the text. Other keys are widget
 * metadata the DOM does not render and are ignored.
 *
 * @param {HTMLElement} el     The target element.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyProps(el, props) {
  if ("style" in props) {
    const css = styleToCss(props.style);
    if (css) {
      el.style.cssText = css;
    } else {
      el.removeAttribute("style");
    }
  }
  const type = el.getAttribute(TYPE_ATTR);
  // Text-bearing props. A Checkbox is an <input> and cannot hold text, so its
  // label rides as an accessible name instead of textContent.
  if ("content" in props) {
    el.textContent = props.content == null ? "" : String(props.content);
  }
  if ("label" in props) {
    if (type === "Checkbox") {
      el.setAttribute("aria-label", props.label == null ? "" : String(props.label));
    } else {
      el.textContent = props.label == null ? "" : String(props.label);
    }
  }
  applyControlProps(el, type, props);
}

/**
 * Apply form-control / media props (Input, Checkbox, Image) onto an element.
 *
 * Maps the widget's typed props onto the right DOM property/attribute so the
 * control is actually interactive (a real <input> holding `value`, a checkbox
 * reflecting `checked`, an <img> pointing at `src`). No-ops for other types.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type (from the data-tw-type attribute).
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyControlProps(el, type, props) {
  if (type === "Input") {
    el.setAttribute("type", props.secure ? "password" : "text");
    if ("value" in props) {
      el.value = props.value == null ? "" : String(props.value);
    }
    if ("placeholder" in props && props.placeholder != null) {
      el.setAttribute("placeholder", String(props.placeholder));
    }
    if (props.max_length != null) {
      el.setAttribute("maxlength", String(props.max_length));
    }
  } else if (type === "Checkbox") {
    el.setAttribute("type", "checkbox");
    if ("checked" in props) {
      el.checked = Boolean(props.checked);
    }
  } else if (type === "Image") {
    if ("src" in props && props.src != null) {
      el.setAttribute("src", String(props.src));
    }
    if ("alt" in props && props.alt != null) {
      el.setAttribute("alt", String(props.alt));
    }
  }
}

/**
 * Build a DOM element from an IR node (recursing into its children).
 * @param {import("./transport.js").Node} node  The serialized node.
 * @returns {HTMLElement}                        The constructed element subtree.
 */
export function buildElement(node) {
  const el = document.createElement(tagForType(node.type));
  applyNodeShape(el, node.type, node.key ?? null, node.props ?? {});
  for (const child of node.children ?? []) {
    el.appendChild(buildElement(child));
  }
  return el;
}

/**
 * Walk a path of child indices from `root` down to the target element.
 * @param {HTMLElement} root      The root element.
 * @param {number[]} path         Child indices from the root ([] = root).
 * @returns {HTMLElement}         The element at `path`.
 * @throws {RangeError}           If an index does not resolve to an element.
 */
function resolvePath(root, path) {
  /** @type {HTMLElement} */
  let el = root;
  for (const index of path) {
    const next = el.children[index];
    if (next == null) {
      throw new RangeError(`tempestweb: patch path out of range at index ${index}`);
    }
    el = /** @type {HTMLElement} */ (next);
  }
  return el;
}

/**
 * Apply a single Update patch: set/unset props on the node at `path`.
 * @param {HTMLElement} root  The root element.
 * @param {{path:number[], set_props?:Object, unset_props?:string[]}} patch  The patch.
 * @returns {void}
 */
function applyUpdate(root, patch) {
  const el = resolvePath(root, patch.path);
  if (patch.set_props) {
    applyProps(el, patch.set_props);
  }
  for (const key of patch.unset_props ?? []) {
    if (key === "style") {
      el.removeAttribute("style");
    } else if (key === "content" || key === "label") {
      el.textContent = "";
    }
  }
}

/**
 * Apply a single Insert patch: insert a new child at `index` under `path`.
 * @param {HTMLElement} root  The root element.
 * @param {{path:number[], index:number, node:import("./transport.js").Node}} patch
 * @returns {void}
 */
function applyInsert(root, patch) {
  const parent = resolvePath(root, patch.path);
  const child = buildElement(patch.node);
  const ref = parent.children[patch.index] ?? null;
  parent.insertBefore(child, ref);
}

/**
 * Apply a single Remove patch: remove the child at `index` under `path`.
 * @param {HTMLElement} root  The root element.
 * @param {{path:number[], index:number}} patch  The patch.
 * @returns {void}
 */
function applyRemove(root, patch) {
  const parent = resolvePath(root, patch.path);
  const child = parent.children[patch.index];
  if (child != null) {
    parent.removeChild(child);
  }
}

/**
 * Apply a single Reorder patch: new child `i` = old child `order[i]`.
 *
 * Snapshots the current children first so indices in `order` refer to the
 * pre-reorder positions, then re-appends them in the requested order.
 *
 * @param {HTMLElement} root  The root element.
 * @param {{path:number[], order:number[]}} patch  The patch.
 * @returns {void}
 */
function applyReorder(root, patch) {
  const parent = resolvePath(root, patch.path);
  const before = Array.from(parent.children);
  for (const index of patch.order) {
    const child = before[index];
    if (child != null) {
      parent.appendChild(child);
    }
  }
}

/**
 * Apply a single Replace patch: swap the element at `path` for a fresh subtree.
 * @param {HTMLElement} root  The root element.
 * @param {{path:number[], node:import("./transport.js").Node}} patch  The patch.
 * @returns {void}
 */
function applyReplace(root, patch) {
  const old = resolvePath(root, patch.path);
  const fresh = buildElement(patch.node);
  if (old.parentNode) {
    old.parentNode.replaceChild(fresh, old);
  }
}

/**
 * Classify a patch by key presence and dispatch it to the right applier.
 * @param {HTMLElement} root                   The root element.
 * @param {import("./transport.js").Patch} patch  The patch to apply.
 * @returns {void}
 * @throws {TypeError}                          If the patch shape is unrecognized.
 */
function applyPatch(root, patch) {
  if ("set_props" in patch || "unset_props" in patch) {
    applyUpdate(root, /** @type {any} */ (patch));
  } else if ("order" in patch) {
    applyReorder(root, /** @type {any} */ (patch));
  } else if ("node" in patch && "index" in patch) {
    applyInsert(root, /** @type {any} */ (patch));
  } else if ("node" in patch) {
    applyReplace(root, /** @type {any} */ (patch));
  } else if ("index" in patch) {
    applyRemove(root, /** @type {any} */ (patch));
  } else {
    throw new TypeError(`tempestweb: unrecognized patch shape ${JSON.stringify(patch)}`);
  }
}

/**
 * Apply a coalesced batch of patches to the DOM tree rooted at `root`.
 *
 * The reconciler coalesces a tick's mutations into one ordered list; the whole
 * list is applied before the next frame. Patches are applied in array order — the
 * order the core emitted them — so index-relative ops (insert/remove/reorder)
 * stay consistent.
 *
 * @param {HTMLElement} root                       The mounted root element.
 * @param {import("./transport.js").Patch[]} patches  The tick's patch batch.
 * @returns {void}
 */
export function applyPatches(root, patches) {
  for (const patch of patches) {
    applyPatch(root, patch);
  }
}
