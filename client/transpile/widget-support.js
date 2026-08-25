// widget-support.js — hand-authored support for the generated widget builders.
//
// The IR widget builders in widgets.gen.js are generated from tempest_core (see
// tests/conformance/_transpile_widgets.py). This module holds the small, stable
// pieces they lean on: the Style shape filler, the Edge helper, and the
// Material 3 style resolver that reads the introspected WIDGET_STYLES table.
//
// See docs/contract.md (wire format) and docs/modo-c-transpile.md (Mode C).

import { WIDGET_STYLES } from "./widget-styles.gen.js";
import { COLOR_ROLES } from "./component-styles.gen.js";
import { Border, SideBorder } from "./values.gen.js";

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
 * Build a `Color` (the `{ r, g, b, a }` wire shape). Mirrors
 * `tempest_core.style.Color`; a Style field value, so no `new`.
 *
 * @param {{r?: number, g?: number, b?: number, a?: number}} [args]
 * @returns {{r: number, g: number, b: number, a: number}}
 */
export function Color({ r = 0, g = 0, b = 0, a = 1.0 } = {}) {
  return { r, g, b, a };
}

/**
 * Parse a `#RGB` / `#RRGGBB` / `#RRGGBBAA` string into a `Color`.
 *
 * How an app writes a literal color — the spelling behind 65 call sites in the
 * examples — and Mode C shipped `Color` as a bare factory, so
 * `Color.from_hex("#b3261e")` compiled, loaded and threw at mount with a blank
 * page. Mirrors `tempest_core.style.Color._parse_hex`: the `#` is optional, a
 * three-digit form doubles each digit, and the fourth byte is alpha over 255.
 *
 * @param {string} value  The hex string, with or without a leading `#`.
 * @returns {{r: number, g: number, b: number, a: number}}
 * @throws {Error} When the string is not a valid hex color.
 */
