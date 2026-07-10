// components.js — Mode C ergonomic layout components (hand-authored).
//
// The tempest_core *components* layer (Card, DataTable, Tabs, …) is Python
// composition: each builds to a tree of primitive widgets at build() time, so it
// cannot be auto-ported to a zero-Python runtime the way the widgets were. The
// pure layout aliases HStack / VStack are the exception — they expand to a plain
// Row / Column with a resolved gap/align/justify, so they port cleanly here.
//
// Data-driven components (charts, tables, inputs, pickers) remain out of scope;
// compose them from primitives, or use Modes A/B. See docs/modo-c-transpile.md.

import { Column, Row } from "./widgets.gen.js";
import { SPACING_STEPS } from "./spacing.gen.js";
import { Style } from "./widget-support.js";

/**
 * Resolve a `gap` to logical pixels: a token name via the theme scale, or a
 * raw number passed through unchanged.
 * @param {number|string} gap  A spacing token (`"md"`) or a pixel value.
 * @returns {?number}  The resolved gap in px, or null when unknown.
 */
function resolveGap(gap) {
  if (typeof gap === "number") {
    return gap;
  }
  return SPACING_STEPS[gap] ?? null;
}

/**
 * `HStack` — a horizontal stack (SwiftUI-style ergonomic Row).
 *
 * Children are laid left-to-right with a token-step `gap` (`"md"`) or a raw px
 * value; `align` (cross-axis) and `justify` (main-axis) are surfaced directly.
 * Expands to a primitive `Row`, matching `tempest_core.components.HStack`.
 *
 * @param {{children?: import("../transport.js").Node[], gap?: number|string,
 *          align?: ?string, justify?: ?string, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function HStack({ children = [], gap = "md", align = "center", justify = null, key = null } = {}) {
  return Row({
    key,
    children,
    style: Style({ gap: resolveGap(gap), align, justify }),
  });
}

/**
 * `VStack` — a vertical stack (SwiftUI-style ergonomic Column).
 *
 * Children are stacked top-to-bottom with a token-step `gap` or a raw px value;
 * `align` (cross-axis) and `justify` (main-axis) are surfaced directly. Expands
 * to a primitive `Column`, matching `tempest_core.components.VStack`.
 *
 * @param {{children?: import("../transport.js").Node[], gap?: number|string,
 *          align?: ?string, justify?: ?string, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function VStack({ children = [], gap = "md", align = null, justify = null, key = null } = {}) {
  return Column({
    key,
    children,
    style: Style({ gap: resolveGap(gap), align, justify }),
  });
}
