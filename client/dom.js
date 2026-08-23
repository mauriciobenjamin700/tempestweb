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

/** Tags the browser treats as form controls, which need a `name` or an `id`. */
const FORM_CONTROL_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

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
  // An IconButton is a button: the core declares `on_click` on it, so rendering
  // it as a div left it unreachable by keyboard and unnamed to a screen reader,
  // while a mouse click still worked — the failure mode nobody notices. Its glyph
  // is a renderer-owned <svg> (see applyIconButtonProps); IconButton is an IR
  // leaf, so no patch path descends into it.
  IconButton: "button",
  Input: "input",
  // A TextArea is a multi-line field. It rendered as an anonymous <div>: the base
  // sheet styles by [data-tw-type], so it *looked* like a field at the right size
  // and had nothing to focus and no input event to fire. `FORM_CONTROL_TAGS` and
  // `payloadFor` were already ready for the <textarea> that was never created.
  TextArea: "textarea",
  // A MaskedInput is an <input> the renderer formats as the reader types; the
  // mask travels as a data attribute so events.js can apply it. Rendering it as a
  // div left CPF, phone and CEP as dead rectangles in every mode.
  MaskedInput: "input",
  // A PinInput is a one-time-code field: a single <input> with the browser's own
  // autofill hint and a length cap, spaced out by the base sheet so it reads as a
  // code box. It rendered as an anonymous div before — declared, and invisible.
  PinInput: "input",
  // A Checkbox renders as a <label> wrapping a real <input type=checkbox> plus
  // its caption text, so the box and its label show side by side and the input
  // gets its accessible name natively. The <label> is the keyed, path-addressed
  // element; the input it wraps is renderer-internal (Checkbox is an IR leaf, so
  // no patch path ever descends into it).
  Checkbox: "label",
  // A Switch is the same shape as a Checkbox — a <label> wrapping a real
  // <input type="checkbox"> the reader can click, tab to and toggle with Space —
  // with role="switch" on the input, which is how a native checkbox spells "this
  // is on/off, not tick-the-box". As an anonymous div it was a settings row with
  // nothing to switch: `checked` had no element to sit on and no change to fire.
  Switch: "label",
  // A Slider is an <input type="range">: the core's `min_value`/`max_value`/`step`
  // ARE the native attributes, so the browser owns the drag, the arrow keys and
  // the a11y for free. The div it used to be had no thumb to grab.
  Slider: "input",
  // A RangeSlider has two thumbs, which one native range input cannot express, so
  // it stays a <div> holding two renderer-owned range inputs. Legal because
  // RangeSlider is an IR leaf: no patch path descends into it.
  RangeSlider: "div",
  // A Dropdown is a <select>, its `options` renderer-owned <option>s and its
  // `placeholder` a disabled leading one. Also an IR leaf.
  Dropdown: "select",
  // An Autocomplete is a <label> wrapping a text input plus a renderer-owned
  // <datalist> of its `options`: `list=` has to point at a datalist *element*, so
  // the input is wrapped rather than bare, and the browser draws the suggestions.
  Autocomplete: "label",
  // The pickers are the platform's own: <input type=date|time|file> inside the
  // keyed <label> that carries their caption. A hand-drawn calendar would be worse
  // than the one every browser already ships — and these drew nothing at all.
  DatePicker: "label",
  TimePicker: "label",
  FilePicker: "label",
  // A TabBar is the strip a TabView cannot draw for itself: it holds no IR child,
  // so its tabs are renderer-owned <button role="tab">s inside a role="tablist".
  // It is what makes a tabbed screen switchable — the TabView beside it is only
  // the panel (see applyPanelProps).
  TabBar: "div",
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
  // Overlay-layer widgets. They are boxes too; what makes them float is the
  // base sheet (positioning + backdrop) plus the roles applyOverlayProps sets.
  Dialog: "div",
  BottomSheet: "div",
  Toast: "div",
  Menu: "div",
  ActionSheet: "div",
  Popover: "div",
  Tooltip: "div",
});

/**
 * Widget types whose interaction is a native form control.
 *
 * The tag table cannot answer this on its own: a Checkbox, a Switch, an
 * Autocomplete and the three pickers render as a <label> *wrapping* the control,
 * and a RangeSlider as a div holding two range inputs — every one of them fires
 * `input`/`change`, none of them IS an input. Mode C's builder generator reads
 * this set to decide whether an `on_change` binds to `input`/`change` or falls
 * back to `click`; deriving it from tag names plus a hand-added exception is
 * exactly what mapped `MaskedInput`'s `on_change` onto `click` (#142), so the set
 * is declared once, here, next to the tags it qualifies.
 */
export const NATIVE_CONTROL_TYPES = new Set([
  // NOTE: keep CHANGE_REPORTING_TYPES below in sync when adding to this set.
  "Input",
  "TextArea",
  "MaskedInput",
  "PinInput",
  "Checkbox",
  "Switch",
  "Slider",
  "RangeSlider",
  "Dropdown",
  "Autocomplete",
  "DatePicker",
  "TimePicker",
  "FilePicker",
]);

/**
 * Widget types whose `on_change` arrives as an `input`/`change` wire event.
 *
 * A superset of the native controls: a `TabBar` is a div holding buttons, so
 * nothing about its markup says "change", yet a tab click is reported as one —
 * that is the event its handler is declared against. Mode C's builder generator
 * reads this to key the handler map; a widget missing from it binds `on_change`
 * to `click` and never fires.
 */
export const CHANGE_REPORTING_TYPES = new Set([...NATIVE_CONTROL_TYPES, "TabBar"]);

/** The native input `type` each picker widget renders. */
const PICKER_INPUT_TYPES = Object.freeze({
  DatePicker: "date",
  TimePicker: "time",
  FilePicker: "file",
});

/** Widget types drawn as a keyed wrapper holding the control plus a caption. */
const CAPTION_WRAPPER_TYPES = new Set([
  "Checkbox",
  "Switch",
  "DatePicker",
  "TimePicker",
  "FilePicker",
]);

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
  nameFormControl(el, key);
  applyProps(el, props ?? {});
}

