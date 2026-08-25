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
// Still out of scope: the components whose *tree shape* depends on the data they
// are handed (DataTable, Table, the charts, the date/media pickers,
// DetectionOverlay, ResultView) — one row of cells per record, one bar per
// datum. A component that merely loops over a flat list of labels or widgets
// (Tabs, Accordion, SegmentedControl) is a fixed composition and ports fine.
// Compose the rest from primitives, or use Modes A/B. See
// docs/advanced/transpile.md.

import {
  Button,
  Column,
  Container,
  IconButton,
  Input,
  MaskedInput,
  Row,
  ScrollView,
  Text,
} from "./widgets.gen.js";
import { EMAIL_PATTERN } from "./validators.js";
import { SPACING_STEPS } from "./spacing.gen.js";
import {
  Color,
  Edge,
  Style,
  colorRoles,
  modeTable,
  resolveWidgetStyle,
} from "./widget-support.js";
import { Border, SideBorder } from "./values.gen.js";
import {
  ALERT_STYLES,
  AVATAR_COLORS,
  BADGE_STYLES,
  COLOR_ROLES,
  FIELD_STYLES,
  SELECTION_ACCENT,
  SHAPE_STEPS,
  SURFACE_STYLES,
  TYPOGRAPHY,
} from "./component-styles.gen.js";

/**
 * The legacy status tones `Banner`/`Badge` accept, which double as scheme names.
 * @type {ReadonlySet<string>}
 */
