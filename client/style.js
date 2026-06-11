// style.js — translate a Style object (Pydantic dump) to CSS.  PHASE W2.
//
// styleToCss(style) -> string of CSS declarations joined by "; ", covering the v1
// fields: flex (direction/justify/align/align_self/grow/gap/flex_wrap), box model
// (padding/margin via Edge {top,right,bottom,left}), border/radius, background/color
// (Color {r,g,b,a} -> rgba()), typography (font_*) and dimensions (width/height/
// min/max). Style is the same Pydantic model the desktop Qt renderer consumes; CSS
// is the native target, so the mapping is closer to identity than the QSS one in
//   ../../tempestroid/tempestroid/renderers/qt/style_translator.py
//
// Verify against ../tests/fixtures/style_sample.json in tests/client/.

/**
 * @typedef {Object} ColorDump
 * @property {number} r  Red channel, 0-255.
 * @property {number} g  Green channel, 0-255.
 * @property {number} b  Blue channel, 0-255.
 * @property {number} a  Alpha channel, 0.0-1.0.
 */

/**
 * @typedef {Object} EdgeDump
 * @property {number} top     Top spacing, px.
 * @property {number} right   Right spacing, px.
 * @property {number} bottom  Bottom spacing, px.
 * @property {number} left    Left spacing, px.
 */

/**
 * @typedef {Object} BorderDump
 * @property {number} width        Border width, px.
 * @property {?ColorDump} color    Border color, or null for the renderer default.
 */

/**
 * @typedef {Object} SideBorderDump
 * @property {?BorderDump} top     Top side border, or null.
 * @property {?BorderDump} right   Right side border, or null.
 * @property {?BorderDump} bottom  Bottom side border, or null.
 * @property {?BorderDump} left    Left side border, or null.
 */

/**
 * @typedef {Object} CornersDump
 * @property {number} top_left      Top-left radius, px.
 * @property {number} top_right     Top-right radius, px.
 * @property {number} bottom_right  Bottom-right radius, px.
 * @property {number} bottom_left   Bottom-left radius, px.
 */

/**
 * @typedef {Object} GradientStopDump
 * @property {ColorDump} color  The stop color.
 * @property {number} position  The stop position, 0.0-1.0.
 */

/**
 * @typedef {Object} GradientDump
 * @property {GradientStopDump[]} stops  Ordered color stops.
 * @property {string} direction          One of GradientDirection's values.
 */

// flex `justify`/`align` map cleanly except for "start"/"end", which CSS spells
// "flex-start"/"flex-end". Everything else (center, space-*, stretch) is identity.
const FLEX_EDGE = Object.freeze({ start: "flex-start", end: "flex-end" });

/**
 * Map a flex justify-content value (core spelling) to its CSS spelling.
 * @param {string} value  A JustifyContent value ("start", "center", ...).
 * @returns {string}      The CSS `justify-content` keyword.
 */
function justifyToCss(value) {
  return FLEX_EDGE[value] ?? value;
}

/**
 * Map a flex align-items value (core spelling) to its CSS spelling.
 * @param {string} value  An AlignItems value ("start", "stretch", ...).
 * @returns {string}      The CSS `align-items` keyword.
 */
function alignToCss(value) {
  return FLEX_EDGE[value] ?? value;
}

/**
 * Render a Color dump as a CSS `rgba(r, g, b, a)` string.
 * @param {ColorDump} color  The color dump.
 * @returns {string}         The `rgba(...)` value.
 */
export function colorToRgba(color) {
  return `rgba(${color.r}, ${color.g}, ${color.b}, ${color.a})`;
}

/**
 * Test whether a dump looks like a Gradient (has `stops`) rather than a Color.
 * @param {Object} background  A Color or Gradient dump.
 * @returns {boolean}          True when the dump is a gradient.
 */
function isGradient(background) {
  return Array.isArray(background.stops);
}

