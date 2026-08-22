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

import { createIconSvg, renderIcon } from "./icons/index.js";
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
  // A Checkbox renders as a <label> wrapping a real <input type=checkbox> plus
  // its caption text, so the box and its label show side by side and the input
  // gets its accessible name natively. The <label> is the keyed, path-addressed
  // element; the input it wraps is renderer-internal (Checkbox is an IR leaf, so
  // no patch path ever descends into it).
  Checkbox: "label",
  Image: "img",
  // A Canvas renders to a real <canvas>; its draw-command list is executed onto
  // the 2D context by paintCanvas (charts, overlays, the sketch pad).
  Canvas: "canvas",
  // A ProgressBar is a <div> track holding one renderer-owned fill element; a
  // Spinner is a <div> the base theme paints as a ring. Both are IR leaves, so
  // no patch path ever descends into what the renderer puts inside them.
  ProgressBar: "div",
  Spinner: "div",
  // Draggable/DragTarget are plain boxes; what makes them work is the HTML5
  // drag contract applied by applyDragProps + the listeners in events.js.
  Draggable: "div",
  DragTarget: "div",
});

// Font stack for Canvas draw_text commands (a literal, since a 2D context cannot
// read the --tw-font CSS variable). Mirrors the base theme's family.
const CANVAS_FONT = "Roboto, 'Segoe UI', system-ui, -apple-system, sans-serif";

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
 * For text-bearing props, a Checkbox is a <label> wrapping an <input>, so its
 * caption is set as a trailing text node (see setCheckboxLabel) rather than
 * overwriting textContent, which would drop the nested input. An Icon is an inline
 * <svg> whose glyph is (re)drawn when its name or size changes; a style-only
 * update leaves the existing glyph untouched.
 *
 * @param {HTMLElement} el     The target element.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyProps(el, props) {
  const type = el.getAttribute(TYPE_ATTR);
  if ("style" in props) {
    const css = styleToCss(props.style, type);
    if (css) {
      el.style.cssText = css;
    } else {
      el.removeAttribute("style");
    }
  }
  if ("content" in props) {
    el.textContent = props.content == null ? "" : String(props.content);
  }
  if ("label" in props) {
    if (type === "Checkbox") {
      setCheckboxLabel(el, props.label == null ? "" : String(props.label));
    } else {
      el.textContent = props.label == null ? "" : String(props.label);
    }
  }
  if (type === "Icon" && ("name" in props || "size" in props)) {
    renderIcon(/** @type {any} */ (el), props);
  }
  applyIndicatorProps(el, type, props);
  applyControlProps(el, type, props);
  applyDragProps(el, type, props);
  applyA11yProps(el, props);
  applyEscapeHatchAttrs(el, props);
  applyLazyProps(el, type, props);
}

/** Attribute carrying a `Draggable`'s payload, read by the dragstart listener. */
export const DRAG_DATA_ATTR = "data-tw-drag-data";
/** Attribute marking a `DragTarget`, read by the dragover/drop listeners. */
export const DROP_TARGET_ATTR = "data-tw-drop";

/**
 * Apply the HTML5 drag-and-drop contract for `Draggable` / `DragTarget`.
 *
 * The core has always had both widgets and the SSR renderer emitted their boxes,
 * but the DOM renderer treated them as anonymous `div`s: nothing was marked
 * `draggable`, so a "draggable" card could not be picked up in any mode, and a
 * `DragTarget` never accepted a drop. The board rendered and did nothing.
 *
 * A `Draggable` becomes a real draggable element carrying its payload in
 * {@link DRAG_DATA_ATTR}; `events.js` reads it on `dragstart` and hands it to the
 * `DragTarget` marked with {@link DROP_TARGET_ATTR} on `drop`. The grab cursor is
 * a default only — an explicit Style on the widget wins, and it is re-applied on
 * every update because a `style` patch resets the element's inline cssText.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyDragProps(el, type, props) {
  if (type === "Draggable") {
    el.setAttribute("draggable", "true");
    if ("drag_data" in props) {
      const data = props.drag_data;
      el.setAttribute(DRAG_DATA_ATTR, data == null ? "" : String(data));
    } else if (!el.hasAttribute(DRAG_DATA_ATTR)) {
      el.setAttribute(DRAG_DATA_ATTR, "");
    }
    if (!el.style.cursor) {
      el.style.cursor = "grab";
    }
  } else if (type === "DragTarget") {
    el.setAttribute(DROP_TARGET_ATTR, "");
  }
}

/** Valid HTML attribute name — mirrors `_ATTR_KEY_RE` in the SSR renderer. */
const ATTR_NAME_RE = /^[a-zA-Z][a-zA-Z0-9:_-]*$/;