const TONE_SCHEMES = new Set(["info", "success", "warning", "error"]);

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
export function HStack({ children = [], gap = "md", align = "center", justify = null, key = null, theme = null } = {}) {
  return Row({
    key,
    children,
    style: Style({ gap: resolveGap(gap), align, justify }), theme });
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
export function VStack({ children = [], gap = "md", align = null, justify = null, key = null, theme = null } = {}) {
  return Column({
    key,
    children,
    style: Style({ gap: resolveGap(gap), align, justify }), theme });
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
function surfaceStyle(variant, colorScheme, elevation, radiusStep, theme) {
  const level = elevation == null ? "default" : String(elevation);
  const base = modeTable(SURFACE_STYLES, theme)[variant]?.[colorScheme]?.[level] ?? {};
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
  theme = null,
} = {}) {
  const base = key ?? "card";
  const inner = Container({
    key: `${base}-body`,
    style: Style({ padding: Edge.all(SPACING_STEPS[paddingStep] ?? 0.0) }),
    child: Column({
      key: `${base}-col`,
      style: Style({ gap: SPACING_STEPS[gapStep] ?? 0.0 }),
      children, theme }),
  });
  return Container({
    key: base,
    style: mergeStyle(surfaceStyle(variant, colorScheme, elevation, radiusStep, theme), style),
    child: inner, theme });
}

/**
 * `Divider` — a hairline rule across the available width.
 *
 * @param {{thickness?: number|string, colorScheme?: ?string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Divider({ thickness = 1.0, colorScheme = null, style = null, key = null, theme = null } = {}) {
  const height = typeof thickness === "string" ? SPACING_STEPS[thickness] ?? 0.0 : thickness;
  const tinted = colorScheme != null && colorScheme !== "neutral";
  const color = tinted ? colorRoles(theme)[colorScheme] : colorRoles(theme).outline_variant;
  return Container({
    key: key ?? "divider",
    style: mergeStyle({ height, background: color }, style), theme });
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
  theme = null,
} = {}) {
  const variant = selected ? "solid" : "subtle";
  const pill = modeTable(BADGE_STYLES, theme)[variant]?.[size]?.[colorScheme] ?? {};
  const merged = mergeStyle(pill, style);
  if (onClick != null) {
    return Button({ label, onClick, key: key ?? "chip", style: merged, theme });
  }
  return Text({ content: label, key: key ?? "chip", style: merged, theme });
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
  theme = null,
} = {}) {
  const base = key ?? "segmented";
  const children = options.map((label, index) => {
    const variant = index === selected ? "solid" : "ghost";
    const segment = resolveWidgetStyle("Button", variant, size, colorScheme, null, theme);
    return Button({
      label,
      key: `${base}-item-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: mergeStyle(segment, { grow: 1.0 }), theme });
  });
  const strip = {
    gap: SPACING_STEPS.xs,
    padding: Edge.all(SPACING_STEPS.xs),
    radius: SHAPE_STEPS.md,
    background: colorRoles(theme).surface_variant,
  };
  return Row({ key: base, style: mergeStyle(strip, style), children, theme });
}

/**
 * `AppBar` — a top bar: leading widget, growing title, trailing actions.
 *
 * The bar overrides only the padding step of the resolved surface; the radius
 * keeps the resolver's own default, so a bar carries the same corner as a card.
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
  theme = null,
} = {}) {
  const base = key ?? "appbar";
  const surface = surfaceStyle(variant, colorScheme, elevation, "md", theme);
  const content = surface.color ?? colorRoles(theme).on_surface;
  const children = [];
  if (leading != null) {
    children.push(leading);
  }
  children.push(
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({ grow: 1.0, font_size: 20.0, font_weight: 700, color: content }), theme }),
  );
  if (actions.length > 0) {
    children.push(
      Row({ key: `${base}-actions`, style: Style({ gap: 8.0 }), children: actions, theme }),
    );
  }
  const bar = {
    ...surface,
    padding: Edge.symmetric({ vertical: 14.0, horizontal: 16.0 }),
    gap: 12.0,
    align: "center",
  };
  return Row({ key: base, style: mergeStyle(bar, style), children, theme });
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
  theme = null,
} = {}) {
  const base = key ?? "radiogroup";
  const surface = colorRoles(theme).surface;
  const children = options.map((label, index) => {
    const chosen = index === selected;
    const state = chosen ? "checked" : "unchecked";
    const accent = modeTable(SELECTION_ACCENT, theme)[size]?.[colorScheme]?.[state] ?? null;
    const marker = chosen && accent != null ? accent : colorRoles(theme).on_surface_variant;
    return Button({
      label: `${chosen ? "\u25c9" : "\u25cb"}  ${label}`,
      key: `${base}-item-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: Style({
        padding: Edge.symmetric({ vertical: 10.0, horizontal: 14.0 }),
        radius: SHAPE_STEPS.sm,
        background: surface,
        color: marker,
      }), theme });
  });
  return Column({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.sm }, style),
    children, theme });
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
  theme = null,
} = {}) {
  const base = key ?? "scaffold";
  const children = [];
  if (appBar != null) {
    children.push(appBar);
  }
  const content = body ?? Column({ theme });
  children.push(
    scroll
      ? ScrollView({ key: `${base}-body`, style: Style({ grow: 1.0 }), children: [content], theme })
      : Container({ key: `${base}-body`, style: Style({ grow: 1.0 }), child: content, theme }),
  );
  if (bottomBar != null) {
    children.push(bottomBar);
  }
  const shell = { gap: 0.0, background: colorRoles(theme).background };
  return Column({ key: base, style: mergeStyle(shell, style), children, theme });
}

/**
 * `Surface` — the themed, un-padded box every higher-level surface builds on.
 *
 * Carries the resolved surface style and nothing else: no inner padding, no gap.
 * `Card` is exactly this plus padding and a `Column`.
 *
 * @param {{child?: ?import("../transport.js").Node, variant?: string,
 *          colorScheme?: string, elevation?: ?number, radiusStep?: string,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Surface({
  child = null,
  variant = "elevated",
  colorScheme = "neutral",
  elevation = null,
  radiusStep = "md",
  style = null,
  key = null,
  theme = null,
} = {}) {
  return Container({
    key: key ?? "surface",
    style: mergeStyle(surfaceStyle(variant, colorScheme, elevation, radiusStep, theme), style),
    child, theme });
}

/**
 * `StyledContainer` — a `Container` whose padding is a spacing-token step.
 *
 * A raw number passes through as logical pixels; a step name (`"md"`) resolves
 * against the theme's spacing scale.
 *
 * @param {{child?: ?import("../transport.js").Node, padding?: number|string,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function StyledContainer({ child = null, padding = "md", style = null, key = null, theme = null } = {}) {
  const amount = typeof padding === "string" ? SPACING_STEPS[padding] ?? 0.0 : padding;
  return Container({
    key: key ?? "styled-container",
    style: mergeStyle({ padding: Edge.all(amount) }, style),
    child, theme });
}

/**
 * `Grid` — children laid out in equal-width cells, `columns` per row.
 *
 * Each child is wrapped in a growing `Container` so the columns share the width,
 * and a short final row is padded with empty cells to keep the alignment.
 *
 * @param {{children?: import("../transport.js").Node[], columns?: number,
 *          gap?: number|string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Grid({ children = [], columns = 2, gap = 8.0, style = null, key = null, theme = null } = {}) {
  const base = key ?? "grid";
  const perRow = Math.max(1, columns);
  const space = typeof gap === "string" ? SPACING_STEPS[gap] ?? 0.0 : gap;
  const rows = [];
  for (let start = 0; start < children.length; start += perRow) {
    const chunk = children.slice(start, start + perRow);
    const cells = chunk.map((child, offset) =>
      Container({ key: `${base}-cell-${start + offset}`, style: Style({ grow: 1.0 }), child, theme }),
    );
    for (let pad = chunk.length; pad < perRow; pad += 1) {
      cells.push(
        Container({ key: `${base}-cell-pad-${start}-${pad}`, style: Style({ grow: 1.0 }), theme }),
      );
    }
    rows.push(
      Row({ key: `${base}-row-${start}`, style: Style({ gap: space }), children: cells, theme }),
    );
  }
  return Column({
    key: base,
    style: mergeStyle({ gap: space }, style),
    children: rows, theme });
}

/**
 * A fixed-width lateral panel over a resolved surface — the `Sidebar`/`Drawer` body.
 *
 * @param {string} key           The node key.
 * @param {import("../transport.js").Node[]} children  The stacked children.
 * @param {number} width         The panel width in logical pixels.
 * @param {string} variant       A `CardVariant` value.
 * @param {string} colorScheme   A Material 3 scheme name.
 * @param {?number} elevation    An explicit M3 level, or null for the default.
 * @param {?Object} style        The caller's style override.
 * @returns {import("../transport.js").Node}
 */
function lateralPanel(key, children, width, variant, colorScheme, elevation, style, theme) {
  const frame = {
    ...surfaceStyle(variant, colorScheme, elevation, "md", theme),
    width,
    padding: Edge.all(16.0),
    gap: 10.0,
  };
  return Column({ key, style: mergeStyle(frame, style), children, theme });
}

/**
 * `Sidebar` — a fixed-width lateral column of navigation or content widgets.
 *
 * @param {{children?: import("../transport.js").Node[], width?: number,
 *          variant?: string, colorScheme?: string, elevation?: ?number,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Sidebar({
  children = [],
  width = 240.0,
  variant = "elevated",
  colorScheme = "neutral",
  elevation = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  return lateralPanel(key ?? "sidebar", children, width, variant, colorScheme, elevation, style, theme);
}

/**
 * `Drawer` — a controlled lateral panel that shows its children when `open`.
 *
 * Closed, it collapses to an empty `Container` — the same node the core emits, so
 * the reconciler sees a prop change rather than a replaced subtree.
 *
 * @param {{open?: boolean, children?: import("../transport.js").Node[],
 *          width?: number, variant?: string, colorScheme?: string,
 *          elevation?: ?number, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Drawer({
  open = false,
  children = [],
  width = 260.0,
  variant = "elevated",
  colorScheme = "neutral",
  elevation = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  if (!open) {
    return Container({ key: key ?? "drawer", theme });
  }
  return lateralPanel(key ?? "drawer", children, width, variant, colorScheme, elevation, style, theme);
}

/**
 * `Burger` — the hamburger menu button.
 *
 * Lowers to an `IconButton` carrying the curated `menu` glyph in the `ghost`
 * variant, with `"menu"` as its accessible label. The core's deprecated `glyph`
 * prop is not surfaced: it no longer changes what is drawn.
 *
 * @param {{onClick?: ?Function, variant?: string, colorScheme?: string,
 *          size?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Burger({
  onClick = null,
  variant = "ghost",
  colorScheme = "neutral",
  size = "md",
  style = null,
  key = null,
  theme = null,
} = {}) {
  return IconButton({
    icon: "menu",
    label: "menu",
    onClick,
    variant,
    colorScheme,
    size,
    key: key ?? "burger",
    style, theme });
}

/**
 * `Header` — a flat page-header band: a title with an optional subtitle.
 *
 * A header is a band, not a surface: it fills with the `surface_variant` role and
 * takes no `variant`/elevation. A `colorScheme` other than `"neutral"` tints the
 * title with that role.
 *
 * @param {{title?: string, subtitle?: ?string, colorScheme?: ?string,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Header({ title = "", subtitle = null, colorScheme = null, style = null, key = null, theme = null } = {}) {
  const base = key ?? "header";
  const titleColor =
    colorScheme != null && colorScheme !== "neutral"
      ? colorRoles(theme)[colorScheme]
      : colorRoles(theme).on_surface;
  const children = [
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({
        font_size: TYPOGRAPHY.headline_small.font_size,
        font_weight: 700,
        color: titleColor,
      }), theme }),
  ];
  if (subtitle != null) {
    children.push(
      Text({
        content: subtitle,
        key: `${base}-subtitle`,
        style: Style({
          font_size: TYPOGRAPHY.body_medium.font_size,
          color: colorRoles(theme).on_surface_variant,
        }), theme }),
    );
  }
  const chrome = {
    padding: Edge.all(SPACING_STEPS.lg),
    gap: SPACING_STEPS.xs,
    background: colorRoles(theme).surface_variant,
  };
  return Column({ key: base, style: mergeStyle(chrome, style), children, theme });
}

/**
 * `Footer` — a bottom bar holding arbitrary, centered content.
 *
 * Carries the same resolved surface as an `AppBar`, with the bar's own padding.
 *
 * @param {{children?: import("../transport.js").Node[], variant?: string,
 *          colorScheme?: string, elevation?: ?number, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Footer({
  children = [],
  variant = "elevated",
  colorScheme = "neutral",
  elevation = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = {
    ...surfaceStyle(variant, colorScheme, elevation, "md", theme),
    padding: Edge.symmetric({ vertical: 12.0, horizontal: 16.0 }),
    gap: 12.0,
    align: "center",
  };
  return Row({ key: key ?? "footer", style: mergeStyle(base, style), children, theme });
}

/**
 * `NavBar` — a horizontal navigation bar with the active item as an accent pill.
 *
 * The active item takes the `solid` badge treatment in `colorScheme`; the others
 * take a neutral `ghost` button treatment. Every item grows, so they share the
 * bar's width.
 *
 * @param {{items?: string[], active?: number, onSelect?: ?Function,
 *          colorScheme?: string, size?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function NavBar({
  items = [],
  active = 0,
  onSelect = null,
  colorScheme = "primary",
  size = "md",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "navbar";
  const children = items.map((label, index) => {
    const itemStyle =
      index === active
        ? modeTable(BADGE_STYLES, theme).solid?.[size]?.[colorScheme] ?? {}
        : resolveWidgetStyle("Button", "ghost", size, "neutral", null, theme);
    return Button({
      label,
      key: `${base}-item-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: mergeStyle(itemStyle, { grow: 1.0 }), theme });
  });
  const bar = {
    ...surfaceStyle("filled", "neutral", null, "md", theme),
    gap: 8.0,
    padding: Edge.all(8.0),
    justify: "center",
  };
  return Row({ key: base, style: mergeStyle(bar, style), children, theme });
}

/**
 * `Breadcrumb` — a path trail of crumbs joined by a separator.
 *
 * A crumb is a `link`-styled `Button` while `onSelect` is set, except the last
 * one: the current crumb is never tappable, and reads bold in `on_surface`.
 *
 * @param {{items?: string[], separator?: string, onSelect?: ?Function,
 *          colorScheme?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Breadcrumb({
  items = [],
  separator = "/",
  onSelect = null,
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "breadcrumb";
  const children = [];
  items.forEach((label, index) => {
    if (index) {
      children.push(
        Text({
          content: separator,
          key: `${base}-sep-${index}`,
          style: Style({ color: colorRoles(theme).on_surface_variant, font_size: 14.0 }), theme }),
      );
    }
    const isLast = index === items.length - 1;
    if (onSelect != null && !isLast) {
      children.push(
        Button({
          label,
          key: `${base}-item-${index}`,
          onClick: () => onSelect(index),
          style: resolveWidgetStyle("Button", "link", "sm", colorScheme, null, theme), theme }),
      );
      return;
    }
    children.push(
      Text({
        content: label,
        key: `${base}-item-${index}`,
        style: Style({
          color: isLast ? colorRoles(theme).on_surface : colorRoles(theme).on_surface_variant,
          font_size: 14.0,
          font_weight: isLast ? 700 : 400,
        }), theme }),
    );
  });
  return Row({
    key: base,
    style: mergeStyle({ gap: 6.0, align: "center" }, style),
    children, theme });
}

/**
 * `ListTile` — a list row: optional leading/trailing widgets around a title block.
 *
 * Presentational by design: the primitive set only taps on a `Button`, so an
 * actionable row puts one in `trailing`.
 *
 * @param {{title?: string, subtitle?: ?string,
 *          leading?: ?import("../transport.js").Node,
 *          trailing?: ?import("../transport.js").Node, colorScheme?: ?string,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function ListTile({
  title = "",
  subtitle = null,
  leading = null,
  trailing = null,
  colorScheme = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "listtile";
  const titleColor =
    colorScheme != null && colorScheme !== "neutral"
      ? colorRoles(theme)[colorScheme]
      : colorRoles(theme).on_surface;
  const textChildren = [
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({
        font_size: TYPOGRAPHY.body_large.font_size,
        font_weight: TYPOGRAPHY.body_large.font_weight,
        color: titleColor,
      }), theme }),
  ];
  if (subtitle != null) {
    textChildren.push(
      Text({
        content: subtitle,
        key: `${base}-subtitle`,
        style: Style({
          font_size: TYPOGRAPHY.body_small.font_size,
          color: colorRoles(theme).on_surface_variant,
        }), theme }),
    );
  }
  const children = [];
  if (leading != null) {
    children.push(leading);
  }
  children.push(
    Column({
      key: `${base}-text`,
      style: Style({ grow: 1.0, gap: SPACING_STEPS.xs }),
      children: textChildren, theme }),
  );
  if (trailing != null) {
    children.push(trailing);
  }
  const tile = {
    gap: SPACING_STEPS.sm,
    align: "center",
    padding: Edge.symmetric({ vertical: SPACING_STEPS.sm, horizontal: SPACING_STEPS.md }),
  };
  return Row({ key: base, style: mergeStyle(tile, style), children, theme });
}

/**
 * `Avatar` — a round badge showing short initials.
 *
 * The circle fills with the scheme's tonal `*_container` role and the initials
 * take its legible `on_*_container` pair, so the contrast holds by construction.
 *
 * @param {{initials?: string, size?: number, colorScheme?: string,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Avatar({ initials = "", size = 40.0, colorScheme = "primary", style = null, key = null, theme = null } = {}) {
  const base = key ?? "avatar";
  const pair = modeTable(AVATAR_COLORS, theme)[colorScheme] ?? modeTable(AVATAR_COLORS, theme).primary;
  const disc = {
    width: size,
    height: size,
    radius: size / 2.0,
    background: pair.background,
    align: "center",
  };
  return Container({
    key: base,
    style: mergeStyle(disc, style),
    child: Text({
      content: initials,
      key: `${base}-text`,
      style: Style({ color: pair.color, font_weight: 700, text_align: "center" }), theme }), theme });
}

/**
 * `Tag` — a read-only label: a `Chip` fixed to its static, low-emphasis form.
 *
 * The core models it as a `Chip` subclass whose `selected`/`on_click` fields are
 * frozen, so it always lowers to a `subtle` badge pill. Kept as its own export
 * because app code imports the name; it delegates rather than restating the pill.
 *
 * @param {{label?: string, colorScheme?: string, size?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Tag({ label = "", colorScheme = "primary", size = "md", style = null, key = null, theme = null } = {}) {
  return Chip({ label, colorScheme, size, style, key, theme });
}

/**
 * `Rating` — a row of stars showing, and optionally setting, a 1-based rating.
 *
 * With `onRate` set every star is a tappable `ghost` button with an explicitly
 * transparent fill, so the glyph reads as a bare star instead of a filled pill.
 *
 * @param {{value?: number, maxStars?: number, onRate?: ?Function,
 *          colorScheme?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Rating({
  value = 0,
  maxStars = 5,
  onRate = null,
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "rating";
  const color = colorRoles(theme)[colorScheme];
  const children = [];
  for (let index = 0; index < maxStars; index += 1) {
    const glyph = index < value ? "★" : "☆";
    if (onRate != null) {
      children.push(
        Button({
          label: glyph,
          key: `${base}-star-${index}`,
          variant: "ghost",
          onClick: () => onRate(index + 1),
          style: Style({ font_size: 24.0, color, background: Color({ a: 0.0 }) }), theme }),
      );
    } else {
      children.push(
        Text({
          content: glyph,
          key: `${base}-star-${index}`,
          style: Style({ font_size: 24.0, color }), theme }),
      );
    }
  }
  return Row({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.xs }, style),
    children, theme });
}

/**
 * `Stepper` — a numeric spinner: `-` decrement, current value, `+` increment.
 *
 * Each button reports the value already clamped to `minValue`/`maxValue`, so the
 * app never has to re-check the bounds it declared.
 *
 * Themed since core 0.16.0 (tempestweb#158): both buttons resolve from
 * `variant`/`colorScheme`/`size` and the value reads the theme's `on_surface`
 * role. Before that the port carried the same fixed dark constants the core did,
 * so a stepper on a light app painted a dark-grey button.
 *
 * @param {{value?: number, step?: number, minValue?: ?number,
 *          maxValue?: ?number, onChange?: ?Function, variant?: string,
 *          colorScheme?: string, size?: string, style?: ?Object,
 *          key?: ?string, theme?: ?Object}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Stepper({
  value = 0,
  step = 1,
  minValue = null,
  maxValue = null,
  onChange = null,
  variant = "solid",
  colorScheme = "neutral",
  size = "md",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "stepper";
  const clamped = (candidate) => {
    if (minValue != null && candidate < minValue) {
      return minValue;
    }
    if (maxValue != null && candidate > maxValue) {
      return maxValue;
    }
    return candidate;
  };
  const resolved = mergeStyle(
    resolveWidgetStyle("Button", variant, size, colorScheme, null, theme),
    { font_size: 18.0 },
  );
  const button = (label, delta, buttonKey) =>
    Button({
      label,
      key: buttonKey,
      onClick: onChange == null ? null : () => onChange(clamped(value + delta)),
      style: resolved, theme });
  return Row({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.sm, align: "center" }, style),
    children: [
      button("-", -step, `${base}-down`),
      Text({
        content: String(value),
        key: `${base}-value`,
        style: Style({
          font_size: 18.0,
          font_weight: 700,
          color: colorRoles(theme).on_surface,
        }), theme }),
      button("+", step, `${base}-up`),
    ], theme });
}

/**
 * `SearchBar` — a search field: a controlled `Input` in a surface pill.
 *
 * The clear button appears only when `onClear` is set *and* the query is
 * non-empty, matching the core: an empty field has nothing to clear.
 *
 * @param {{value?: string, placeholder?: string, onChange?: ?Function,
 *          onClear?: ?Function, fieldVariant?: string, colorScheme?: string,
 *          size?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function SearchBar({
  value = "",
  placeholder = "Search",
  onChange = null,
  onClear = null,
  fieldVariant = "filled",
  colorScheme = "neutral",
  size = "md",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "searchbar";
  const field = modeTable(FIELD_STYLES, theme)[fieldVariant]?.[size]?.[colorScheme] ?? {};
  const children = [
    Input({
      value,
      placeholder,
      onChange,
      key: `${base}-input`,
      style: mergeStyle(field, { grow: 1.0 }) }),
  ];
  if (onClear != null && value) {
    children.push(
      IconButton({
        icon: "x",
        label: "clear",
        onClick: onClear,
        variant: "ghost",
        colorScheme,
        size,
        key: `${base}-clear`, theme }),
    );
  }
  const box = {
    ...surfaceStyle("filled", colorScheme, null, "lg", theme),
    gap: 8.0,
    align: "center",
    padding: Edge.all(8.0),
  };
  return Row({ key: base, style: mergeStyle(box, style), children, theme });
}

/**
 * Map the legacy `tone` prop onto a Material 3 color scheme.
 *
 * `Banner`/`Badge` predate the scheme axis and still accept `tone`; an unknown
 * tone falls back to `"info"`, as the core does.
 *
 * @param {string} tone  One of `"info"`/`"success"`/`"warning"`/`"error"`.
 * @returns {string}  The matching scheme name.
 */
function toneScheme(tone) {
  return TONE_SCHEMES.has(tone) ? tone : "info";
}

/**
 * `Banner` — an inline status bar with a message and an optional trailing action.
 *
 * @param {{message?: string, tone?: string, colorScheme?: ?string,
 *          variant?: string, action?: ?import("../transport.js").Node,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Banner({
  message = "",
  tone = "info",
  colorScheme = null,
  variant = "subtle",
  action = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "banner";
  const scheme = colorScheme ?? toneScheme(tone);
  const resolved = modeTable(ALERT_STYLES, theme)[variant]?.[scheme] ?? {};
  const children = [
    Text({
      content: message,
      key: `${base}-text`,
      style: Style({ grow: 1.0, color: resolved.color ?? null, font_size: 14.0 }), theme }),
  ];
  if (action != null) {
    children.push(action);
  }
  const strip = { ...resolved, gap: 12.0, align: "center" };
  return Row({ key: base, style: mergeStyle(strip, style), children, theme });
}

/**
 * `Alert` — a block status callout: optional glyph, title, body and dismiss.
 *
 * The richer sibling of `Banner`, over the same resolved alert block. Use
 * `variant: "left_accent"` for the classic accented-edge callout.
 *
 * @param {{title?: string, body?: ?string, glyph?: ?string,
 *          colorScheme?: string, variant?: string,
 *          dismiss?: ?import("../transport.js").Node, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Alert({
  title = "",
  body = null,
  glyph = null,
  colorScheme = "info",
  variant = "subtle",
  dismiss = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "alert";
  const resolved = modeTable(ALERT_STYLES, theme)[variant]?.[colorScheme] ?? {};
  const content = resolved.color ?? null;
  const columnChildren = [
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({ color: content, font_size: 15.0, font_weight: 700 }), theme }),
  ];
  if (body != null) {
    columnChildren.push(
      Text({
        content: body,
        key: `${base}-body`,
        style: Style({ color: content, font_size: 13.0 }), theme }),
    );
  }
  const children = [];
  if (glyph != null) {
    children.push(
      Text({
        content: glyph,
        key: `${base}-glyph`,
        style: Style({ color: content, font_size: 20.0 }), theme }),
    );
  }
  children.push(
    Column({
      key: `${base}-col`,
      style: Style({ grow: 1.0, gap: SPACING_STEPS.xs }),
      children: columnChildren, theme }),
  );
  if (dismiss != null) {
    children.push(dismiss);
  }
  const block = { ...resolved, gap: SPACING_STEPS.sm, align: "center" };
  return Row({ key: base, style: mergeStyle(block, style), children, theme });
}

/**
 * `Badge` — a small inline status pill (a count or a short label).
 *
 * @param {{label?: string, tone?: string, colorScheme?: ?string,
 *          variant?: string, size?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Badge({
  label = "",
  tone = "error",
  colorScheme = null,
  variant = "solid",
  size = "sm",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const scheme = colorScheme ?? toneScheme(tone);
  const pill = modeTable(BADGE_STYLES, theme)[variant]?.[size]?.[scheme] ?? {};
  return Text({
    content: label,
    key: key ?? "badge",
    style: mergeStyle({ ...pill, text_align: "center" }, style), theme });
}

/**
 * `EmptyState` — a centered placeholder: glyph, title, subtitle, action.
 *
 * @param {{title?: string, subtitle?: ?string, glyph?: string,
 *          action?: ?import("../transport.js").Node, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function EmptyState({
  title = "",
  subtitle = null,
  glyph = "○",
  action = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "emptystate";
  const muted = colorRoles(theme).on_surface_variant;
  const children = [
    Text({
      content: glyph,
      key: `${base}-glyph`,
      style: Style({ font_size: 48.0, color: muted, text_align: "center" }), theme }),
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({
        font_size: 18.0,
        font_weight: 700,
        color: colorRoles(theme).on_surface,
        text_align: "center",
      }), theme }),
  ];
  if (subtitle != null) {
    children.push(
      Text({
        content: subtitle,
        key: `${base}-subtitle`,
        style: Style({ font_size: 14.0, color: muted, text_align: "center" }), theme }),
    );
  }
  if (action != null) {
    children.push(action);
  }
  const frame = {
    gap: SPACING_STEPS.sm,
    align: "center",
    padding: Edge.all(SPACING_STEPS.lg),
  };
  return Column({ key: base, style: mergeStyle(frame, style), children, theme });
}

/**
 * `Stat` — a labelled metric with a value and an optional trend delta.
 *
 * The delta is tinted by the `success`/`error` status role and prefixed with the
 * canonical ▲/▼ cue, following `deltaUp`.
 *
 * @param {{label?: string, value?: string, delta?: ?string, deltaUp?: boolean,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Stat({ label = "", value = "", delta = null, deltaUp = true, style = null, key = null, theme = null } = {}) {
  const base = key ?? "stat";
  const children = [
    Text({
      content: label,
      key: `${base}-label`,
      style: Style({ color: colorRoles(theme).on_surface_variant, font_size: 13.0 }), theme }),
    Text({
      content: value,
      key: `${base}-value`,
      style: Style({ color: colorRoles(theme).on_surface, font_size: 28.0, font_weight: 700 }), theme }),
  ];
  if (delta != null) {
    children.push(
      Text({
        content: `${deltaUp ? "▲" : "▼"} ${delta}`,
        key: `${base}-delta`,
        style: Style({
          color: deltaUp ? colorRoles(theme).success : colorRoles(theme).error,
          font_size: 13.0,
          font_weight: 500,
        }), theme }),
    );
  }
  return Column({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.xs }, style),
    children, theme });
}

/**
 * One `ProgressStepper` cell: a numbered disc above its label.
 *
 * A done or active step paints a filled accent disc; a pending one an outlined,
 * muted disc — which is the whole visual cue the stepper carries.
 *
 * @param {number} index        The zero-based step position.
 * @param {string} label        The step's caption.
 * @param {number} current      The active step index.
 * @param {string} colorScheme  A Material 3 scheme name.
 * @param {string} base         The stepper's key, which the cell's hangs off.
 * @returns {import("../transport.js").Node}
 */
function stepCell(index, label, current, colorScheme, base, theme) {
  const doneOrActive = index <= current;
  const muted = colorRoles(theme).on_surface_variant;
  const disc = doneOrActive
    ? Style({
        width: 28.0,
        height: 28.0,
        radius: 14.0,
        background: colorRoles(theme)[colorScheme],
        color: colorRoles(theme)[`on_${colorScheme}`],
        align: "center",
        text_align: "center",
        font_weight: 700,
        font_size: 13.0,
      })
    : Style({
        width: 28.0,
        height: 28.0,
        radius: 14.0,
        border: { width: 1.0, color: colorRoles(theme).outline },
        color: muted,
        align: "center",
        text_align: "center",
        font_size: 13.0,
      });
  return Column({
    key: `${base}-step-${index}`,
    style: Style({ gap: SPACING_STEPS.xs, align: "center" }),
    children: [
      Text({ content: String(index + 1), key: `${base}-step-disc-${index}`, style: disc, theme }),
      Text({
        content: label,
        key: `${base}-step-label-${index}`,
        style: Style({
          color: doneOrActive ? colorRoles(theme).on_surface : muted,
          font_size: 12.0,
        }), theme }),
    ], theme });
}

/**
 * `ProgressStepper` — a horizontal wizard showing labelled, numbered steps.
 *
 * Named for the core's own split: this is the progress trail, while `Stepper` is
 * the numeric +/- spinner.
 *
 * @param {{steps?: string[], current?: number, colorScheme?: string,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function ProgressStepper({
  steps = [],
  current = 0,
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "progress-stepper";
  const children = [];
  steps.forEach((label, index) => {
    if (index > 0) {
      children.push(
        Text({
          content: "",
          key: `${base}-step-conn-${index}`,
          style: Style({
            grow: 1.0,
            height: 2.0,
            background:
              index <= current ? colorRoles(theme)[colorScheme] : colorRoles(theme).outline_variant,
          }), theme }),
      );
    }
    children.push(stepCell(index, label, current, colorScheme, base, theme));
  });
  return Row({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.xs, align: "center" }, style),
    children, theme });
}

/**
 * `MetricCard` — a dashboard metric inside a themed card.
 *
 * `Card` + `Stat`, with an optional trailing slot (a sparkline, an icon) laid
 * beside the stat block. No new primitive is introduced.
 *
 * @param {{label?: string, value?: string, delta?: ?string, deltaUp?: boolean,
 *          colorScheme?: string, variant?: string,
 *          trailing?: ?import("../transport.js").Node, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function MetricCard({
  label = "",
  value = "",
  delta = null,
  deltaUp = true,
  colorScheme = "neutral",
  variant = "elevated",
  trailing = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "metric-card";
  const stat = Stat({
    label,
    value,
    delta,
    deltaUp,
    key: `${base}-stat`,
    style: Style({ grow: 1.0 }), theme });
  const body =
    trailing == null
      ? stat
      : Row({
          key: `${base}-row`,
          style: Style({ gap: SPACING_STEPS.md, align: "center" }),
          children: [stat, trailing], theme });
  return Card({
    key: base,
    variant,
    colorScheme,
    style,
    children: [body], theme });
}

/**
 * `StatCard` — a compact preset of `MetricCard` (a `filled` card).
 *
 * @param {{label?: string, value?: string, delta?: ?string, deltaUp?: boolean,
 *          colorScheme?: string, variant?: string,
 *          trailing?: ?import("../transport.js").Node, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function StatCard({
  label = "",
  value = "",
  delta = null,
  deltaUp = true,
  colorScheme = "neutral",
  variant = "filled",
  trailing = null,
  style = null,
  key = null,
  theme = null,
} = {}) {
  return MetricCard({
    label,
    value,
    delta,
    deltaUp,
    colorScheme,
    variant,
    trailing,
    style,
    key: key ?? "stat-card", theme });
}

/**
 * Map a confidence score to a status color scheme.
 *
 * The traffic-light cue every confidence-driven component shares: at or above
 * `high` reads `"success"`, at or above `mid` reads `"warning"`, below `mid`
 * reads `"error"`.
 *
 * @param {number} conf  The confidence score, typically in `[0, 1]`.
 * @param {{high?: number, mid?: number}} [thresholds]
 * @returns {string}  One of `"success"`/`"warning"`/`"error"`.
 */
export function confidence_scheme(conf, { high = 0.8, mid = 0.5 } = {}) {
  if (conf >= high) {
    return "success";
  }
  if (conf >= mid) {
    return "warning";
  }
  return "error";
}

/**
 * `ConfidenceBadge` — a status pill showing a model's confidence.
 *
 * A `subtle` `Badge` whose scheme comes from {@link confidence_scheme} and whose
 * label is the rounded percentage, optionally prefixed with a class name. The
 * percentage is formatted the way the transpiler renders Python's `.0%` spec, so
 * a hand-built badge and a transpiled f-string agree.
 *
 * @param {{confidence?: number, label?: string, high?: number, mid?: number,
 *          style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function ConfidenceBadge({
  confidence = 0.0,
  label = "",
  high = 0.8,
  mid = 0.5,
  style = null,
  key = null,
  theme = null,
} = {}) {
  const percent = `${(confidence * 100).toFixed(0)}%`;
  return Badge({
    key: key ?? "confidence-badge",
    label: label ? `${label} ${percent}`.trim() : percent,
    colorScheme: confidence_scheme(confidence, { high, mid }),
    variant: "subtle",
    style, theme });
}

/**
 * `Accordion` — a titled section whose body shows only when `open`.
 *
 * The header is a resolved surface button carrying the disclosure marker; the
 * body is a padded column rendered only while open, so a closed accordion is a
 * single child and the reconciler removes the body rather than hiding it.
 * `open` is controlled — the app flips it from `onToggle`.
 *
 * @param {{title?: string, open?: boolean,
 *          children?: import("../transport.js").Node[], onToggle?: ?Function,
 *          variant?: string, colorScheme?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Accordion({
  title = "",
  open = false,
  children = [],
  onToggle = null,
  variant = "filled",
  colorScheme = "neutral",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "accordion";
  const header = Button({
    label: `${open ? "▾" : "▸"}  ${title}`,
    onClick: onToggle,
    key: `${base}-header`,
    style: Style({
      ...surfaceStyle(variant, colorScheme, null, "sm", theme),
      padding: Edge.all(SPACING_STEPS.sm),
      font_weight: 700,
    }), theme });
  const body = open
    ? [
        Column({
          key: `${base}-body`,
          style: Style({
            gap: SPACING_STEPS.sm,
            padding: Edge.all(SPACING_STEPS.md),
          }),
          children, theme }),
      ]
    : [];
  return Column({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.xs }, style),
    children: [header, ...body], theme });
}

/**
 * `Tabs` — a tab strip whose active tab carries an underline indicator.
 *
 * Each tab is a ghost button that grows to share the strip evenly; the active
 * one resolves against `colorScheme` instead of neutral and takes a thin bottom
 * `SideBorder` in the accent role — the indicator uses the existing border
 * fields, never a new style field. The active index is app state, reported back
 * through `onSelect`.
 *
 * @param {{tabs?: string[], active?: number, onSelect?: ?Function,
 *          colorScheme?: string, size?: string, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Tabs({
  tabs = [],
  active = 0,
  onSelect = null,
  colorScheme = "primary",
  size = "md",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "tabs";
  const accent = colorRoles(theme)[colorScheme] ?? colorRoles(theme).primary;
  const children = tabs.map((label, index) => {
    const chosen = index === active;
    const resting = resolveWidgetStyle(
      "Button",
      "ghost",
      size,
      chosen ? colorScheme : "neutral",
      null,
    theme,
    );
    const overrides = chosen
      ? { grow: 1.0, border: SideBorder({ bottom: Border({ width: 2.0, color: accent }) }) }
      : { grow: 1.0 };
    return Button({
      label,
      key: `${base}-item-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: mergeStyle(resting, overrides), theme });
  });
  const strip = {
    ...surfaceStyle("filled", "neutral", null, "none", theme),
    gap: 4.0,
    padding: Edge.symmetric({ vertical: 0.0, horizontal: 4.0 }),
    justify: "center",
    align: "stretch",
  };
  return Row({ key: base, style: mergeStyle(strip, style), children, theme });
}

/**
 * The muted label shown above a labelled field.
 *
 * @param {string} label  The label text.
 * @param {string} key    The reconciler key.
 * @returns {import("../transport.js").Node}
 */
function labelText(label, key, theme) {
  return Text({
    content: label,
    key,
    style: Style({ font_size: 13.0, font_weight: 500, color: colorRoles(theme).on_surface_variant }), theme });
}

/**
 * Wrap an input in its optional label and optional error line.
 *
 * The label and the error line are *absent* from the tree when empty, never
 * rendered blank, so the reconciler inserts and removes them — the same shape
 * `_labelled_field` builds in `tempest_core.components.brforms`.
 *
 * @param {string} label   The label text; empty means no label.
 * @param {import("../transport.js").Node} field  The input to wrap.
 * @param {string} error   The validation message; empty means no error line.
 * @param {string} key     The wrapping column's key.
 * @param {?Object} style  The caller's style for the column.
 * @returns {import("../transport.js").Node}
 */
function labelledField(label, field, error, key, style, theme) {
  const children = [];
  if (label) {
    children.push(labelText(label, `${key}-field-label`, theme));
  }
  children.push(field);
  if (error) {
    children.push(
      Text({
        content: error,
        key: `${key}-field-error`,
        style: Style({ font_size: 12.0, color: colorRoles(theme).error }), theme }),
    );
  }
  return Column({ key, style: mergeStyle({ gap: 4.0 }, style), children, theme });
}

/**
 * Adapt the app's string handler to the input's typed change event.
 *
 * A BR field's `on_change` takes the new *value*, so the caller never touches
 * the event object — the adapter the core installs, kept here so a view written
 * against the core behaves the same in Mode C.
 *
 * @param {?Function} handler  The app's `(value: string) => void`, or null.
 * @returns {?Function}
 */
function onValue(handler) {
  return handler == null ? null : (event) => handler(event.value);
}

/**
 * `EmailInput` — a labelled e-mail field with the e-mail keyboard and a mail icon.
 *
 * @param {{value?: string, label?: string, placeholder?: string, error?: string,
 *          onChange?: ?Function, fieldVariant?: string, size?: string,
 *          colorScheme?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function EmailInput({
  value = "",
  label = "E-mail",
  placeholder = "",
  error = "",
  onChange = null,
  fieldVariant = "outline",
  size = "md",
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "email-input";
  const field = Input({
    value,
    placeholder,
    keyboard: "email",
    pattern: EMAIL_PATTERN,
    leadingIcon: "mail",
    error,
    onChange: onValue(onChange),
    key: `${base}-field`,
    fieldVariant,
    size,
    colorScheme, theme });
  return labelledField(label, field, error, base, style, theme);
}

/**
 * `PasswordInput` — a labelled password field (secure, with the eye toggle).
 *
 * @param {{value?: string, label?: string, placeholder?: string, error?: string,
 *          onChange?: ?Function, fieldVariant?: string, size?: string,
 *          colorScheme?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function PasswordInput({
  value = "",
  label = "Senha",
  placeholder = "Senha",
  error = "",
  onChange = null,
  fieldVariant = "outline",
  size = "md",
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "password-input";
  const field = Input({
    value,
    placeholder,
    secure: true,
    leadingIcon: "lock",
    error,
    onChange: onValue(onChange),
    key: `${base}-field`,
    fieldVariant,
    size,
    colorScheme, theme });
  return labelledField(label, field, error, base, style, theme);
}

/**
 * A labelled masked field — the shape `PhoneInput`/`CPFInput`/`CNPJInput` share.
 *
 * @param {{mask: string, keyboard: string, defaultKey: string,
 *          label: string, value: string,
 *          placeholder: string, error: string, onChange: ?Function,
 *          fieldVariant: string, size: string, colorScheme: string,
 *          style: ?Object, key: ?string}} args
 * @returns {import("../transport.js").Node}
 */
function maskedField({
  mask,
  keyboard,
  defaultKey,
  label,
  value,
  placeholder,
  error,
  onChange,
  fieldVariant,
  size,
  colorScheme,
  style,
  key,
}, theme) {
  const base = key ?? defaultKey;
  const field = MaskedInput({
    value,
    placeholder,
    mask,
    keyboard,
    onChange: onValue(onChange),
    key: `${base}-field`,
    fieldVariant,
    size,
    colorScheme, theme });
  return labelledField(label, field, error, base, style, theme);
}

/**
 * `PhoneInput` — a labelled Brazilian phone field, masked `(99) 99999-9999`.
 *
 * @param {{value?: string, label?: string, placeholder?: string, error?: string,
 *          onChange?: ?Function, fieldVariant?: string, size?: string,
 *          colorScheme?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function PhoneInput({
  value = "",
  label = "Telefone",
  placeholder = "",
  error = "",
  onChange = null,
  fieldVariant = "outline",
  size = "md",
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  return maskedField({
    mask: "(99) 99999-9999",
    keyboard: "phone",
    defaultKey: "phone-input",
    label,
    value,
    placeholder,
    error,
    onChange,
    fieldVariant,
    size,
    colorScheme,
    style,
    key,
  }, theme);
}

/**
 * `CPFInput` — a labelled CPF field, masked `999.999.999-99`.
 *
 * @param {{value?: string, label?: string, placeholder?: string, error?: string,
 *          onChange?: ?Function, fieldVariant?: string, size?: string,
 *          colorScheme?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function CPFInput({
  value = "",
  label = "CPF",
  placeholder = "",
  error = "",
  onChange = null,
  fieldVariant = "outline",
  size = "md",
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  return maskedField({
    mask: "999.999.999-99",
    keyboard: "number",
    defaultKey: "cpf-input",
    label,
    value,
    placeholder,
    error,
    onChange,
    fieldVariant,
    size,
    colorScheme,
    style,
    key,
  }, theme);
}

/**
 * `CNPJInput` — a labelled CNPJ field, masked `99.999.999/9999-99`.
 *
 * @param {{value?: string, label?: string, placeholder?: string, error?: string,
 *          onChange?: ?Function, fieldVariant?: string, size?: string,
 *          colorScheme?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function CNPJInput({
  value = "",
  label = "CNPJ",
  placeholder = "",
  error = "",
  onChange = null,
  fieldVariant = "outline",
  size = "md",
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  return maskedField({
    mask: "99.999.999/9999-99",
    keyboard: "number",
    defaultKey: "cnpj-input",
    label,
    value,
    placeholder,
    error,
    onChange,
    fieldVariant,
    size,
    colorScheme,
    style,
    key,
  }, theme);
}

/**
 * `AddressInput` — a grouped Brazilian address block of labelled fields.
 *
 * One handler serves the whole block: it is called as
 * `onChange(fieldName, newValue)` for whichever of `cep`, `street`, `number`,
 * `complement`, `neighborhood`, `city` or `state` changed.
 *
 * @param {{cep?: string, street?: string, number?: string, complement?: string,
 *          neighborhood?: string, city?: string, state?: string, label?: string,
 *          onChange?: ?Function, fieldVariant?: string, size?: string,
 *          colorScheme?: string, style?: ?Object, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function AddressInput({
  cep = "",
  street = "",
  number = "",
  complement = "",
  neighborhood = "",
  city = "",
  state = "",
  label = "Endereço",
  onChange = null,
  fieldVariant = "outline",
  size = "md",
  colorScheme = "primary",
  style = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "address-input";
  const report = (fieldName) =>
    onChange == null ? null : (event) => onChange(fieldName, event.value);
  const children = [];
  if (label) {
    children.push(labelText(label, "address-label", theme));
  }
  children.push(
    MaskedInput({
      value: cep,
      placeholder: "CEP",
      mask: "99999-999",
      keyboard: "number",
      onChange: report("cep"),
      key: `${base}-cep`,
      fieldVariant,
      size,
      colorScheme, theme }),
  );
  const textFields = [
    ["street", street, "Rua"],
    ["number", number, "Número"],
    ["complement", complement, "Complemento"],
    ["neighborhood", neighborhood, "Bairro"],
    ["city", city, "Cidade"],
    ["state", state, "UF"],
  ];
  for (const [fieldName, fieldValue, placeholder] of textFields) {
    children.push(
      Input({
        value: fieldValue,
        placeholder,
        onChange: report(fieldName),
        key: `${base}-${fieldName}`,
        fieldVariant,
        size,
        colorScheme, theme }),
    );
  }
  return Column({
    key: base,
    style: mergeStyle({ gap: 8.0 }, style),
    children, theme });
}

/**
 * Wrap an input in the tempestweb field's label + error column.
 *
 * Every child key is derived from `key`: keys are how the event router finds the
 * handler that fired, so a literal key here would be shared by every field of
 * this kind on the screen and edits would land on the wrong one.
 *
 * @param {string} label   The label text; empty means no label.
 * @param {import("../transport.js").Node} field  The input to wrap.
 * @param {string} error   The validation message; empty means no error line.
 * @param {string} key     The column's key, and the prefix of its children's.
 * @param {?Object} theme  The theme whose scheme resolves the label and error
 *                         colours. `Text` takes no theme of its own, so they are
 *                         resolved here and passed as inline style.
 * @returns {import("../transport.js").Node}
 */
function tempestwebField(label, field, error, key, theme) {
  const children = [];
  if (label) {
    children.push(
      Text({
        content: label,
        key: `${key}-label`,
        style: Style({ font_size: 13.0, font_weight: 500, color: colorRoles(theme).on_surface_variant }), theme }),
    );
  }
  children.push(field);
  if (error) {
    children.push(
      Text({
        content: error,
        key: `${key}-error`,
        style: Style({ font_size: 12.0, color: colorRoles(theme).error }), theme }),
    );
  }
  return Column({ key, style: Style({ gap: 4.0 }), children, theme });
}

/**
 * `TextField` — a generic labelled text field (name, title, …).
 *
 * The plain sibling of the BR fields: an unstyled label, a controlled `Input`
 * and an optional error line, in a column that also carries vertical padding.
 *
 * @param {{value?: string, label?: string, placeholder?: string, error?: string,
 *          onChange?: ?Function, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function TextField({
  value = "",
  label = "",
  placeholder = "",
  error = "",
  onChange = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "text-field";
  const children = [];
  if (label) {
    children.push(Text({ content: label, key: `${base}-label`, theme }));
  }
  children.push(
    Input({ value, placeholder, onChange: onValue(onChange), theme, key: `${base}-input` }),
  );
  if (error) {
    children.push(
      Text({ content: error, key: `${base}-error`, style: Style({ color: colorRoles(theme).error }), theme }),
    );
  }
  return Column({
    key: base,
    style: Style({ gap: 4.0, padding: Edge.symmetric({ vertical: 4.0 }) }),
    children, theme });
}

/**
 * `EmailField` — the tempestweb-native labelled e-mail field.
 *
 * The message is shown on its own line only: unlike the core's `EmailInput`,
 * this field does not hand `error` to the inner `Input`, so the box itself keeps
 * its resting outline.
 *
 * @param {{value?: string, label?: string, placeholder?: string, error?: string,
 *          onChange?: ?Function, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function EmailField({
  value = "",
  label = "E-mail",
  placeholder = "you@example.com",
  error = "",
  onChange = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "email-field";
  const field = Input({
    value,
    placeholder,
    keyboard: "email",
    onChange: onValue(onChange),
    theme,
    key: `${base}-input` });
  return tempestwebField(label, field, error, base, theme);
}

/**
 * `PasswordField` — the tempestweb-native labelled secure field.
 *
 * @param {{value?: string, label?: string, placeholder?: string, error?: string,
 *          onChange?: ?Function, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function PasswordField({
  value = "",
  label = "Senha",
  placeholder = "",
  error = "",
  onChange = null,
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "password-field";
  const field = Input({
    value,
    placeholder,
    secure: true,
    onChange: onValue(onChange),
    theme,
    key: `${base}-input` });
  return tempestwebField(label, field, error, base, theme);
}

/**
 * `LoginForm` — a complete e-mail + password form with a submit button.
 *
 * Controlled: the app holds both values and updates them from the `on*Change`
 * handlers, and `onSubmit` fires on the button. The children key off `key` (or
 * `"login"`) while the column itself keys off `key` or `"login-form"` — the
 * core's own asymmetry, kept so a patch addresses the same node in every mode.
 *
 * @param {{email?: string, password?: string, onEmailChange?: ?Function,
 *          onPasswordChange?: ?Function, onSubmit?: ?Function,
 *          emailError?: string, passwordError?: string, title?: string,
 *          submitLabel?: string, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function LoginForm({
  email = "",
  password = "",
  onEmailChange = null,
  onPasswordChange = null,
  onSubmit = null,
  emailError = "",
  passwordError = "",
  title = "",
  submitLabel = "Entrar",
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "login";
  const children = [];
  if (title) {
    children.push(Text({ content: title, key: `${base}-title`, theme }));
  }
  children.push(
    EmailField({
      value: email,
      onChange: onEmailChange,
      error: emailError,
      key: `${base}-email`, theme }),
    PasswordField({
      value: password,
      onChange: onPasswordChange,
      error: passwordError,
      key: `${base}-password`, theme }),
    Button({ label: submitLabel, onClick: onSubmit, theme, key: `${base}-submit` }),
  );
  return Column({
    key: key ?? "login-form",
    style: Style({ gap: 12.0, padding: Edge.all(16) }),
    children, theme });
}

/**
 * `SignupForm` — e-mail + password + confirm, with a submit button.
 *
 * @param {{email?: string, password?: string, confirm?: string,
 *          onEmailChange?: ?Function, onPasswordChange?: ?Function,
 *          onConfirmChange?: ?Function, onSubmit?: ?Function,
 *          emailError?: string, passwordError?: string, confirmError?: string,
 *          title?: string, submitLabel?: string, key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function SignupForm({
  email = "",
  password = "",
  confirm = "",
  onEmailChange = null,
  onPasswordChange = null,
  onConfirmChange = null,
  onSubmit = null,
  emailError = "",
  passwordError = "",
  confirmError = "",
  title = "",
  submitLabel = "Cadastrar",
  key = null,
  theme = null,
} = {}) {
  const base = key ?? "signup";
  const children = [];
  if (title) {
    children.push(Text({ content: title, key: `${base}-title`, theme }));
  }
  children.push(
    EmailField({
      value: email,
      onChange: onEmailChange,
      error: emailError,
      key: `${base}-email`, theme }),
    PasswordField({
      value: password,
      onChange: onPasswordChange,
      error: passwordError,
      key: `${base}-password`, theme }),
    PasswordField({
      value: confirm,
      onChange: onConfirmChange,
      error: confirmError,
      label: "Confirmar senha",
      key: `${base}-confirm`, theme }),
    Button({ label: submitLabel, onClick: onSubmit, theme, key: `${base}-submit` }),
  );
  return Column({
    key: key ?? "signup-form",
    style: Style({ gap: 12.0, padding: Edge.all(16) }),
    children, theme });
}

export {
  AddressInput as AddressField,
  CNPJInput as CNPJField,
  CPFInput as CPFField,
  PhoneInput as PhoneField,
};