/**
 * Give a native form control a `name`, taken from its widget key.
 *
 * A control with neither `name` nor `id` is an accessibility and autofill dead
 * end: the browser cannot label it, cannot offer a saved value for it, and
 * DevTools reports it as an issue on every page that renders an input. The
 * widget key is already the stable identity the reconciler addresses the node
 * by, so it is the honest name — and it stays out of the wire, because the
 * renderer derives it rather than the app declaring it twice.
 *
 * Inert for submission: tempestweb never submits an HTML form (state lives in
 * Python), so the attribute only feeds the accessibility tree and autofill.
 *
 * @param {HTMLElement} el   The freshly shaped element.
 * @param {?string} key      The widget key, or null.
 * @returns {void}
 */
function nameFormControl(el, key) {
  if (key == null || !FORM_CONTROL_TAGS.has(el.tagName)) {
    return;
  }
  if (!el.hasAttribute("name")) {
    el.setAttribute("name", key);
  }
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
 * overwriting textContent, which would drop the nested input. A `label` is drawn
 * only for the widget types it actually names (see LABEL_AS_TEXT_TYPES). An Icon is an inline
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
    if (type != null && CAPTION_WRAPPER_TYPES.has(type)) {
      setWrapperCaption(el, props.label == null ? "" : String(props.label));
    } else if (type != null && LABEL_AS_TEXT_TYPES.has(type)) {
      el.textContent = props.label == null ? "" : String(props.label);
    }
  }
  if (type === "Icon" && ("name" in props || "size" in props)) {
    renderIcon(/** @type {any} */ (el), props);
  }
  // The app's own semantics are applied FIRST, then each widget's defaults fill
  // what is still missing. The other order looks equivalent and is not: a widget
  // with no semantics sends `semantics: null`, which clears role/aria-label — so
  // running it last stripped the role every widget had just set, leaving a
  // ProgressBar with aria-valuemin and no role at all, and a Toast that
  // announced nothing.
  applyA11yProps(el, props);
  applyIconButtonProps(el, type, props);
  applyIndicatorProps(el, type, props);
  applyControlProps(el, type, props);
  applyDragProps(el, type, props);
  applyOverlayProps(el, type, props);
  applyEscapeHatchAttrs(el, props);
  applyLazyProps(el, type, props);
  applyListEventProps(el, type, props);
  applySortAndPageProps(el, type, props);
  applyCameraProps(el, type, props);
}

/**
 * Draw an `IconButton`: its glyph, its accessible name, and the button type.
 *
 * The `icon` prop names a curated glyph the `Icon` widget already knows how to
 * draw, but `renderIcon` only ever ran for an `Icon` node — so an IconButton
 * showed its `label` as text (a `Burger` read "menu" instead of ☰) and, in the
 * SSR renderer, nothing at all. The glyph is a renderer-owned `<svg>`, which is
 * legal because IconButton is an IR leaf: no patch path descends into it.
 *
 * `label` becomes the accessible name rather than visible text — that is what a
 * label means on an icon-only control. This runs *after* {@link applyA11yProps}
 * on purpose: a widget with no semantics sends `semantics: null`, which clears
 * `aria-label`, so naming the button before that pass left it nameless again
 * (measured in Chrome: `aria-label` was null on a `Burger`). Running after also
 * makes the app's own `semantics.label` win, because it is already on the
 * element and this only fills a gap.
 *
 * @param {Element} el     The button element.
 * @param {?string} type   The node's IR type.
 * @param {Object} props   The node's props (may be a partial Update).
 * @returns {void}
 */
function applyIconButtonProps(el, type, props) {
  if (type !== "IconButton") {
    return;
  }
  if (!el.hasAttribute("type")) {
    el.setAttribute("type", "button");
  }
  if ("icon" in props) {
    let svg = el.querySelector(`[${ITEM_ATTR}="glyph"]`);
    if (svg == null) {
      svg = createIconSvg();
      svg.setAttribute(ITEM_ATTR, "glyph");
      el.appendChild(svg);
    }
    renderIcon(/** @type {any} */ (svg), {
      name: props.icon == null ? "" : String(props.icon),
    });
  }
  const named = el.getAttribute("aria-label");
  if (
    (named == null || named === "") &&
    props.label != null &&
    String(props.label) !== ""
  ) {
    el.setAttribute("aria-label", String(props.label));
  }
}

/** Attribute holding a `Dialog`'s title, painted by the base sheet. */
export const TITLE_ATTR = "data-tw-title";
/** Attribute marking a renderer-owned menu item, read by the click listener. */
export const ITEM_ATTR = "data-tw-part";
/** Attribute holding the value a menu item selects. */
export const ITEM_VALUE_ATTR = "data-tw-value";
/** Attribute holding the widget key an overlay anchors itself to. */
export const ANCHOR_ATTR = "data-tw-anchor";

/**
 * Render a `Menu`/`ActionSheet`'s items as renderer-owned buttons.
 *
 * `items` is a prop — a list of `{label, value, icon}` dicts — and these widgets
 * are IR leaves, so no patch path ever descends into them and the renderer is
 * free to own their contents. Without this the widget rendered as an empty box:
 * the items existed on the wire and nothing drew them.
 *
 * The list is rebuilt whenever `items` arrives, which is what an Update carrying
 * a changed menu looks like. Each button carries its value for the click
 * listener, and `role=menuitem` so the menu reads as a menu.
 *
 * A `MenuItem` declares three things — `label`, `value` and `icon` — and the
 * icon used to be dropped, so a menu the app drew with icons came out as plain
 * text. It is resolved through the same registry the `Icon` widget uses and
 * inserted before the label, which lives in its own span so the click listener
 * can read the label back without the glyph's markup in the way.
 *
 * Once any item names an icon, every item gets the slot — an empty one where
 * there is no icon. Otherwise the labels of the icon-less items start a glyph's
 * width to the left of the others, which reads as a broken menu rather than as a
 * menu with some icons.
 *
 * @param {HTMLElement} el     The Menu/ActionSheet element.
 * @param {*} items            The `items` prop (anything else is treated empty).
 * @returns {void}
 */
