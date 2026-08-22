// components.js — Mode C components (hand-authored, parity-pinned).
//
// The tempest_core *components* layer is Python composition: each one builds to a
// tree of primitive widgets at build() time, so it cannot be auto-ported to a
// zero-Python runtime the way the widgets were. What ports is the composition
// itself — rewritten here per component — plus the *output* of the core's style
// resolvers, which are pure and therefore travel as generated tables
// (component-styles.gen.js), exactly as widget-styles.gen.js does for widgets.
//
// Every builder here is pinned by tests/fixtures/transpile_component_samples.json,
// built from the real core over a matrix of props: if a component's composition or
// resolved style drifts, the JS test fails until this file follows.
//
// Still out of scope: the data-driven components (DataTable, charts, Tabs, form
// pickers) whose composition depends on the data they are handed. Compose them
// from primitives, or use Modes A/B. See docs/advanced/transpile.md.

import { Button, Column, Container, Row, ScrollView, Text } from "./widgets.gen.js";
import { SPACING_STEPS } from "./spacing.gen.js";
import { Edge, Style, resolveWidgetStyle } from "./widget-support.js";
import {
  BADGE_STYLES,
  COLOR_ROLES,
  SELECTION_ACCENT,
  SHAPE_STEPS,
  SURFACE_STYLES,
} from "./component-styles.gen.js";

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

/**
 * Merge a caller's `style` over a resolved default: set fields win.
 *
 * Mirrors `tempest_core.style.merge_style` — the caller's non-null fields
 * override, everything else keeps the resolved value. A `null` field in the
 * override means "not set", never "clear it", which is what keeps a partial
 * style from erasing a resolved background.
 *
 * @param {Object} base        The resolved default style.
 * @param {?Object} override   The caller's style, or null.
 * @returns {Object}           A full Style object.
 */
