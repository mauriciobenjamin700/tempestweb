// widgets.js — pure IR constructors for Mode C (transpile).
//
// Each widget factory returns a serialized Node in the EXACT shape the core
// (tempest-core >= 0.11) emits: { type, key, props, children } with `attrs: {}`
// and `tag: null` on every node. These mirror the tempest_core widget builders so
// the JS `diff` (client/transpile/diff.js) conforms against the golden fixtures.
//
// The shared renderer (client/dom.js) reads only `type`/`key`/`props`/`children`
// and ignores props it doesn't know (color_scheme, size, variant, on_click, ...),
// so carrying the full core prop set here is harmless — it just keeps the wire
// shape faithful.
//
// Handler note (spike): the wire prop `on_click` is always `null` (matching the
// core fixtures, where handlers are serialized as a reference, never a function),
// which also keeps `diff` stable across re-renders that rebuild fresh closures.
// The real JS click closure is stashed on a SEPARATE, non-wire node field
// (`onClick`) that `diff` never inspects; the runtime collects handlers from it.
//
// See docs/contract.md (wire format) and docs/modo-c-transpile.md (Mode C).

import { WIDGET_STYLES } from "./widget-styles.gen.js";

/**
 * @typedef {import("../transport.js").Node} Node
 */

/**
 * The complete set of `Style` field names in the core's serialized order-agnostic
 * shape (tempest-core >= 0.11). {@link Style} fills every one, defaulting unset
 * fields to `null`, so a Style object always has the same keys the core emits.
 * @type {readonly string[]}
 */
const STYLE_FIELDS = Object.freeze([
  "align",
  "align_self",
  "aspect_ratio",
  "background",
  "border",
  "bottom",
  "color",
  "direction",
  "flex_wrap",
  "font_asset",
  "font_family",
  "font_size",
  "font_style",
  "font_weight",
  "gap",
  "grow",
  "height",
  "justify",
  "left",
  "letter_spacing",
  "line_height",
  "margin",
  "max_height",
  "max_lines",
  "max_width",
  "min_height",
  "min_width",
  "opacity",
  "padding",
  "position",
  "radius",
  "right",
  "shadow",
  "stack_align",
  "text_align",
  "text_decoration",
  "text_overflow",
  "text_scale",
  "top",
  "transition",
  "width",
]);

/**
 * Build a full `Style` object from a partial one.
 *
 * Fills every field in the core's Style shape, defaulting unset fields to `null`,
 * so the result matches the wire contract (see `style_sample.json`). `Color` is
 * `{ r, g, b, a }` and `Edge` is `{ top, right, bottom, left }`; pass those shapes
 * through unchanged (use {@link Edge.all} for a uniform edge).
 *
 * @param {Object<string, *>} [partial]  The fields to set (any subset of the
 *        Style shape). Unknown keys are ignored.
 * @returns {Object<string, *>}          The complete Style object.
 */
export function Style(partial = {}) {
  /** @type {Object<string, *>} */
  const style = {};
  for (const field of STYLE_FIELDS) {
    style[field] = field in partial ? partial[field] : null;
  }
  return style;
}

/**
 * Edge helpers — a box's four side offsets in px (`{ top, right, bottom, left }`).
 */
export const Edge = Object.freeze({
  /**
   * A uniform edge with the same value on all four sides.
   * @param {number} n  The px value for every side.
   * @returns {{top: number, right: number, bottom: number, left: number}}
   */
  all(n) {
    return { top: n, right: n, bottom: n, left: n };
  },
});

/**
 * Build a `Text` IR node.
 * @param {{content: string, key?: ?string, style?: ?Object}} args
 * @returns {Node}
 */
export function Text({ content, key = null, style = null }) {
  return {
    type: "Text",
    key,
    props: {
      attrs: {},
      content,
      focus_order: null,
      focusable: null,
      semantics: null,
      style,
      tag: null,
    },
    children: [],
  };
}

/**
 * Build a `Column` IR node (a vertical flex container).
 * @param {{children?: Node[], key?: ?string, style?: ?Object}} args
 * @returns {Node}
 */
export function Column({ children = [], key = null, style = null }) {
  return {
    type: "Column",
    key,
    props: {
      attrs: {},
      focus_order: null,
      focusable: null,
      semantics: null,
      style,
      tag: null,
    },
    children,
  };
}

/**
 * Build a `Row` IR node (a horizontal flex container).
 * @param {{children?: Node[], key?: ?string, style?: ?Object}} args
 * @returns {Node}
 */
export function Row({ children = [], key = null, style = null }) {
  return {
    type: "Row",
    key,
    props: {
      attrs: {},
      focus_order: null,
      focusable: null,
      semantics: null,
      style,
      tag: null,
    },
    children,
  };
}

/**
 * Resolve a Button's baked style from its variant/size/color_scheme.
 *
 * Mirrors the core: the default Material 3 style for the combination (from the
 * build-time-introspected {@link WIDGET_STYLES} table) is the base, and an
 * explicit `style` is merged **on top** — the caller's set (non-null) fields win.
 * The result is a full `Style` object (unset fields `null`), matching the core's
 * wire shape so the diff stays stable across re-renders.
 *
 * @param {string} variant  The button variant (e.g. `"solid"`).
 * @param {string} size  The density size (e.g. `"md"`).
 * @param {string} colorScheme  The Material 3 color scheme (e.g. `"primary"`).
 * @param {?Object} override  The caller's explicit style, or `null`.
 * @returns {Object<string, *>}  The resolved, full Style object.
 */
function resolveButtonStyle(variant, size, colorScheme, override) {
  const base = WIDGET_STYLES.Button?.[variant]?.[size]?.[colorScheme] ?? {};
  const merged = { ...base };
  if (override != null) {
    for (const [field, value] of Object.entries(override)) {
      if (value !== null && value !== undefined) {
        merged[field] = value;
      }
    }
  }
  return Style(merged);
}

/**
 * Build a `Button` IR node with its Material 3 variant style resolved.
 *
 * The `variant`/`size`/`color_scheme` select the baked default style (see
 * {@link resolveButtonStyle}); an explicit `style` layers over it. The wire prop
 * `on_click` is always `null` (a serialized reference in the core; see the module
 * header). The actual JS click closure is stashed on the separate, non-wire
 * `onClick` field that {@link import("./diff.js").diff} never inspects — the
 * runtime (`client/transpile/runtime.js`) collects handlers from it by key.
 *
 * @param {{label: string, onClick?: ?Function, key?: ?string, style?: ?Object,
 *          variant?: string, size?: string, colorScheme?: string}} args
 * @returns {Node & {onClick: ?Function}}
 */
export function Button({
  label,
  onClick = null,
  key = null,
  style = null,
  variant = "solid",
  size = "md",
  colorScheme = "primary",
}) {
  return {
    type: "Button",
    key,
    props: {
      attrs: {},
      color_scheme: colorScheme,
      focus_order: null,
      focusable: null,
      label,
      on_click: null,
      semantics: null,
      size,
      style: resolveButtonStyle(variant, size, colorScheme, style),
      tag: null,
      variant,
    },
    children: [],
    // Non-wire: the live click closure, collected by the runtime, ignored by diff.
    onClick,
  };
}