function renderMenuItems(el, items) {
  const list = Array.isArray(items) ? items : [];
  for (const existing of Array.from(el.querySelectorAll(`[${ITEM_ATTR}="item"]`))) {
    existing.remove();
  }
  const anyIcon = list.some((item) => item?.icon != null && String(item.icon) !== "");
  for (const item of list) {
    const button = document.createElement("button");
    button.setAttribute("type", "button");
    button.setAttribute(ITEM_ATTR, "item");
    button.setAttribute("role", "menuitem");
    button.setAttribute(ITEM_VALUE_ATTR, item?.value == null ? "" : String(item.value));
    if (anyIcon) {
      const svg = createIconSvg();
      renderIcon(svg, { name: item?.icon == null ? "" : String(item.icon) });
      button.appendChild(svg);
    }
    const label = document.createElement("span");
    label.setAttribute(ITEM_ATTR, "item-label");
    label.textContent = item?.label == null ? "" : String(item.label);
    button.appendChild(label);
    el.appendChild(button);
  }
}

/**
 * Position every anchored overlay next to the widget it names.
 *
 * A `Menu`/`Popover` carries the `key` of its anchor, which the renderer can
 * only honour once layout exists — so this runs in the same post-layout pass
 * that repaints canvases. The overlay is placed under the anchor, left-aligned,
 * then clamped into the viewport so a menu opened near an edge stays reachable.
 * An overlay whose anchor is absent keeps the sheet's default placement.
 *
 * @param {HTMLElement} root  The mount root to search under.
 * @returns {void}
 */
export function positionAnchoredOverlays(root) {
  const anchored = root.querySelectorAll(`[${ANCHOR_ATTR}]`);
  for (const node of anchored) {
    const el = /** @type {HTMLElement} */ (node);
    const key = el.getAttribute(ANCHOR_ATTR);
    if (!key) continue;
    const anchor = root.querySelector(`[${KEY_ATTR}="${CSS.escape(key)}"]`);
    if (anchor == null) continue;
    const box = anchor.getBoundingClientRect();
    const own = el.getBoundingClientRect();
    const margin = 8;
    // A harness without layout (jsdom) reports no viewport; skip the clamp there
    // rather than pinning everything to the top-left corner.
    const viewW = globalThis.innerWidth || 0;
    const viewH = globalThis.innerHeight || 0;
    const left = Math.max(margin, box.left);
    const top = box.bottom + 4;
    const maxLeft = viewW > 0 ? Math.max(margin, viewW - own.width - margin) : left;
    const maxTop = viewH > 0 ? Math.max(margin, viewH - own.height - margin) : top;
    el.style.position = "fixed";
    el.style.left = `${Math.min(left, maxLeft)}px`;
    el.style.top = `${Math.min(top, maxTop)}px`;
    el.style.transform = "none";
  }
}

/**
 * Apply the overlay-layer widgets' text and accessibility semantics.
 *
 * A scene's overlays are patched into a separate host (see `mount`), which the
 * base sheet positions; these are the per-widget bits the sheet cannot do.
 *
 * A `Dialog`'s title is *not* one of its children — it is a prop — so it cannot
 * be inserted as an element without shifting the indices every child patch is
 * relative to. It goes onto {@link TITLE_ATTR}, which the sheet paints via
 * `::before`, and onto `aria-label`, so a screen reader announces the dialog by
 * its title rather than reading a decorative pseudo-element. A `Toast` carries
 * no children at all, so its message is plain text content, and it announces
 * itself politely — a toast that appeared silently would be invisible to a
 * screen reader.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyOverlayProps(el, type, props) {
  if (type === "Dialog") {
    if (!el.hasAttribute("role")) {
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-modal", "true");
    }
    if ("title" in props) {
      const title = props.title;
      setOrRemove(el, TITLE_ATTR, title === "" ? null : title);
      // An explicit semantics.label is the app naming the dialog on purpose; the
      // title only supplies a name when the app did not.
      const sem = props.semantics;
      const named = sem != null && typeof sem === "object" && sem.label != null;
      if (!named) {
        setOrRemove(el, "aria-label", title === "" ? null : title);
      }
    }
  } else if (type === "BottomSheet") {
    if (!el.hasAttribute("role")) {
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-modal", "true");
    }
  } else if (type === "Toast") {
    if (!el.hasAttribute("role")) {
      el.setAttribute("role", "status");
      el.setAttribute("aria-live", "polite");
    }
    if ("message" in props) {
      el.textContent = props.message == null ? "" : String(props.message);
    }
  } else if (type === "Menu" || type === "ActionSheet") {
    if (!el.hasAttribute("role")) {
      el.setAttribute("role", "menu");
    }
    if (type === "ActionSheet" && "title" in props) {
      const title = props.title;
      setOrRemove(el, TITLE_ATTR, title === "" ? null : title);
      const sem = props.semantics;
      const named = sem != null && typeof sem === "object" && sem.label != null;
      if (!named) {
        setOrRemove(el, "aria-label", title === "" ? null : title);
      }
    }
    if ("items" in props) {
      renderMenuItems(el, props.items);
    }
    if ("anchor" in props) {
      setOrRemove(el, ANCHOR_ATTR, props.anchor);
    }
  } else if (type === "Popover") {
    if (!el.hasAttribute("role")) {
      el.setAttribute("role", "dialog");
    }
    if ("anchor" in props) {
      setOrRemove(el, ANCHOR_ATTR, props.anchor);
    }
  } else if (type === "Tooltip") {
    // The native `title` attribute, deliberately: it shows on hover and keyboard
    // focus, and assistive tech already reads it. A custom bubble would need an
    // id to point aria-describedby at, and would fight the browser's own.
    if ("message" in props) {
      setOrRemove(el, "title", props.message === "" ? null : props.message);
    }
  }
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

/** Attribute marking a camera widget: `preview` or `scanner`. */
export const CAMERA_ATTR = "data-tw-camera";

/** Attribute holding a `PinInput`'s expected code length. */
export const PIN_LENGTH_ATTR = "data-tw-length";

/** Attribute holding a `MaskedInput`'s mask, which events.js applies as you type. */
export const MASK_ATTR = "data-tw-mask";

/** Attribute holding a `FormField`'s field name, reported with its validation. */
export const FIELD_ATTR = "data-tw-field";

/** Attribute holding a `FormField`'s current error message, painted by the sheet. */
export const FIELD_ERROR_ATTR = "data-tw-error";

/** Attribute holding a `TabView`'s active tab index. */
export const ACTIVE_ATTR = "data-tw-active";

/** Attribute marking a `RouteDrawer` whose drawer is open. */
export const OPEN_ATTR = "data-tw-open";

/** Attribute marking a `ReorderableList`, whose children can be dragged to sort. */
export const REORDER_ATTR = "data-tw-reorder";