// CSS gradient axis keyword per core GradientDirection.
const GRADIENT_DIRECTION = Object.freeze({
  "top-bottom": "to bottom",
  "bottom-top": "to top",
  "left-right": "to right",
  "right-left": "to left",
});

/**
 * Render a background dump (Color or Gradient) as a CSS background value.
 * @param {ColorDump|GradientDump} background  The background dump.
 * @returns {string}                           A CSS color or `linear-gradient(...)`.
 */
function backgroundToCss(background) {
  if (isGradient(background)) {
    const axis = GRADIENT_DIRECTION[background.direction] ?? "to bottom";
    const stops = background.stops
      .map((stop) => `${colorToRgba(stop.color)} ${stop.position * 100}%`)
      .join(", ");
    return `linear-gradient(${axis}, ${stops})`;
  }
  return colorToRgba(/** @type {ColorDump} */ (background));
}

/**
 * Render an Edge dump as a CSS shorthand `top right bottom left` (in px).
 * @param {EdgeDump} edge  The edge dump.
 * @returns {string}       The four-value px shorthand.
 */
function edgeToCss(edge) {
  return `${edge.top}px ${edge.right}px ${edge.bottom}px ${edge.left}px`;
}

/**
 * Render a single uniform Border dump as a CSS `Npx solid color` value.
 * @param {BorderDump} border  The border dump.
 * @returns {string}           The CSS border value.
 */
function borderValue(border) {
  const color = border.color ? colorToRgba(border.color) : "currentColor";
  return `${border.width}px solid ${color}`;
}

/**
 * Test whether a border dump is per-side (SideBorder) rather than uniform.
 * @param {BorderDump|SideBorderDump} border  The border dump.
 * @returns {boolean}                         True when the dump is per-side.
 */
function isSideBorder(border) {
  return (
    "top" in border || "right" in border || "bottom" in border || "left" in border
  );
}

/**
 * Render a border dump (uniform or per-side) as one or more CSS declarations.
 * @param {BorderDump|SideBorderDump} border  The border dump.
 * @returns {string[]}                        CSS declarations (e.g. ["border: ..."]).
 */
function borderRules(border) {
  if (isSideBorder(border)) {
    const side = /** @type {SideBorderDump} */ (border);
    /** @type {string[]} */
    const rules = [];
    for (const name of /** @type {const} */ (["top", "right", "bottom", "left"])) {
      const value = side[name];
      if (value != null) {
        rules.push(`border-${name}: ${borderValue(value)}`);
      }
    }
    return rules;
  }
  return [`border: ${borderValue(/** @type {BorderDump} */ (border))}`];
}

/**
 * Test whether a radius dump is per-corner (Corners) rather than a single float.
 * @param {number|CornersDump} radius  The radius dump.
 * @returns {boolean}                  True when the dump is per-corner.
 */
function isCorners(radius) {
  return typeof radius === "object" && radius !== null;
}

/**
 * Render a radius dump (uniform float or per-corner Corners) as a CSS value.
 * @param {number|CornersDump} radius  The radius dump.
 * @returns {string}                   The CSS `border-radius` value (in px).
 */
function radiusValue(radius) {
  if (isCorners(radius)) {
    const c = /** @type {CornersDump} */ (radius);
    return `${c.top_left}px ${c.top_right}px ${c.bottom_right}px ${c.bottom_left}px`;
  }
  return `${radius}px`;
}

// CSS keyword per core FontStyle / TextDecoration (identity, but kept explicit so
// an unmapped value never silently leaks an invalid CSS keyword).
const FONT_STYLE = Object.freeze({ normal: "normal", italic: "italic" });
const TEXT_DECORATION = Object.freeze({
  none: "none",
  underline: "underline",
  "line-through": "line-through",
});