function mergeStyle(base, override) {
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
 * The resolved surface style for a variant/scheme/elevation, with its own radius.
 *
 * The generated table is keyed with `padding_step="none"` and
 * `radius_step="none"` so the two scale-driven fields can be applied here — the
 * core's resolver assigns both directly, so setting them after the lookup gives
 * the identical style while keeping the table 49× smaller.
 *
 * @param {string} variant      A `CardVariant` value.
 * @param {string} colorScheme  A Material 3 scheme name.
 * @param {?number} elevation   An explicit M3 level, or null for the default.
 * @param {string} radiusStep   The shape-scale step for the corner radius.
 * @returns {Object}            The resolved (sparse) style fields.
 */
function surfaceStyle(variant, colorScheme, elevation, radiusStep) {
  const level = elevation == null ? "default" : String(elevation);
  const base = SURFACE_STYLES[variant]?.[colorScheme]?.[level] ?? {};
  return { ...base, radius: SHAPE_STEPS[radiusStep] ?? 0.0 };
}

/**
 * `Card` — a themed, padded surface wrapping a column of children.
 *
 * Expands to the core's tree: a `Container` carrying the resolved surface style
 * (the `Surface` the core lowers to), wrapping a padded `Container` around a
 * gapped `Column`.
 *
 * @param {{children?: import("../transport.js").Node[], variant?: string,
 *          colorScheme?: string, elevation?: ?number, paddingStep?: string,
 *          radiusStep?: string, gapStep?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Card({
  children = [],
  variant = "elevated",
  colorScheme = "neutral",
  elevation = null,
  paddingStep = "md",
  radiusStep = "md",
  gapStep = "sm",
  style = null,
  key = null,
} = {}) {
  const inner = Container({
    key: "card-body",
    style: Style({ padding: Edge.all(SPACING_STEPS[paddingStep] ?? 0.0) }),
    child: Column({
      key: "card-col",
      style: Style({ gap: SPACING_STEPS[gapStep] ?? 0.0 }),
      children,
    }),
  });
  return Container({
    key: key ?? "card",
    style: mergeStyle(surfaceStyle(variant, colorScheme, elevation, radiusStep), style),
    child: inner,
  });
}

/**
 * `Divider` — a hairline rule across the available width.
 *
 * @param {{thickness?: number|string, colorScheme?: ?string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Divider({ thickness = 1.0, colorScheme = null, style = null, key = null } = {}) {
  const height = typeof thickness === "string" ? SPACING_STEPS[thickness] ?? 0.0 : thickness;
  const tinted = colorScheme != null && colorScheme !== "neutral";
  const color = tinted ? COLOR_ROLES[colorScheme] : COLOR_ROLES.outline_variant;
  return Container({
    key: key ?? "divider",
    style: mergeStyle({ height, background: color }, style),
  });
}

/**
 * `Chip` — a compact pill, clickable when it carries `onClick`.
 *
 * @param {{label?: string, selected?: boolean, onClick?: ?Function,
 *          colorScheme?: string, size?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Chip({
  label = "",
  selected = false,
  onClick = null,
  colorScheme = "primary",
  size = "md",
  style = null,
  key = null,
} = {}) {
  const variant = selected ? "solid" : "subtle";
  const pill = BADGE_STYLES[variant]?.[size]?.[colorScheme] ?? {};
  const merged = mergeStyle(pill, style);
  if (onClick != null) {
    return Button({ label, onClick, key: key ?? "chip", style: merged });
  }
  return Text({ content: label, key: key ?? "chip", style: merged });
}

/**
 * `SegmentedControl` — a row of segment buttons, the active one solid.
 *
 * @param {{options?: string[], selected?: number, onSelect?: ?Function,
 *          colorScheme?: string, size?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function SegmentedControl({
  options = [],
  selected = 0,
  onSelect = null,
  colorScheme = "primary",
  size = "sm",
  style = null,
  key = null,
} = {}) {
  const children = options.map((label, index) => {
    const variant = index === selected ? "solid" : "ghost";
    const segment = resolveWidgetStyle("Button", variant, size, colorScheme, null);
    return Button({
      label,
      key: `seg-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: mergeStyle(segment, { grow: 1.0 }),
    });
  });
  const base = {
    gap: SPACING_STEPS.xs,
    padding: Edge.all(SPACING_STEPS.xs),
    radius: SHAPE_STEPS.md,
    background: COLOR_ROLES.surface_variant,
  };
  return Row({ key: key ?? "segmented", style: mergeStyle(base, style), children });
}

/**
 * `AppBar` — a top bar: leading widget, growing title, trailing actions.
 *
 * @param {{title?: string, leading?: ?import("../transport.js").Node,
 *          actions?: import("../transport.js").Node[], variant?: string,
 *          colorScheme?: string, elevation?: ?number, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function AppBar({
  title = "",
  leading = null,
  actions = [],
  variant = "elevated",
  colorScheme = "neutral",
  elevation = null,
  style = null,
  key = null,
} = {}) {
  // `_bar_surface` overrides only the padding step; the radius keeps the
  // resolver's own default, so a bar carries the same corner as a card.
  const surface = surfaceStyle(variant, colorScheme, elevation, "md");
  const content = surface.color ?? COLOR_ROLES.on_surface;
  const children = [];
  if (leading != null) {
    children.push(leading);
  }
  children.push(
    Text({
      content: title,
      key: "appbar-title",
      style: Style({ grow: 1.0, font_size: 20.0, font_weight: 700, color: content }),
    }),
  );
  if (actions.length > 0) {
    children.push(Row({ key: "appbar-actions", style: Style({ gap: 8.0 }), children: actions }));
  }
  const base = {
    ...surface,
    padding: Edge.symmetric({ vertical: 14.0, horizontal: 16.0 }),
    gap: 12.0,
    align: "center",
  };
  return Row({ key: key ?? "appbar", style: mergeStyle(base, style), children });
}

/**
 * `RadioGroup` — one button per option, the chosen one marked.
 *
 * @param {{options?: string[], selected?: number, onSelect?: ?Function,
 *          size?: string, colorScheme?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function RadioGroup({
  options = [],
  selected = 0,
  onSelect = null,
  size = "md",
  colorScheme = "primary",
  style = null,
  key = null,
} = {}) {
  const surface = COLOR_ROLES.surface;
  const children = options.map((label, index) => {
    const chosen = index === selected;
    const state = chosen ? "checked" : "unchecked";
    const accent = SELECTION_ACCENT[size]?.[colorScheme]?.[state] ?? null;
    const marker = chosen && accent != null ? accent : COLOR_ROLES.on_surface_variant;
    return Button({
      label: `${chosen ? "\u25c9" : "\u25cb"}  ${label}`,
      key: `radio-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: Style({
        padding: Edge.symmetric({ vertical: 10.0, horizontal: 14.0 }),
        radius: SHAPE_STEPS.sm,
        background: surface,
        color: marker,
      }),
    });
  });
  return Column({
    key: key ?? "radiogroup",
    style: mergeStyle({ gap: SPACING_STEPS.sm }, style),
    children,
  });
}

/**
 * `Scaffold` — app bar, growing body and bottom bar stacked in a column.
 *
 * @param {{appBar?: ?import("../transport.js").Node,
 *          body?: ?import("../transport.js").Node,
 *          bottomBar?: ?import("../transport.js").Node, scroll?: boolean,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Scaffold({
  appBar = null,
  body = null,
  bottomBar = null,
  scroll = false,
  style = null,
  key = null,
} = {}) {
  const children = [];
  if (appBar != null) {
    children.push(appBar);
  }
  const content = body ?? Column({});
  children.push(
    scroll
      ? ScrollView({ key: "scaffold-body", style: Style({ grow: 1.0 }), children: [content] })
      : Container({ key: "scaffold-body", style: Style({ grow: 1.0 }), child: content }),
  );
  if (bottomBar != null) {
    children.push(bottomBar);
  }
  const base = { gap: 0.0, background: COLOR_ROLES.background };
  return Column({ key: key ?? "scaffold", style: mergeStyle(base, style), children });
}