/** Attribute holding a `PageView`'s current page index. */
export const PAGE_ATTR = "data-tw-page";

/** Attribute holding a `PageView`'s page count. */
export const PAGE_COUNT_ATTR = "data-tw-pages";

/**
 * Apply a `PinInput`'s props onto its `<input>`.
 *
 * The widget declares `length`, `value`, `secure` and `on_complete`, and used to
 * render as an empty div: nothing to type into, so `on_change` and `on_complete`
 * were both unreachable. It becomes a single one-time-code field rather than
 * `length` separate boxes, because that is what the platform rewards — the
 * browser (and iOS/Android) offer to fill `autocomplete="one-time-code"` from an
 * SMS, `inputmode="numeric"` brings up the digit keypad, and a paste of the whole
 * code just works. The base sheet spaces the characters so it still reads as a
 * code box. `data-tw-length` is what the client compares against to know the code
 * is complete.
 *
 * `secure` is applied only when the patch mentions it, for the same reason as an
 * Input: typing patches `value` alone, and re-deriving the type from every props
 * bag would unmask the code on the first keystroke.
 *
 * @param {HTMLElement} el  The PinInput element.
 * @param {Object} props    The props to apply.
 * @returns {void}
 */
function applyPinProps(el, props) {
  if ("secure" in props) {
    el.setAttribute("type", props.secure ? "password" : "text");
  } else if (!el.hasAttribute("type")) {
    el.setAttribute("type", "text");
  }
  if (!el.hasAttribute("inputmode")) {
    el.setAttribute("inputmode", "numeric");
    el.setAttribute("autocomplete", "one-time-code");
  }
  if ("length" in props && props.length != null) {
    const length = Math.max(1, Math.trunc(Number(props.length)));
    el.setAttribute("maxlength", String(length));
    el.setAttribute(PIN_LENGTH_ATTR, String(length));
  }
  if ("value" in props) {
    el.value = props.value == null ? "" : String(props.value);
  }
}

/**
 * Apply the contract of the two container widgets whose gesture the DOM lacks.
 *
 * A `ReorderableList` is marked so `events.js` can read a drag between its
 * children as a reorder, and a `PageView` becomes a snapping horizontal
 * carousel whose current page is both an attribute (so a scroll can tell whether
 * the page actually changed) and a scroll position (so the app moving `page`
 * moves the carousel).
 *
 * Their children are *not* marked here: children arrive and leave through
 * Insert/Remove patches on the container, which never pass through this
 * function, so anything written onto a child would go stale. The base sheet
 * styles them by selector, and {@link syncContainerGestures} reconciles what
 * depends on them after each batch.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
/**
 * Mark a camera widget so `client/camera.js` can open its stream.
 *
 * `CameraPreview` and `QrScanner` are IR leaves that rendered as empty boxes:
 * no stream, no preview, and their declared handlers (`on_frame`, `on_scan`)
 * unreachable. The marker carries which of the two it is, plus the preview's own
 * two props — which camera to ask for, and how often to sample — because the
 * module that opens the stream reads them off the element rather than being told
 * twice.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyCameraProps(el, type, props) {
  if (type === "CameraPreview") {
    el.setAttribute(CAMERA_ATTR, "preview");
    if ("facing" in props && props.facing != null) {
      el.setAttribute("data-tw-facing", String(props.facing));
    }
    if ("frame_interval_ms" in props && props.frame_interval_ms != null) {
      el.setAttribute("data-tw-frame-interval", String(props.frame_interval_ms));
    }
    return;
  }
  if (type === "QrScanner") {
    el.setAttribute(CAMERA_ATTR, "scanner");
  }
}

function applySortAndPageProps(el, type, props) {
  if (type === "FormField") {
    // The name is what `ValidationEvent.field` carries, and the app looks its
    // validators up by it; without it on the element the client has nothing to
    // report and `on_validate` can never fire.
    if ("name" in props) {
      setOrRemove(el, FIELD_ATTR, props.name);
    }
    // `error` is a prop, not a child, so it cannot become an element without
    // shifting the index the field's own child is addressed by. It goes onto an
    // attribute the base sheet paints through `::after` — the same trick a
    // Dialog's title uses — plus `aria-invalid`, so the message is announced and
    // not merely drawn.
    if ("error" in props) {
      const error = props.error;
      const has = error != null && String(error) !== "";
      setOrRemove(el, FIELD_ERROR_ATTR, has ? error : null);
      setOrRemove(el, "aria-invalid", has ? "true" : null);
    }
    return;
  }
  if (type === "ReorderableList") {
    el.setAttribute(REORDER_ATTR, "");
    return;
  }
  if (type !== "PageView") {
    return;
  }
  if (!("page" in props)) {
    return;
  }
  const page = Number(props.page);
  const current = Number.isFinite(page) && page >= 0 ? Math.trunc(page) : 0;
  el.setAttribute(PAGE_ATTR, String(current));
  // The app owning `page` means the app can also *move* it, so honour it: a page
  // set from state scrolls the carousel there. Guarded by a width, because a
  // viewport with no layout yet (first mount, jsdom) would scroll to 0 and land
  // the reader on the wrong page.
  const width = el.clientWidth;
  if (width > 0) {
    const target = current * width;
    if (Math.abs(el.scrollLeft - target) > 1) {
      el.scrollLeft = target;
    }
  }
}

/**
 * Reconcile the two container gestures with the children a batch left behind.
 *
 * Both facts here are about *children*, and a child is inserted or removed by a
 * patch on its **parent** — which never passes through the parent's own
 * `applyProps`. So this runs in the post-layout pass instead: it marks a
 * `ReorderableList`'s rows draggable, and records how many pages a `PageView`
 * currently holds. Idempotent, and cheap enough to run per batch (one query per
 * marked container).
 *
 * @param {HTMLElement} root  The mount root.
 * @returns {void}
 */
export function syncContainerGestures(root) {
  for (const list of root.querySelectorAll(`[${REORDER_ATTR}]`)) {
    for (const child of list.children) {
      const item = /** @type {HTMLElement} */ (child);
      if (item.getAttribute("draggable") !== "true") {
        item.setAttribute("draggable", "true");
      }
      if (!item.style.cursor) {
        item.style.cursor = "grab";
      }
    }
  }
  for (const node of root.querySelectorAll(`[${PAGE_ATTR}]`)) {
    const view = /** @type {HTMLElement} */ (node);
    view.setAttribute(PAGE_COUNT_ATTR, String(view.childElementCount));
  }
}