/** Attributes this renderer owns; `attrs` may never overwrite them. */
const RESERVED_ATTRS = new Set([TYPE_ATTR, KEY_ATTR, "style"]);

/**
 * Inline event-handler attributes (`onclick`, `onerror`, …), refused by `attrs`.
 *
 * `attrs` is an escape hatch for markup an app owns — `id`, `class`, `data-*`,
 * `hx-*`. An `on*` value is *code*, so a widget built from data the app did not
 * write (a row label, a remote field) would execute it. The SSR renderer refuses
 * the same names, so a tree behaves identically whichever renderer draws it.
 */
const EVENT_HANDLER_ATTR_RE = /^on/i;

/**
 * Apply the core's `attrs` escape hatch (`id`, `class`, `data-*`, `hx-*`, …).
 *
 * Every widget carries an `attrs` dict, and the SSR renderer has always emitted
 * it; the DOM renderer used to drop it, so the same tree gained attributes when
 * server-rendered and lost them in Modes A/B/C. This closes that gap, which is
 * also what lets the layout presets tag their subtrees (`data-tw-layout`) for
 * `client/layouts.js` to style responsively.
 *
 * Attributes previously set from `attrs` and absent from the new dict are
 * removed, so an Update that drops a key does not leave it stranded on the
 * element. Names are validated against the same pattern the SSR renderer
 * enforces — an invalid name is skipped with a warning rather than throwing,
 * since a bad key must not take down a live re-render — and the renderer's own
 * attributes are never overwritten.
 *
 * @param {HTMLElement} el   The target element.
 * @param {Object} props     The props to apply.
 * @returns {void}
 */
function applyEscapeHatchAttrs(el, props) {
  if (!("attrs" in props)) return;
  const attrs = props.attrs || {};
  const previous = el.__twAttrs;
  const applied = new Set();
  for (const [name, value] of Object.entries(attrs)) {
    if (!ATTR_NAME_RE.test(name)) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn(`tempestweb: ignoring invalid attribute name in attrs: ${name}`);
      }
      continue;
    }
    if (EVENT_HANDLER_ATTR_RE.test(name)) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn(
          `tempestweb: ignoring inline event-handler attribute in attrs: ${name}`,
        );
      }
      continue;
    }
    if (RESERVED_ATTRS.has(name)) continue;
    el.setAttribute(name, value == null ? "" : String(value));
    applied.add(name);
  }
  if (previous) {
    for (const name of previous) {
      if (!applied.has(name)) el.removeAttribute(name);
    }
  }
  el.__twAttrs = applied;
}

/**
 * Apply accessibility props (semantics + focus) onto an element.
 *
 * Maps the core's renderer-agnostic a11y model to ARIA/DOM: ``semantics.label``
 * → ``aria-label``, ``semantics.role`` → ``role``, ``semantics.hint`` →
 * ``aria-description``; ``focus_order`` sets an explicit ``tabindex`` and
 * ``focusable`` toggles a default one (``0`` to include, ``-1`` to exclude).
 *
 * @param {HTMLElement} el     The target element.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyA11yProps(el, props) {
  if ("semantics" in props) {
    const sem = props.semantics;
    const semantics = sem != null && typeof sem === "object" ? sem : {};
    setOrRemove(el, "aria-label", semantics.label);
    setOrRemove(el, "role", semantics.role);
    setOrRemove(el, "aria-description", semantics.hint);
  }
  if (!("focus_order" in props) && !("focusable" in props)) return;
  if (props.focus_order != null) {
    el.setAttribute("tabindex", String(props.focus_order));
  } else if (props.focusable === true) {
    el.setAttribute("tabindex", "0");
  } else if (props.focusable === false) {
    el.setAttribute("tabindex", "-1");
  } else {
    el.removeAttribute("tabindex");
  }
}

/**
 * Set an attribute, or remove it when the value is `null`/`undefined`.
 *
 * The IR keeps a widget's prop set fixed, so a prop the app stops passing comes
 * across as `null` rather than disappearing. Treating that as "leave the old
 * value alone" is what let a cleared `semantics` keep announcing a stale
 * `aria-label`, and a cleared `max_length` keep capping an input — the DOM held
 * state the tree no longer described.
 *
 * @param {HTMLElement} el     The target element.
 * @param {string} name        The attribute name.
 * @param {*} value            The value, or null/undefined to remove it.
 * @returns {void}
 */
function setOrRemove(el, name, value) {
  if (value == null) {
    el.removeAttribute(name);
  } else {
    el.setAttribute(name, String(value));
  }
}