/**
 * Translate a serialized Style into a CSS string (declarations joined by "; ").
 *
 * Field order follows the source model (flex, box model, paint, typography,
 * dimensions, stacking) so the emitted declarations are stable across runs.
 * `null`/absent fields are skipped entirely — they mean "unset" and let the
 * browser default apply. Layout-only flags that have no CSS analogue beyond what
 * is emitted (opacity, shadow, transition, stack/position insets) are handled
 * inline; unsupported v1 fields are simply not emitted.
 *
 * @param {?Object} style  Style dump, or null.
 * @returns {string}       A "; "-joined CSS declaration body ("" when empty/null).
 */
export function styleToCss(style) {
  if (style == null) {
    return "";
  }
  /** @type {string[]} */
  const rules = [];

  // Flexbox layout. A direction present implies a flex container.
  if (style.direction != null) {
    rules.push("display: flex");
    rules.push(`flex-direction: ${style.direction}`);
  }
  if (style.justify != null) {
    rules.push(`justify-content: ${justifyToCss(style.justify)}`);
  }
  if (style.align != null) {
    rules.push(`align-items: ${alignToCss(style.align)}`);
  }
  if (style.align_self != null) {
    rules.push(`align-self: ${alignToCss(style.align_self)}`);
  }
  if (style.grow != null) {
    rules.push(`flex-grow: ${style.grow}`);
  }
  if (style.gap != null) {
    rules.push(`gap: ${style.gap}px`);
  }
  if (style.flex_wrap != null) {
    rules.push(`flex-wrap: ${style.flex_wrap}`);
  }

  // Box model.
  if (style.padding != null) {
    rules.push(`padding: ${edgeToCss(style.padding)}`);
  }
  if (style.margin != null) {
    rules.push(`margin: ${edgeToCss(style.margin)}`);
  }
  if (style.border != null) {
    rules.push(...borderRules(style.border));
  }
  if (style.radius != null) {
    rules.push(`border-radius: ${radiusValue(style.radius)}`);
  }

  // Paint.
  if (style.background != null) {
    rules.push(`background: ${backgroundToCss(style.background)}`);
  }
  if (style.color != null) {
    rules.push(`color: ${colorToRgba(style.color)}`);
  }
  if (style.opacity != null) {
    rules.push(`opacity: ${style.opacity}`);
  }

  // Typography.
  if (style.font_family != null) {
    rules.push(`font-family: ${style.font_family}`);
  }
  if (style.font_size != null) {
    rules.push(`font-size: ${style.font_size}px`);
  }
  if (style.font_weight != null) {
    rules.push(`font-weight: ${style.font_weight}`);
  }
  if (style.font_style != null) {
    rules.push(`font-style: ${FONT_STYLE[style.font_style] ?? style.font_style}`);
  }
  if (style.text_align != null) {
    rules.push(`text-align: ${style.text_align}`);
  }
  if (style.text_decoration != null) {
    rules.push(
      `text-decoration: ${TEXT_DECORATION[style.text_decoration] ?? style.text_decoration}`,
    );
  }
  if (style.letter_spacing != null) {
    rules.push(`letter-spacing: ${style.letter_spacing}px`);
  }
  if (style.line_height != null) {
    rules.push(`line-height: ${style.line_height}`);
  }

  // Dimensions.
  if (style.width != null) {
    rules.push(`width: ${style.width}px`);
  }
  if (style.height != null) {
    rules.push(`height: ${style.height}px`);
  }
  if (style.min_width != null) {
    rules.push(`min-width: ${style.min_width}px`);
  }
  if (style.max_width != null) {
    rules.push(`max-width: ${style.max_width}px`);
  }
  if (style.min_height != null) {
    rules.push(`min-height: ${style.min_height}px`);
  }
  if (style.max_height != null) {
    rules.push(`max-height: ${style.max_height}px`);
  }
  if (style.aspect_ratio != null) {
    rules.push(`aspect-ratio: ${style.aspect_ratio}`);
  }

  return rules.join("; ");
}