/**
 * Widget types whose `label` prop *is* their text content.
 *
 * Not every widget with a label wants it drawn: a `FormField` is a container
 * whose label is metadata (the core renders its own `Text` child for it, and the
 * SSR renderer ignores the prop). Writing it as text content painted an
 * unstyled, duplicate label — Times New Roman next to the themed one — and an
 * Update carrying `label` would have wiped the field's children along with it,
 * since textContent replaces everything.
 *
 * A wrapper type (see `CAPTION_WRAPPER_TYPES`) is not here for the same reason
 * squared: its `label` is a caption *beside* a nested control, so writing it as
 * textContent would delete the control the reader interacts with.
 */
const LABEL_AS_TEXT_TYPES = new Set(["Button"]);

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
  if (type === "LazyGrid" && "columns" in props) {
    // `columns` was declared and never read: a three-column gallery rendered one
    // item per row. The spacers virtualize.js reserves are ::before/::after, so
    // they take a grid cell — `grid-column: 1 / -1` in the base sheet keeps them
    // spanning the row, and the reserved extent stays proportional.
    const columns = Math.max(1, Math.trunc(Number(props.columns) || 1));
    el.style.display = "grid";
    el.style.gridTemplateColumns = `repeat(${columns}, minmax(0, 1fr))`;
    el.setAttribute("data-tw-columns", String(columns));
  }
  const start = Array.isArray(props.window) ? props.window[0] : 0;
  el.setAttribute("data-tw-window-start", String(start ?? 0));
}

// List widgets that declare `end_reached_threshold` + `on_end_reached`. The
// windowed ones scroll their own box; a SectionList flows in the page — both
// geometries are measured by client/lists.js off the same marker.
const END_REACHED_TYPES = Object.freeze([
  "LazyColumn",
  "LazyRow",
  "LazyGrid",
  "SectionList",
]);

// Widgets that declare `on_refresh`, and the axis their pull runs along: a
// LazyRow scrolls sideways, so its pull-to-refresh is a drag to the right.
const REFRESH_AXIS = Object.freeze({
  LazyColumn: "y",
  LazyRow: "x",
  RefreshControl: "y",
});

/**
 * Get (or lazily create) the spinner inside a RefreshControl.
 *
 * A RefreshControl is an IR leaf that carries only the refresh contract — the
 * core says the content "is supplied by the renderer" — so no patch path
 * descends into it and this element is safe to own, exactly like a ProgressBar's
 * fill. It is the only thing the widget can show: the pull affordance while the
 * gesture is armed, and the running indicator while `refreshing` is set.
 *
 * @param {HTMLElement} el  The RefreshControl element.
 * @returns {HTMLElement}   The spinner element.
 */
function ensureRefreshSpinner(el) {
  let spinner = /** @type {HTMLElement|null} */ (el.querySelector("[data-tw-part=\"spinner\"]"));
  if (spinner == null) {
    spinner = document.createElement("div");
    spinner.setAttribute("data-tw-part", "spinner");
    el.appendChild(spinner);
  }
  return spinner;
}

/**
 * Mark the list-event contract a widget declares: end-reached and refresh.
 *
 * Both markers exist because the handlers themselves never cross the wire (they
 * serialize to `null`), so the element has to carry what the widget *declares*:
 * the scroll fraction it wants `end_reached` at (a core prop, default `0.8`) and
 * the axis its pull-to-refresh runs along. `client/lists.js` reads both. The
 * app's `refreshing` flag is mirrored too — it both drives the running indicator
 * (base theme) and suppresses a second pull while the reload is in flight — and
 * is announced with `aria-busy` so a screen reader hears the wait.
 *
 * @param {HTMLElement} el     The target element.
 * @param {?string} type       The widget type.
 * @param {Object} props       The props to apply.
 * @returns {void}
 */