/**
 * Apply form-control / media / canvas props (Canvas, Input, Checkbox, Image).
 *
 * Maps the widget's typed props onto the right DOM property/attribute so the
 * control is actually interactive (a real <input> holding `value`, a checkbox
 * reflecting `checked`, an <img> pointing at `src`) or, for a Canvas, paints its
 * draw-command list onto the 2D context. No-ops for other types.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type (from the data-tw-type attribute).
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
// Virtualized list widgets: rendered as scroll viewports whose visible window
// the runtime slides in response to scroll events (see client/virtualize.js).
const LAZY_TYPES = Object.freeze(["LazyColumn", "LazyRow", "LazyGrid"]);

/**
 * Mark a virtualized list element and mirror its windowing metadata to data
 * attributes so the scroll controller can compute the visible window.
 *
 * The element becomes a bounded, scrollable viewport: the app's Style sets the
 * extent (e.g. height), overflow scrolls the materialized window, and scrolling
 * past the edge slides the window (see client/virtualize.js). `min-height:0` stops
 * a flex parent from growing the viewport to fit its content instead of scrolling.
 * The `window` prop is `[start, end)` when slid, or null (start at 0).
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyLazyProps(el, type, props) {
  if (type == null || !LAZY_TYPES.includes(type)) {
    return;
  }
  const horizontal = type === "LazyRow";
  el.style.overflowY = horizontal ? "hidden" : "auto";
  el.style.overflowX = horizontal ? "auto" : "hidden";
  el.style.minHeight = "0";
  if ("item_count" in props) {
    setOrRemove(el, "data-tw-item-count", props.item_count);
  }
  if ("window_size" in props) {
    setOrRemove(el, "data-tw-window-size", props.window_size);
  }
  const start = Array.isArray(props.window) ? props.window[0] : 0;
  el.setAttribute("data-tw-window-start", String(start ?? 0));
}

/** Widget types the base theme paints as progress indicators. */
const INDICATOR_TYPES = ["ProgressBar", "Spinner"];

/**
 * Get (or lazily create) the fill element inside a ProgressBar's track.
 *
 * The track is the keyed, path-addressed element; this fill is
 * renderer-owned, exactly like the input nested in a Checkbox's label.
 * A ProgressBar is an IR leaf, so no patch path descends into it and nothing
 * upstream can collide with what lives here.
 *
 * @param {HTMLElement} el  The ProgressBar track element.
 * @returns {HTMLElement}   The fill element.
 */
function ensureProgressFill(el) {
  let fill = /** @type {HTMLElement|null} */ (el.querySelector("[data-tw-part=\"fill\"]"));
  if (fill == null) {
    fill = document.createElement("div");
    fill.setAttribute("data-tw-part", "fill");
    el.appendChild(fill);
  }
  return fill;
}

/**
 * Paint a ProgressBar or a Spinner from its props.
 *
 * Both widgets carry a ``color_scheme`` the core leaves unresolved — the
 * renderer decides what the family means. Here it becomes a
 * ``data-tw-scheme`` attribute the base theme keys its accent off, so a change
 * of family is a CSS variable swap rather than an inline color the app's own
 * Style could not override.
 *
 * A determinate bar's fill is sized by percentage width, which is what makes it
 * animate smoothly under the theme's transition; an indeterminate one drops the
 * width entirely and is animated by the sheet. ``aria-valuenow`` is written only
 * when there is a value to report — an indeterminate bar that claimed a number
 * would be read out as progress that is not being measured.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyIndicatorProps(el, type, props) {
  if (type == null || !INDICATOR_TYPES.includes(type)) {
    return;
  }
  if ("color_scheme" in props) {
    setOrRemove(el, "data-tw-scheme", props.color_scheme);
  }
  if (type === "Spinner") {
    if ("size" in props) {
      const size = props.size;
      if (size == null) {
        el.style.removeProperty("width");
        el.style.removeProperty("height");
      } else {
        el.style.width = `${Number(size)}px`;
        el.style.height = `${Number(size)}px`;
      }
    }
    if (!el.hasAttribute("role")) {
      el.setAttribute("role", "progressbar");
    }
    return;
  }
  const indeterminate = Boolean(props.indeterminate);
  if ("indeterminate" in props) {
    if (indeterminate) {
      el.setAttribute("data-tw-indeterminate", "");
    } else {
      el.removeAttribute("data-tw-indeterminate");
    }
  }
  if (!el.hasAttribute("role")) {
    el.setAttribute("role", "progressbar");
    el.setAttribute("aria-valuemin", "0");
    el.setAttribute("aria-valuemax", "1");
  }
  const fill = ensureProgressFill(el);
  if (el.hasAttribute("data-tw-indeterminate")) {
    el.removeAttribute("aria-valuenow");
    fill.style.removeProperty("width");
    return;
  }
  if ("value" in props) {
    const value = Math.min(Math.max(Number(props.value) || 0, 0), 1);
    el.setAttribute("aria-valuenow", String(value));
    fill.style.width = `${value * 100}%`;
  }
}

/**
 * Get (or lazily create) the real ``<input type=checkbox>`` nested inside a
 * Checkbox's ``<label>`` wrapper. The label is the keyed, path-addressed
 * element; this nested input carries the actual ``checked`` state and fires the
 * native ``change`` event (which bubbles up to the keyed label for delegation).
 *
 * @param {HTMLElement} el  The Checkbox ``<label>`` element.
 * @returns {HTMLInputElement}  The nested checkbox input.
 */
