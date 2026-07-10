// widget-support.js — hand-authored support for the generated widget builders.
//
// The IR widget builders in widgets.gen.js are generated from tempest_core (see
// tests/conformance/_transpile_widgets.py). This module holds the small, stable
// pieces they lean on: the Style shape filler, the Edge helper, and the
// Material 3 style resolver that reads the introspected WIDGET_STYLES table.
//
// See docs/contract.md (wire format) and docs/modo-c-transpile.md (Mode C).

import { WIDGET_STYLES } from "./widget-styles.gen.js";

/**
 * The complete set of `Style` field names in the core's serialized shape
 * (tempest-core >= 0.11). {@link Style} fills every one, defaulting unset fields
 * to `null`, so a Style object always carries the keys the core emits.
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
 * so the result matches the wire contract. `Color` is `{ r, g, b, a }` and `Edge`
 * is `{ top, right, bottom, left }`; pass those shapes through unchanged.
 *
 * @param {Object<string, *>} [partial]  The fields to set (any subset). Unknown
 *        keys are ignored.
 * @returns {Object<string, *>}  The complete Style object.
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
 * Resolve a widget's baked Material 3 style from the introspected defaults table.
 *
 * The default style for the widget's variant/size/color_scheme combination (from
 * the build-time-introspected {@link WIDGET_STYLES} table, keyed with `"_"` for
 * axes the widget lacks) is the base; an explicit `style` is merged **on top** —
 * the caller's set (non-null) fields win. The result is a full `Style` object
 * (unset fields `null`), matching the core's wire shape so the diff stays stable.
 *
 * @param {string} widget  The widget type name (e.g. `"Button"`).
 * @param {string} variant  The variant / field_variant axis, or `"_"`.
 * @param {string} size  The size axis, or `"_"`.
 * @param {string} colorScheme  The color-scheme axis, or `"_"`.
 * @param {?Object} override  The caller's explicit style, or `null`.
 * @returns {Object<string, *>}  The resolved, full Style object.
 */
export function resolveWidgetStyle(widget, variant, size, colorScheme, override) {
  const base = WIDGET_STYLES[widget]?.[variant]?.[size]?.[colorScheme] ?? {};
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