function applyListEventProps(el, type, props) {
  if (type == null) {
    return;
  }
  if (
    END_REACHED_TYPES.includes(type) &&
    "end_reached_threshold" in props &&
    props.end_reached_threshold != null
  ) {
    el.setAttribute("data-tw-end-threshold", String(props.end_reached_threshold));
  }
  const axis = REFRESH_AXIS[type];
  if (axis === undefined) {
    return;
  }
  el.setAttribute("data-tw-refresh", axis);
  if (type === "RefreshControl") {
    ensureRefreshSpinner(el);
  }
  if ("refreshing" in props) {
    if (props.refreshing) {
      el.setAttribute("data-tw-refreshing", "true");
      el.setAttribute("aria-busy", "true");
    } else {
      el.removeAttribute("data-tw-refreshing");
      el.removeAttribute("aria-busy");
    }
  }
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
 * Get (or lazily create) the real form control nested inside a keyed wrapper.
 *
 * A Checkbox, Switch, Autocomplete or picker is drawn as a `<label>`: the label
 * is the keyed, path-addressed element, and this nested control carries the state
 * the reader changes and fires the native `input`/`change` that bubbles up to the
 * label for delegation. Wrapping in a `<label>` also gives the control its
 * accessible name from the caption natively — no `aria-label` to keep in sync.
 *
 * Legal because every widget drawn this way is an IR leaf: no patch path ever
 * descends into what the renderer puts inside it.
 *
 * @param {HTMLElement} el         The keyed wrapper element.
 * @param {string} inputType       The `type` attribute for the nested input.
 * @returns {HTMLInputElement}     The nested input.
 */
function ensureNestedInput(el, inputType) {
  let input = /** @type {HTMLInputElement|null} */ (el.querySelector("input"));
  if (input == null) {
    input = /** @type {HTMLInputElement} */ (document.createElement("input"));
    input.setAttribute("type", inputType);
    nameFormControl(input, el.getAttribute(KEY_ATTR));
    el.insertBefore(input, el.firstChild);
  }
  return input;
}

/**
 * Set a wrapper's visible caption, as a single trailing text node.
 *
 * Only text nodes are replaced: the nested control (and an Autocomplete's
 * `<datalist>`) are elements and survive, which is the whole reason this is not
 * a `textContent` assignment. An empty caption clears it.
 *
 * @param {HTMLElement} el    The keyed wrapper element.
 * @param {string} text       The caption text (``""`` clears it).
 * @returns {void}
 */
function setWrapperCaption(el, text) {
  for (const node of Array.from(el.childNodes)) {
    if (node.nodeType === 3) {
      el.removeChild(node);
    }
  }
  if (text) {
    el.appendChild(document.createTextNode(text));
  }
}

/**
 * Get (or lazily create) one of a RangeSlider's two renderer-owned thumbs.
 *
 * Each thumb is a native range input tagged with the end it drives, and named
 * `<key>-low` / `<key>-high` so a form submits both. The low thumb is inserted
 * first, so the DOM order matches the pair the wire payload reports.
 *
 * @param {HTMLElement} el   The RangeSlider element.
 * @param {string} part      Which end: `"low"` or `"high"`.
 * @returns {HTMLInputElement}  The thumb input.
 */
function ensureRangeThumb(el, part) {
  let thumb = /** @type {HTMLInputElement|null} */ (
    el.querySelector(`input[${ITEM_ATTR}="${part}"]`)
  );
  if (thumb == null) {
    thumb = /** @type {HTMLInputElement} */ (document.createElement("input"));
    thumb.setAttribute("type", "range");
    thumb.setAttribute(ITEM_ATTR, part);
    const key = el.getAttribute(KEY_ATTR);
    nameFormControl(thumb, key == null ? null : `${key}-${part}`);
    el.appendChild(thumb);
  }
  return thumb;
}

/**
 * Get (or lazily create) the `<datalist>` an Autocomplete's input reads from.
 *
 * The id is derived from the widget key, which is what the app addresses the
 * widget by; a keyless Autocomplete gets a sequence number instead, so two of
 * them on one screen never share a suggestion list.
 *
 * @param {HTMLElement} el              The Autocomplete `<label>`.
 * @param {HTMLInputElement} input      Its nested text input.
 * @returns {HTMLElement}               The datalist element.
 */
function ensureDataList(el, input) {
  let list = el.querySelector("datalist");
  if (list == null) {
    list = document.createElement("datalist");
    const key = el.getAttribute(KEY_ATTR);
    _datalistSeq += 1;
    list.setAttribute("id", `tw-list-${key ?? _datalistSeq}`);
    el.appendChild(list);
  }
  input.setAttribute("list", list.getAttribute("id") ?? "");
  return list;
}

/** Sequence for the datalist id of a keyless Autocomplete. */
let _datalistSeq = 0;

/**
 * Rewrite a `<select>`'s or `<datalist>`'s options from an `options` list.
 *
 * The placeholder is a disabled leading option, tagged so `events.js` can tell a
 * real choice from "nothing chosen yet" when it reports the selected index. A
 * `<datalist>` takes no placeholder — it is a suggestion list, not a value.
 *
 * @param {HTMLElement} host        The `<select>` or `<datalist>`.
 * @param {Array<*>} options        The option values, in order.
 * @param {?string} placeholder     Leading disabled option, or null for none.
 * @returns {void}
 */
function renderOptions(host, options, placeholder) {
  host.textContent = "";
  if (placeholder) {
    const empty = document.createElement("option");
    empty.setAttribute("value", "");
    empty.setAttribute("disabled", "");
    empty.setAttribute(ITEM_ATTR, "placeholder");
    empty.textContent = placeholder;
    host.appendChild(empty);
  }
  for (const option of options) {
    const item = document.createElement("option");
    const value = option == null ? "" : String(option);
    item.setAttribute("value", value);
    item.textContent = value;
    host.appendChild(item);
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
 * **Buffer vs. display size.** A canvas has two sizes: the pixel buffer
 * (`width`/`height`) and the box CSS gives it. Painting only the buffer at the
 * widget's declared size left the browser to stretch that bitmap over whatever
 * box the layout produced — a 320×200 chart blown up to 909×568 inside a card,
 * every label soft and oversized. And on a HiDPI screen the same bitmap was
 * stretched again by the device pixel ratio. So the buffer is sized to the box
 * actually on screen (times the DPR) while the context is scaled to keep the
 * app's declared coordinate system, which is what its draw commands are written
 * in. Before layout — first paint, or a jsdom harness with no layout at all —
 * the box is unknown (`clientWidth` is 0) and the declared size is used as-is.
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
  const declaredW = el._twCanvasW;
  const declaredH = el._twCanvasH;
  if (declaredW == null || declaredH == null) {
    return;
  }
  // Defaults only, and only when the app's Style did not size the canvas: a
  // canvas declares 320x200 but a flex parent's `align-items: stretch` (the CSS
  // default) pulls it to the container's width, and the intrinsic aspect ratio
  // drags the height along — a chart drawn for 320x200 was being blown up to
  // 909x568, so every label came out 2.8x too large. Pinning the box to the
  // declared size keeps the drawing at the scale the app designed it for; an
  // app that wants a bigger canvas sets the size on the widget's Style, and the
  // scaling below then maps its commands onto that box.
  if (!el.style.width) {
    el.style.width = `${declaredW}px`;
  }
  if (!el.style.height) {
    el.style.height = `${declaredH}px`;
  }
  const dpr = globalThis.devicePixelRatio || 1;
  const displayW = el.clientWidth || declaredW;
  const displayH = el.clientHeight || declaredH;
  el.width = Math.round(displayW * dpr);
  el.height = Math.round(displayH * dpr);
  const ctx = typeof el.getContext === "function" ? el.getContext("2d") : null;
  if (ctx == null) {
    return;
  }
  if (typeof ctx.setTransform === "function") {
    ctx.setTransform((displayW * dpr) / declaredW, 0, 0, (displayH * dpr) / declaredH, 0, 0);
  }
  ctx.clearRect(0, 0, declaredW, declaredH);
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
/**
 * Input types and autofill hints for each `KeyboardType` the core declares.
 *
 * `NUMBER` maps to `inputmode` rather than `type="number"`: a number input adds
 * spinners and drops a partially typed value, which fights a controlled field.
 * `PASSWORD` gets no `autocomplete` — only the app knows whether the field is a
 * login or a new password, and guessing `current-password` on a signup form
 * makes the browser offer the wrong saved secret.
 */
const KEYBOARD_HINTS = Object.freeze({
  email: { type: "email", autocomplete: "email" },
  phone: { type: "tel", autocomplete: "tel" },
  url: { type: "url", autocomplete: "url" },
  number: { inputmode: "numeric" },
  password: { type: "password" },
});

/**
 * Decide an Input's `type`, input mode and autofill hint from what it declared.
 *
 * The widget declared the keyboard and the renderer dropped it: an
 * `Input(keyboard=KeyboardType.EMAIL)` — what `EmailField` builds — rendered a
 * plain text box, so a phone showed the wrong keyboard, the browser offered no
 * saved address, and DevTools reported the field as missing an autocomplete
 * attribute.
 *
 * `secure` wins the type — a masked field stays masked whatever keyboard it
 * asks for, and an explicit ``secure: false`` unmasks even when the patch says
 * nothing about the keyboard — while a props bag with neither key leaves the
 * attribute alone: typing
 * patches `value` only, and re-deriving from an incomplete bag used to turn a
 * password field back into a visible one on the first keystroke. An
 * `autocomplete` the app set through `attrs` also wins, because only the app
 * knows the field's role in its form (a signup needs `new-password`, a login
 * `current-password`).
 *
 * @param {HTMLElement} el   The input element.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applyInputType(el, props) {
  const hint = "keyboard" in props ? KEYBOARD_HINTS[String(props.keyboard)] : null;
  if (hint?.inputmode != null) {
    el.setAttribute("inputmode", hint.inputmode);
  }
  if (hint?.autocomplete != null && !el.hasAttribute("autocomplete")) {
    el.setAttribute("autocomplete", hint.autocomplete);
  }
  if (props.secure === true) {
    el.setAttribute("type", "password");
  } else if (hint?.type != null) {
    el.setAttribute("type", hint.type);
  } else if ("secure" in props || !el.hasAttribute("type")) {
    el.setAttribute("type", "text");
  }
}

/**
 * Draw a `Switch`: the nested checkbox the reader flips, plus its state.
 *
 * `role="switch"` on a real checkbox is how HTML spells an on/off control: the
 * keyboard, the focus ring and the checked state stay native, and a screen reader
 * announces "switch, on" instead of "checkbox, checked".
 *
 * @param {HTMLElement} el   The Switch `<label>`.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applySwitchProps(el, props) {
  const input = ensureNestedInput(el, "checkbox");
  input.setAttribute("role", "switch");
  if ("checked" in props) {
    input.checked = Boolean(props.checked);
  }
}

/**
 * Draw a `Slider`: a native range input over the declared scale.
 *
 * The bounds are written before the value, because a range input clamps whatever
 * it is given to the range it currently has — assigning `value` first and the
 * bounds after left a slider parked at the wrong end (a 0..1 default clamping a
 * value of 70 down to 1).
 *
 * @param {HTMLElement} el   The Slider `<input>`.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applySliderProps(el, props) {
  el.setAttribute("type", "range");
  applyRangeBounds(el, props);
  if ("value" in props) {
    /** @type {HTMLInputElement} */ (el).value =
      props.value == null ? "" : String(props.value);
  }
}

/**
 * Write the shared `min`/`max`/`step` of a range input from the core's props.
 *
 * @param {HTMLElement} el   A range input (a Slider, or one RangeSlider thumb).
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applyRangeBounds(el, props) {
  if ("min_value" in props) {
    setOrRemove(el, "min", props.min_value);
  }
  if ("max_value" in props) {
    setOrRemove(el, "max", props.max_value);
  }
  if ("step" in props) {
    setOrRemove(el, "step", props.step);
  }
}

/**
 * Draw a `RangeSlider`: two native range inputs, one per end of the window.
 *
 * @param {HTMLElement} el   The RangeSlider `<div>`.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applyRangeSliderProps(el, props) {
  const low = ensureRangeThumb(el, "low");
  const high = ensureRangeThumb(el, "high");
  applyRangeBounds(low, props);
  applyRangeBounds(high, props);
  if ("low" in props) {
    low.value = props.low == null ? "" : String(props.low);
  }
  if ("high" in props) {
    high.value = props.high == null ? "" : String(props.high);
  }
}

/**
 * Draw a `Dropdown`: its options, its placeholder and the current choice.
 *
 * The options are re-rendered only when the widget says so, and the current
 * choice is restored across a re-render, so an Update that only changes the
 * option list does not silently clear what the reader had picked. The `options`
 * and `placeholder` last applied are kept on the element because an Update
 * carries one prop, not the whole bag.
 *
 * @param {HTMLElement} el   The Dropdown `<select>`.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applyDropdownProps(el, props) {
  const select = /** @type {HTMLSelectElement} */ (el);
  if ("options" in props) {
    select.__twOptions = Array.isArray(props.options) ? props.options : [];
  }
  if ("placeholder" in props) {
    select.__twPlaceholder = props.placeholder == null ? "" : String(props.placeholder);
  }
  if ("options" in props || "placeholder" in props) {
    const chosen = select.value;
    renderOptions(select, select.__twOptions ?? [], select.__twPlaceholder ?? null);
    if (!("value" in props)) {
      select.value = chosen;
    }
  }
  if ("value" in props) {
    select.value = props.value == null ? "" : String(props.value);
  }
}