function ensureCheckboxInput(el) {
  let input = /** @type {HTMLInputElement|null} */ (el.querySelector("input"));
  if (input == null) {
    input = /** @type {HTMLInputElement} */ (document.createElement("input"));
    input.setAttribute("type", "checkbox");
    el.insertBefore(input, el.firstChild);
  }
  return input;
}

/**
 * Set a Checkbox's visible caption, kept as a single text node after the nested
 * input so the box and its label render side by side. Wrapping the input in the
 * ``<label>`` also gives it its accessible name natively (no ``aria-label``).
 *
 * @param {HTMLElement} el    The Checkbox ``<label>`` element.
 * @param {string} text       The caption text (``""`` clears it).
 * @returns {void}
 */
function setCheckboxLabel(el, text) {
  const input = ensureCheckboxInput(el);
  for (const node of Array.from(el.childNodes)) {
    if (node !== input) {
      el.removeChild(node);
    }
  }
  if (text) {
    el.appendChild(document.createTextNode(text));
  }
}

/**
 * Convert a core color (RGBA channels as floats in [0, 1]) to a CSS `rgba()`.
 *
 * @param {?number[]} c  ``[r, g, b, a]`` with each channel in ``[0, 1]``; alpha
 *                       defaults to ``1`` when absent.
 * @returns {string}     A CSS ``rgba(...)`` string (transparent when malformed).
 */
function canvasColor(c) {
  if (!Array.isArray(c) || c.length < 3) {
    return "rgba(0,0,0,0)";
  }
  const r = Math.round(c[0] * 255);
  const g = Math.round(c[1] * 255);
  const b = Math.round(c[2] * 255);
  const a = c.length > 3 && c[3] != null ? c[3] : 1;
  return `rgba(${r},${g},${b},${a})`;
}

/**
 * Paint a Canvas widget's draw-command list onto its ``<canvas>`` 2D context.
 *
 * The command list is an immediate-mode path program mirroring the core's Canvas
 * API: ``move_to``/``line_to`` build the current path, ``draw_rect`` adds a
 * rectangle, ``stroke``/``fill`` paint it, and ``draw_text`` writes a label.
 * Width, height and commands are remembered on the element so an Update patch
 * that changes only one of them still repaints the whole canvas — setting a
 * canvas's width/height resets its drawing buffer, so a full repaint is always
 * required. A no-op when the 2D context is unavailable (e.g. a jsdom harness
 * without canvas support).
 *
 * @param {HTMLCanvasElement} el  The Canvas element.
 * @param {Object} props          Props that may include width/height/commands.
 * @returns {void}
 */
function paintCanvas(el, props) {
  if ("width" in props && props.width != null) {
    el._twCanvasW = Number(props.width);
  }
  if ("height" in props && props.height != null) {
    el._twCanvasH = Number(props.height);
  }
  if ("commands" in props && Array.isArray(props.commands)) {
    el._twCanvasCmds = props.commands;
  }
  if (el._twCanvasW != null) {
    el.width = el._twCanvasW;
  }
  if (el._twCanvasH != null) {
    el.height = el._twCanvasH;
  }
  const ctx = typeof el.getContext === "function" ? el.getContext("2d") : null;
  if (ctx == null) {
    return;
  }
  ctx.clearRect(0, 0, el.width, el.height);
  for (const cmd of el._twCanvasCmds ?? []) {
    switch (cmd.kind) {
      case "move_to":
        ctx.beginPath();
        ctx.moveTo(cmd.x, cmd.y);
        break;
      case "line_to":
        ctx.lineTo(cmd.x, cmd.y);
        break;
      case "draw_rect":
        ctx.beginPath();
        ctx.rect(cmd.x, cmd.y, cmd.width, cmd.height);
        break;
      case "stroke":
        ctx.strokeStyle = canvasColor(cmd.color);
        ctx.lineWidth = cmd.width != null ? cmd.width : 1;
        ctx.stroke();
        break;
      case "fill":
        ctx.fillStyle = canvasColor(cmd.color);
        ctx.fill();
        break;
      case "draw_text":
        ctx.fillStyle = canvasColor(cmd.color);
        ctx.font = `${cmd.size != null ? cmd.size : 12}px ${CANVAS_FONT}`;
        ctx.fillText(String(cmd.text), cmd.x, cmd.y);
        break;
      default:
        break;
    }
  }
}