Color.from_hex = function from_hex(value) {
  let text = String(value).replace(/^#+/, "");
  if (text.length === 3) {
    text = [...text].map((ch) => ch + ch).join("");
  }
  if ((text.length !== 6 && text.length !== 8) || !/^[0-9a-fA-F]+$/.test(text)) {
    throw new Error(`invalid hex color: ${JSON.stringify(value)}`);
  }
  return {
    r: parseInt(text.slice(0, 2), 16),
    g: parseInt(text.slice(2, 4), 16),
    b: parseInt(text.slice(4, 6), 16),
    a: text.length === 8 ? parseInt(text.slice(6, 8), 16) / 255 : 1.0,
  };
};
Object.freeze(Color);

/**
 * A box's four side offsets in px (`{ top, right, bottom, left }`).
 *
 * Callable like the core's `Edge`, which is a model with four fields defaulting
 * to `0.0`: `Edge(top=20.0, left=20.0)` is how an app names two sides and leaves
 * the others at zero. Mode C exposed only the `all`/`symmetric` helpers, so that
 * spelling compiled into `Edge({...})` against a frozen object and the page died
 * on `Edge is not a function` — measured in `examples/image-gallery`, which
 * rendered nothing at all.
 *
 * @param {{top?: number, right?: number, bottom?: number, left?: number}} [args]
 * @returns {{top: number, right: number, bottom: number, left: number}}
 */
export function Edge({ top = 0.0, right = 0.0, bottom = 0.0, left = 0.0 } = {}) {
  return { top, right, bottom, left };
}

/**
 * A uniform edge with the same value on all four sides.
 * @param {number} n  The px value for every side.
 * @returns {{top: number, right: number, bottom: number, left: number}}
 */
Edge.all = function all(n) {
  return { top: n, right: n, bottom: n, left: n };
};

/**
 * An edge with one value top/bottom and another left/right.
 * @param {{vertical?: number, horizontal?: number}} [args]
 * @returns {{top: number, right: number, bottom: number, left: number}}
 */
Edge.symmetric = function symmetric({ vertical = 0.0, horizontal = 0.0 } = {}) {
  return { top: vertical, right: horizontal, bottom: vertical, left: horizontal };
};

Object.freeze(Edge);

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
 * @param {?Object} [theme]  The widget's theme; its mode picks the leaf.
 * @returns {Object<string, *>}  The resolved, full Style object.
 */
export function resolveWidgetStyle(widget, variant, size, colorScheme, override, theme) {
  const leaf = WIDGET_STYLES[widget]?.[variant]?.[size]?.[colorScheme];
  const base = leaf?.[themeMode(theme)] ?? {};
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
 * Which leaf of a generated style table a theme selects: `"light"` or `"dark"`.
 *
 * A widget built with no theme resolves light in the core, so an absent theme
 * answers `"light"` here too. `SYSTEM` defers to the platform flag exactly as
 * `Theme.is_dark` does, which is why the theme object is asked instead of its
 * `mode` string being read.
 *
 * @param {?Object} theme  A `Theme` (or anything with `is_dark`), or null.
 * @returns {string}       The table key.
 */
export function themeMode(theme) {
  return theme != null && typeof theme.is_dark === "function" && theme.is_dark()
    ? "dark"
    : "light";
}

/**
 * The Material 3 colour roles of a theme, from the generated table.
 *
 * @param {?Object} theme  The widget's theme, or null for the light default.
 * @returns {Object<string, Object>}  Role name -> serialized colour.
 */
export function colorRoles(theme) {
  return COLOR_ROLES[themeMode(theme)];
}

/**
 * The mode slice of any generated table that carries colour.
 *
 * Every colour-carrying table in `component-styles.gen.js` is keyed by mode
 * first, so a component reads its own axes off this slice.
 *
 * @param {Object} table   The generated table.
 * @param {?Object} theme  The component's theme, or null for light.
 * @returns {Object}       The table for this theme's mode.
 */
export function modeTable(table, theme) {
  return table[themeMode(theme)];
}

/**
 * The resolved style for a field widget, honoring the invalid (error) state.
 *
 * The generated table carries the **resting** style per variant/size/scheme,
 * which is the whole story for every widget but a field: the core repaints an
 * invalid field's border and text in the `error` role at build time, so the rule
 * lives in the built style and not in the stylesheet. Without it a Mode C field
 * carrying a validation message rendered as if it were fine. A flushed field
 * keeps its single bottom edge, and the caller's own `style` still wins last —
 * both mirroring `_apply_field_state` in `tempest_core.variants`.
 *
 * @param {string} widget       The core widget name (a `WIDGET_STYLES` key).
 * @param {string} fieldVariant The field treatment (outline/filled/flushed).
 * @param {string} size         The density size.
 * @param {string} colorScheme  The Material 3 scheme name.
 * @param {string} error        The validation message; empty means valid.
 * @param {?Object} override    The caller's style, or null.
 * @param {?Object} [theme]     The widget's theme; its mode picks the palette.
 * @returns {Object}            The complete Style object.
 */
export function resolveFieldStyle(
  widget,
  fieldVariant,
  size,
  colorScheme,
  error,
  override,
  theme,
) {
  if (!error) {
    return resolveWidgetStyle(widget, fieldVariant, size, colorScheme, override, theme);
  }
  const roles = colorRoles(theme);
  const edge = Border({ width: 1.0, color: roles.error });
  const layered = {
    border: fieldVariant === "flushed" ? SideBorder({ bottom: edge }) : edge,
    color: roles.error,
  };
  if (override != null) {
    for (const [field, value] of Object.entries(override)) {
      if (value !== null && value !== undefined) {
        layered[field] = value;
      }
    }
  }
  return resolveWidgetStyle(widget, fieldVariant, size, colorScheme, layered, theme);
}

/**
 * Run a `Form`'s field validators over `values`, the way the core's method does.
 *
 * The client carries each widget's *builder* and none of the Python methods its
 * class also has, so `form.validate(values)` had nowhere to land: it was refused
 * where the compiler could tell the receiver was a `Form`, and compiled into
 * `form1.validate is not a function` where it could not.
 *
 * The port is possible because `validators` never crosses a wire in Mode C — the
 * generated builder puts the array straight on the node, so the live functions
 * are right here. Mirrors `Form.validate` + `FormField.run_validators`: the first
 * failing validator per field wins, a name absent from `values` validates as the
 * empty string, and `valid` means no field failed.
 *
 * A receiver that is not a `Form` node keeps its own `validate`, so an app object
 * that happens to have one is untouched.
 *
 * @param {Object} target  The `Form` IR node (or any object with `.validate`).
 * @param {Object<string, *>} values  Field name -> its raw value.
 * @returns {{errors: Object<string, string>, valid: boolean}}  The `FormState`.
 */
export function formValidate(target, values) {
  if (target?.type !== "Form") {
    return target.validate(values);
  }
  const errors = {};
  for (const field of target.children ?? []) {
    const name = field?.props?.name;
    if (name == null) {
      continue;
    }
    const value = Object.hasOwn(values ?? {}, name) ? values[name] : "";
    for (const rule of field.props.validators ?? []) {
      const error = rule(value);
      if (error != null) {
        errors[name] = error;
        break;
      }
    }
  }
  return { errors, valid: Object.keys(errors).length === 0 };
}

/**
 * The window each virtualized list is currently slid to, by widget key.
 *
 * The core injects a tracked window into the widget tree *before* the children
 * are materialized (`App._inject_windows`). A Mode C builder has no app to ask
 * and materializes as it runs, so the runtime publishes the map here for the
 * duration of `view(app)` — the same ambient shape `use_theme` has in the core.
 * @type {?Map<string, number[]>}
 */
let SLID_WINDOWS = null;

/**
 * Publish the app's tracked list windows for the duration of a build.
 *
 * @param {?Map<string, number[]>} windows  The window map, or null to clear it.
 * @returns {void}
 */
export function setSlidWindows(windows) {
  SLID_WINDOWS = windows;
}

/**
 * Materialize a lazy scroller's visible window into keyed item nodes.
 *
 * A generated builder is a passthrough, and the lazy scrollers are the one place
 * where a widget's children do not exist until something runs: the core calls
 * `item_builder(index)` for each index in the resolved window and re-keys each
 * item by its **absolute index**, so the reconciler turns a window slide into a
 * minimal remove/reorder/insert instead of rebuilding the list. This mirrors
 * `_resolve_window` + `_materialize_items` in `tempest_core.widgets.lists`.
 *
 * The window is clamped to `itemCount`: an app slides `window` on a scroll event
 * and a stale pair must not address items that no longer exist. With no window
 * set, the initial `[0, min(windowSize, itemCount))` materializes, which is what
 * gives the first mount content.
 *
 * A window the app slid (a `scroll` event the runtime applied) wins over the
 * one the view declared, exactly as the core's injection overwrites it: the
 * view re-runs on every rebuild and would otherwise snap the list back to its
 * declared window on the next state change.
 *
 * @param {?string} key        The list's widget key, used to find a slid window.
 * @param {?function(number): import("../transport.js").Node} itemBuilder
 *   The factory building the item at an index; `null` yields no children.
 * @param {number} itemCount   The total number of items.
 * @param {?number[]} window   The explicit `[start, end)` override, or null.
 * @param {number} windowSize  The initial window size when no override is set.
 * @returns {import("../transport.js").Node[]}  The materialized window.
 */
export function lazyChildren(key, itemBuilder, itemCount, window, windowSize) {
  if (typeof itemBuilder !== "function") {
    return [];
  }
  const slid = key != null && SLID_WINDOWS != null ? SLID_WINDOWS.get(key) : undefined;
  const effective = slid ?? window;
  const count = Math.max(0, itemCount ?? 0);
  let start;
  let end;
  if (effective == null) {
    start = 0;
    end = Math.min(windowSize ?? 0, count);
  } else {
    [start, end] = effective;
  }
  start = Math.max(0, Math.min(start, count));
  end = Math.max(start, Math.min(end, count));
  const items = [];
  for (let index = start; index < end; index += 1) {
    items.push({ ...itemBuilder(index), key: String(index) });
  }
  return items;
}