/**
 * Draw an `Autocomplete`: a text input plus the datalist the browser suggests from.
 *
 * @param {HTMLElement} el   The Autocomplete `<label>`.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applyAutocompleteProps(el, props) {
  const input = ensureNestedInput(el, "text");
  const list = ensureDataList(el, input);
  if ("options" in props) {
    renderOptions(list, Array.isArray(props.options) ? props.options : [], null);
  }
  if ("value" in props) {
    input.value = props.value == null ? "" : String(props.value);
  }
  if ("placeholder" in props) {
    setOrRemove(input, "placeholder", props.placeholder);
  }
}

/**
 * Draw a `DatePicker`, `TimePicker` or `FilePicker`: the platform's own control.
 *
 * A file input's `value` cannot be assigned — the browser refuses, so that no
 * page can hand itself a path — so a FilePicker's `value` is reflected as an
 * attribute the base sheet prints beside the button. Date and time take theirs
 * directly, in the ISO spelling both the core and the native control use.
 *
 * @param {HTMLElement} el   The picker `<label>`.
 * @param {string} type      The widget type.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applyPickerProps(el, type, props) {
  const input = ensureNestedInput(el, PICKER_INPUT_TYPES[type]);
  if (!("value" in props)) {
    return;
  }
  const value = props.value == null ? "" : String(props.value);
  if (type === "FilePicker") {
    setOrRemove(el, ITEM_VALUE_ATTR, value === "" ? null : value);
  } else {
    input.value = value;
  }
}

/**
 * Draw a `TabBar`: one button per tab, inside a real tablist.
 *
 * The tabs are renderer-owned, which is legal because a TabBar holds no IR child
 * — and necessary, because the strip is the only part of a tabbed screen the
 * reader can actually operate. Each button carries its index, so a click reports
 * the `params["index"]` the core's `RouteChangeEvent` convention puts it under.
 *
 * The buttons are rebuilt only when the labels change; switching tabs just moves
 * `aria-selected`, so the strip does not flash on every keystroke elsewhere.
 *
 * @param {HTMLElement} el   The TabBar `<div>`.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applyTabBarProps(el, props) {
  if (!el.hasAttribute("role")) {
    el.setAttribute("role", "tablist");
  }
  if ("tabs" in props) {
    const tabs = Array.isArray(props.tabs) ? props.tabs : [];
    el.textContent = "";
    tabs.forEach((label, index) => {
      const tab = document.createElement("button");
      tab.setAttribute("type", "button");
      tab.setAttribute("role", "tab");
      tab.setAttribute(ITEM_ATTR, "tab");
      tab.setAttribute(ITEM_VALUE_ATTR, String(index));
      tab.textContent = label == null ? "" : String(label);
      el.appendChild(tab);
    });
  }
  if ("active" in props) {
    setOrRemove(el, ACTIVE_ATTR, props.active);
  }
  const active = Number(el.getAttribute(ACTIVE_ATTR) ?? 0);
  Array.from(el.children).forEach((tab, index) => {
    tab.setAttribute("aria-selected", String(index === active));
    tab.setAttribute("tabindex", index === active ? "0" : "-1");
  });
}

/**
 * Reflect a `TabView`'s active tab, and a `RouteDrawer`'s open state.
 *
 * Neither widget can be *driven* by this renderer: both hold IR children (a
 * TabView its panel, a RouteDrawer its content plus the drawer), so a
 * renderer-owned tab strip would sit at a child index the patch paths address —
 * the corruption the contract forbids. What the renderer can do is say the truth
 * about the state, which is what a11y and the base sheet need: the panel is named
 * after its active tab, and the drawer's `open` becomes an attribute the sheet
 * slides on. The strip itself is a `TabBar` beside the TabView — a widget with no
 * IR child, so the renderer *can* draw its tabs (see applyTabBarProps) — wired to
 * the same handler.
 *
 * @param {HTMLElement} el   The TabView / RouteDrawer element.
 * @param {string} type      The widget type.
 * @param {Object} props     The props being applied.
 * @returns {void}
 */