/**
 * Apply widget-type-specific control props (Canvas/Input/Checkbox/Image).
 *
 * For a Checkbox, the box and caption are laid out on one line as a block-level
 * flex row so stacked checkboxes each get their own line (an inline default would
 * let adjacent labels flow together in a non-flex parent). These are defaults
 * only — an explicit Style on the widget (applied just before this) wins — and
 * they are re-applied on every update because a `style` patch resets the element's
 * inline cssText. The width is set to `fit-content` so the <label>, as a flex item
 * of a column, does not collapse to the input's width and overflow the caption
 * onto the next row.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyControlProps(el, type, props) {
  if (type === "Canvas") {
    paintCanvas(el, props);
  } else if (type === "Input") {
    el.setAttribute("type", props.secure ? "password" : "text");
    if ("value" in props) {
      el.value = props.value == null ? "" : String(props.value);
    }
    if ("placeholder" in props) {
      setOrRemove(el, "placeholder", props.placeholder);
    }
    if ("max_length" in props) {
      setOrRemove(el, "maxlength", props.max_length);
    }
  } else if (type === "Checkbox") {
    const input = ensureCheckboxInput(el);
    if ("checked" in props) {
      input.checked = Boolean(props.checked);
    }
    if (!el.style.display) {
      el.style.display = "flex";
    }
    if (!el.style.alignItems) {
      el.style.alignItems = "center";
    }
    if (!el.style.gap) {
      el.style.gap = "0.4em";
    }
    if (!el.style.width) {
      el.style.width = "fit-content";
    }
  } else if (type === "Image") {
    if ("src" in props) {
      setOrRemove(el, "src", props.src);
    }
    if ("alt" in props) {
      setOrRemove(el, "alt", props.alt);
    }
  }
}

/**
 * Build a DOM element from an IR node (recursing into its children).
 *
 * An Icon is an inline <svg>, which must be created in the SVG namespace (not via
 * createElement); it is an IR leaf, so no children are recursed into it.
 *
 * @param {import("./transport.js").Node} node  The serialized node.
 * @returns {HTMLElement}                        The constructed element subtree.
 */
export function buildElement(node) {
  const el =
    node.type === "Icon"
      ? createIconSvg()
      : document.createElement(tagForType(node.type));
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
 *
 * An unset prop is applied as `null`, which every prop applier reads as "clear
 * whatever a previous value put on the element". Handling the two cases
 * separately is what let `unset_props` cover only `style`/`content`/`label`
 * while `src`, `value`, `attrs` and the a11y attributes stayed behind.
 *
 * @param {HTMLElement} root  The root element.
 * @param {{path:number[], set_props?:Object, unset_props?:string[]}} patch  The patch.
 * @returns {void}
 */
function applyUpdate(root, patch) {
  const el = resolvePath(root, patch.path);
  if (patch.set_props) {
    applyProps(el, patch.set_props);
  }
  const unset = patch.unset_props ?? [];
  if (unset.length > 0) {
    applyProps(el, Object.fromEntries(unset.map((name) => [name, null])));
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
 * A patch that cannot be applied means the tree here no longer matches the one
 * the patch was computed against, and every later patch is index-relative to
 * that tree — so the batch **stops** at the failure and `onError` is called.
 * Carrying on would keep mutating a tree that is already wrong. Without an
 * `onError` the error is rethrown, which is the old behaviour.
 *
 * @param {HTMLElement} root                       The mounted root element.
 * @param {import("./transport.js").Patch[]} patches  The tick's patch batch.
 * @param {(error: Error, patch: import("./transport.js").Patch) => void} [onError]
 *        Called with the first patch that failed; the rest of the batch is
 *        skipped. Omit to have the error propagate.
 * @returns {void}
 */
export function applyPatches(root, patches, onError) {
  for (const patch of patches) {
    try {
      applyPatch(root, patch);
    } catch (error) {
      if (!onError) throw error;
      onError(/** @type {Error} */ (error), patch);
      return;
    }
  }
}