function applyPanelProps(el, type, props) {
  if (type === "TabView") {
    const tabs = Array.isArray(props.tabs) ? props.tabs : null;
    if ("active" in props) {
      setOrRemove(el, ACTIVE_ATTR, props.active);
    }
    if (!el.hasAttribute("role")) {
      el.setAttribute("role", "tabpanel");
    }
    const active = Number(el.getAttribute(ACTIVE_ATTR) ?? 0);
    if (tabs != null && tabs[active] != null && !el.hasAttribute("aria-label")) {
      el.setAttribute("aria-label", String(tabs[active]));
    }
    return;
  }
  if ("open" in props) {
    const open = Boolean(props.open);
    setOrRemove(el, OPEN_ATTR, open ? "" : null);
    el.setAttribute("aria-expanded", String(open));
  }
}

function applyControlProps(el, type, props) {
  if (type === "Canvas") {
    paintCanvas(el, props);
  } else if (type === "Input") {
    applyInputType(el, props);
    if ("value" in props) {
      el.value = props.value == null ? "" : String(props.value);
    }
    if ("placeholder" in props) {
      setOrRemove(el, "placeholder", props.placeholder);
    }
    if ("max_length" in props) {
      setOrRemove(el, "maxlength", props.max_length);
    }
  } else if (type === "TextArea") {
    if ("value" in props) {
      el.value = props.value == null ? "" : String(props.value);
    }
    if ("placeholder" in props) {
      setOrRemove(el, "placeholder", props.placeholder);
    }
    if ("rows" in props) {
      setOrRemove(el, "rows", props.rows);
    }
    if ("max_length" in props) {
      setOrRemove(el, "maxlength", props.max_length);
    }
  } else if (type === "MaskedInput") {
    applyInputType(el, props);
    if ("mask" in props) {
      setOrRemove(el, MASK_ATTR, props.mask);
    }
    if ("value" in props) {
      el.value = props.value == null ? "" : String(props.value);
    }
    if ("placeholder" in props) {
      setOrRemove(el, "placeholder", props.placeholder);
    }
  } else if (type === "PinInput") {
    applyPinProps(el, props);
  } else if (type === "Checkbox") {
    const input = ensureNestedInput(el, "checkbox");
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
  } else if (type === "Switch") {
    applySwitchProps(el, props);
  } else if (type === "Slider") {
    applySliderProps(el, props);
  } else if (type === "RangeSlider") {
    applyRangeSliderProps(el, props);
  } else if (type === "Dropdown") {
    applyDropdownProps(el, props);
  } else if (type === "Autocomplete") {
    applyAutocompleteProps(el, props);
  } else if (type != null && type in PICKER_INPUT_TYPES) {
    applyPickerProps(el, type, props);
  } else if (type === "TabBar") {
    applyTabBarProps(el, props);
  } else if (type === "TabView" || type === "RouteDrawer") {
    applyPanelProps(el, type, props);
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
 * Repaint every Canvas under `root` at its current on-screen size.
 *
 * The first paint happens while the element is still detached, so it has no box
 * to measure and falls back to the declared size; the same is true after the
 * window resizes. Callers run this once layout exists (see `mount`), which is
 * what keeps a chart sharp instead of a stretched bitmap.
 *
 * @param {HTMLElement} root  The mount root to search under.
 * @returns {void}
 */
export function repaintCanvases(root) {
  const canvases = root.querySelectorAll('[data-tw-type="Canvas"]');
  for (const el of canvases) {
    paintCanvas(/** @type {any} */ (el), {});
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
