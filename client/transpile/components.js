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
import { Color, Edge, Style, resolveWidgetStyle } from "./widget-support.js";
import { Border, MUTED, ON_SURFACE, SideBorder } from "./values.gen.js";
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
  const base = key ?? "card";
  const inner = Container({
    key: `${base}-body`,
    style: Style({ padding: Edge.all(SPACING_STEPS[paddingStep] ?? 0.0) }),
    child: Column({
      key: `${base}-col`,
      style: Style({ gap: SPACING_STEPS[gapStep] ?? 0.0 }),
      children,
    }),
  });
  return Container({
    key: base,
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
  const base = key ?? "segmented";
  const children = options.map((label, index) => {
    const variant = index === selected ? "solid" : "ghost";
    const segment = resolveWidgetStyle("Button", variant, size, colorScheme, null);
    return Button({
      label,
      key: `${base}-item-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: mergeStyle(segment, { grow: 1.0 }),
    });
  });
  const strip = {
    gap: SPACING_STEPS.xs,
    padding: Edge.all(SPACING_STEPS.xs),
    radius: SHAPE_STEPS.md,
    background: COLOR_ROLES.surface_variant,
  };
  return Row({ key: base, style: mergeStyle(strip, style), children });
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
} = {}) {
  const base = key ?? "appbar";
  const surface = surfaceStyle(variant, colorScheme, elevation, "md");
  const content = surface.color ?? COLOR_ROLES.on_surface;
  const children = [];
  if (leading != null) {
    children.push(leading);
  }
  children.push(
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({ grow: 1.0, font_size: 20.0, font_weight: 700, color: content }),
    }),
  );
  if (actions.length > 0) {
    children.push(
      Row({ key: `${base}-actions`, style: Style({ gap: 8.0 }), children: actions }),
    );
  }
  const bar = {
    ...surface,
    padding: Edge.symmetric({ vertical: 14.0, horizontal: 16.0 }),
    gap: 12.0,
    align: "center",
  };
  return Row({ key: base, style: mergeStyle(bar, style), children });
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
  const base = key ?? "radiogroup";
  const surface = COLOR_ROLES.surface;
  const children = options.map((label, index) => {
    const chosen = index === selected;
    const state = chosen ? "checked" : "unchecked";
    const accent = SELECTION_ACCENT[size]?.[colorScheme]?.[state] ?? null;
    const marker = chosen && accent != null ? accent : COLOR_ROLES.on_surface_variant;
    return Button({
      label: `${chosen ? "\u25c9" : "\u25cb"}  ${label}`,
      key: `${base}-item-${index}`,
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
    key: base,
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
  const base = key ?? "scaffold";
  const children = [];
  if (appBar != null) {
    children.push(appBar);
  }
  const content = body ?? Column({});
  children.push(
    scroll
      ? ScrollView({ key: `${base}-body`, style: Style({ grow: 1.0 }), children: [content] })
      : Container({ key: `${base}-body`, style: Style({ grow: 1.0 }), child: content }),
  );
  if (bottomBar != null) {
    children.push(bottomBar);
  }
  const shell = { gap: 0.0, background: COLOR_ROLES.background };
  return Column({ key: base, style: mergeStyle(shell, style), children });
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
} = {}) {
  return Container({
    key: key ?? "surface",
    style: mergeStyle(surfaceStyle(variant, colorScheme, elevation, radiusStep), style),
    child,
  });
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
export function StyledContainer({ child = null, padding = "md", style = null, key = null } = {}) {
  const amount = typeof padding === "string" ? SPACING_STEPS[padding] ?? 0.0 : padding;
  return Container({
    key: key ?? "styled-container",
    style: mergeStyle({ padding: Edge.all(amount) }, style),
    child,
  });
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
export function Grid({ children = [], columns = 2, gap = 8.0, style = null, key = null } = {}) {
  const base = key ?? "grid";
  const perRow = Math.max(1, columns);
  const space = typeof gap === "string" ? SPACING_STEPS[gap] ?? 0.0 : gap;
  const rows = [];
  for (let start = 0; start < children.length; start += perRow) {
    const chunk = children.slice(start, start + perRow);
    const cells = chunk.map((child, offset) =>
      Container({ key: `${base}-cell-${start + offset}`, style: Style({ grow: 1.0 }), child }),
    );
    for (let pad = chunk.length; pad < perRow; pad += 1) {
      cells.push(
        Container({ key: `${base}-cell-pad-${start}-${pad}`, style: Style({ grow: 1.0 }) }),
      );
    }
    rows.push(
      Row({ key: `${base}-row-${start}`, style: Style({ gap: space }), children: cells }),
    );
  }
  return Column({
    key: base,
    style: mergeStyle({ gap: space }, style),
    children: rows,
  });
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
function lateralPanel(key, children, width, variant, colorScheme, elevation, style) {
  const frame = {
    ...surfaceStyle(variant, colorScheme, elevation, "md"),
    width,
    padding: Edge.all(16.0),
    gap: 10.0,
  };
  return Column({ key, style: mergeStyle(frame, style), children });
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
} = {}) {
  return lateralPanel(key ?? "sidebar", children, width, variant, colorScheme, elevation, style);
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
} = {}) {
  if (!open) {
    return Container({ key: key ?? "drawer" });
  }
  return lateralPanel(key ?? "drawer", children, width, variant, colorScheme, elevation, style);
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
} = {}) {
  return IconButton({
    icon: "menu",
    label: "menu",
    onClick,
    variant,
    colorScheme,
    size,
    key: key ?? "burger",
    style,
  });
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
export function Header({ title = "", subtitle = null, colorScheme = null, style = null, key = null } = {}) {
  const base = key ?? "header";
  const titleColor =
    colorScheme != null && colorScheme !== "neutral"
      ? COLOR_ROLES[colorScheme]
      : COLOR_ROLES.on_surface;
  const children = [
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({
        font_size: TYPOGRAPHY.headline_small.font_size,
        font_weight: 700,
        color: titleColor,
      }),
    }),
  ];
  if (subtitle != null) {
    children.push(
      Text({
        content: subtitle,
        key: `${base}-subtitle`,
        style: Style({
          font_size: TYPOGRAPHY.body_medium.font_size,
          color: COLOR_ROLES.on_surface_variant,
        }),
      }),
    );
  }
  const chrome = {
    padding: Edge.all(SPACING_STEPS.lg),
    gap: SPACING_STEPS.xs,
    background: COLOR_ROLES.surface_variant,
  };
  return Column({ key: base, style: mergeStyle(chrome, style), children });
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
} = {}) {
  const base = {
    ...surfaceStyle(variant, colorScheme, elevation, "md"),
    padding: Edge.symmetric({ vertical: 12.0, horizontal: 16.0 }),
    gap: 12.0,
    align: "center",
  };
  return Row({ key: key ?? "footer", style: mergeStyle(base, style), children });
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
} = {}) {
  const base = key ?? "navbar";
  const children = items.map((label, index) => {
    const itemStyle =
      index === active
        ? BADGE_STYLES.solid?.[size]?.[colorScheme] ?? {}
        : resolveWidgetStyle("Button", "ghost", size, "neutral", null);
    return Button({
      label,
      key: `${base}-item-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: mergeStyle(itemStyle, { grow: 1.0 }),
    });
  });
  const bar = {
    ...surfaceStyle("filled", "neutral", null, "md"),
    gap: 8.0,
    padding: Edge.all(8.0),
    justify: "center",
  };
  return Row({ key: base, style: mergeStyle(bar, style), children });
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
} = {}) {
  const base = key ?? "breadcrumb";
  const children = [];
  items.forEach((label, index) => {
    if (index) {
      children.push(
        Text({
          content: separator,
          key: `${base}-sep-${index}`,
          style: Style({ color: COLOR_ROLES.on_surface_variant, font_size: 14.0 }),
        }),
      );
    }
    const isLast = index === items.length - 1;
    if (onSelect != null && !isLast) {
      children.push(
        Button({
          label,
          key: `${base}-item-${index}`,
          onClick: () => onSelect(index),
          style: resolveWidgetStyle("Button", "link", "sm", colorScheme, null),
        }),
      );
      return;
    }
    children.push(
      Text({
        content: label,
        key: `${base}-item-${index}`,
        style: Style({
          color: isLast ? COLOR_ROLES.on_surface : COLOR_ROLES.on_surface_variant,
          font_size: 14.0,
          font_weight: isLast ? 700 : 400,
        }),
      }),
    );
  });
  return Row({
    key: base,
    style: mergeStyle({ gap: 6.0, align: "center" }, style),
    children,
  });
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
} = {}) {
  const base = key ?? "listtile";
  const titleColor =
    colorScheme != null && colorScheme !== "neutral"
      ? COLOR_ROLES[colorScheme]
      : COLOR_ROLES.on_surface;
  const textChildren = [
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({
        font_size: TYPOGRAPHY.body_large.font_size,
        font_weight: TYPOGRAPHY.body_large.font_weight,
        color: titleColor,
      }),
    }),
  ];
  if (subtitle != null) {
    textChildren.push(
      Text({
        content: subtitle,
        key: `${base}-subtitle`,
        style: Style({
          font_size: TYPOGRAPHY.body_small.font_size,
          color: COLOR_ROLES.on_surface_variant,
        }),
      }),
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
      children: textChildren,
    }),
  );
  if (trailing != null) {
    children.push(trailing);
  }
  const tile = {
    gap: SPACING_STEPS.sm,
    align: "center",
    padding: Edge.symmetric({ vertical: SPACING_STEPS.sm, horizontal: SPACING_STEPS.md }),
  };
  return Row({ key: base, style: mergeStyle(tile, style), children });
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
export function Avatar({ initials = "", size = 40.0, colorScheme = "primary", style = null, key = null } = {}) {
  const base = key ?? "avatar";
  const pair = AVATAR_COLORS[colorScheme] ?? AVATAR_COLORS.primary;
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
      style: Style({ color: pair.color, font_weight: 700, text_align: "center" }),
    }),
  });
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
export function Tag({ label = "", colorScheme = "primary", size = "md", style = null, key = null } = {}) {
  return Chip({ label, colorScheme, size, style, key });
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
} = {}) {
  const base = key ?? "rating";
  const color = COLOR_ROLES[colorScheme];
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
          style: Style({ font_size: 24.0, color, background: Color({ a: 0.0 }) }),
        }),
      );
    } else {
      children.push(
        Text({
          content: glyph,
          key: `${base}-star-${index}`,
          style: Style({ font_size: 24.0, color }),
        }),
      );
    }
  }
  return Row({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.xs }, style),
    children,
  });
}

/**
 * `Stepper` — a numeric spinner: `-` decrement, current value, `+` increment.
 *
 * Each button reports the value already clamped to `minValue`/`maxValue`, so the
 * app never has to re-check the bounds it declared.
 *
 * @param {{value?: number, step?: number, minValue?: ?number,
 *          maxValue?: ?number, onChange?: ?Function, style?: ?Object,
 *          key?: ?string}} [args]
 * @returns {import("../transport.js").Node}
 */
export function Stepper({
  value = 0,
  step = 1,
  minValue = null,
  maxValue = null,
  onChange = null,
  style = null,
  key = null,
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
  const button = (label, delta, buttonKey) =>
    Button({
      label,
      key: buttonKey,
      onClick: onChange == null ? null : () => onChange(clamped(value + delta)),
      style: Style({
        padding: Edge.symmetric({ vertical: 8.0, horizontal: 16.0 }),
        radius: 8.0,
        background: MUTED,
        color: ON_SURFACE,
        font_size: 18.0,
      }),
    });
  return Row({
    key: base,
    style: mergeStyle({ gap: 10.0, align: "center" }, style),
    children: [
      button("-", -step, `${base}-down`),
      Text({
        content: String(value),
        key: `${base}-value`,
        style: Style({ font_size: 18.0, font_weight: 700, color: ON_SURFACE }),
      }),
      button("+", step, `${base}-up`),
    ],
  });
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
} = {}) {
  const base = key ?? "searchbar";
  const field = FIELD_STYLES[fieldVariant]?.[size]?.[colorScheme] ?? {};
  const children = [
    Input({
      value,
      placeholder,
      onChange,
      key: `${base}-input`,
      style: mergeStyle(field, { grow: 1.0 }),
    }),
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
        key: `${base}-clear`,
      }),
    );
  }
  const box = {
    ...surfaceStyle("filled", colorScheme, null, "lg"),
    gap: 8.0,
    align: "center",
    padding: Edge.all(8.0),
  };
  return Row({ key: base, style: mergeStyle(box, style), children });
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
} = {}) {
  const base = key ?? "banner";
  const scheme = colorScheme ?? toneScheme(tone);
  const resolved = ALERT_STYLES[variant]?.[scheme] ?? {};
  const children = [
    Text({
      content: message,
      key: `${base}-text`,
      style: Style({ grow: 1.0, color: resolved.color ?? null, font_size: 14.0 }),
    }),
  ];
  if (action != null) {
    children.push(action);
  }
  const strip = { ...resolved, gap: 12.0, align: "center" };
  return Row({ key: base, style: mergeStyle(strip, style), children });
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
} = {}) {
  const base = key ?? "alert";
  const resolved = ALERT_STYLES[variant]?.[colorScheme] ?? {};
  const content = resolved.color ?? null;
  const columnChildren = [
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({ color: content, font_size: 15.0, font_weight: 700 }),
    }),
  ];
  if (body != null) {
    columnChildren.push(
      Text({
        content: body,
        key: `${base}-body`,
        style: Style({ color: content, font_size: 13.0 }),
      }),
    );
  }
  const children = [];
  if (glyph != null) {
    children.push(
      Text({
        content: glyph,
        key: `${base}-glyph`,
        style: Style({ color: content, font_size: 20.0 }),
      }),
    );
  }
  children.push(
    Column({
      key: `${base}-col`,
      style: Style({ grow: 1.0, gap: SPACING_STEPS.xs }),
      children: columnChildren,
    }),
  );
  if (dismiss != null) {
    children.push(dismiss);
  }
  const block = { ...resolved, gap: SPACING_STEPS.sm, align: "center" };
  return Row({ key: base, style: mergeStyle(block, style), children });
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
} = {}) {
  const scheme = colorScheme ?? toneScheme(tone);
  const pill = BADGE_STYLES[variant]?.[size]?.[scheme] ?? {};
  return Text({
    content: label,
    key: key ?? "badge",
    style: mergeStyle({ ...pill, text_align: "center" }, style),
  });
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
} = {}) {
  const base = key ?? "emptystate";
  const muted = COLOR_ROLES.on_surface_variant;
  const children = [
    Text({
      content: glyph,
      key: `${base}-glyph`,
      style: Style({ font_size: 48.0, color: muted, text_align: "center" }),
    }),
    Text({
      content: title,
      key: `${base}-title`,
      style: Style({
        font_size: 18.0,
        font_weight: 700,
        color: COLOR_ROLES.on_surface,
        text_align: "center",
      }),
    }),
  ];
  if (subtitle != null) {
    children.push(
      Text({
        content: subtitle,
        key: `${base}-subtitle`,
        style: Style({ font_size: 14.0, color: muted, text_align: "center" }),
      }),
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
  return Column({ key: base, style: mergeStyle(frame, style), children });
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
export function Stat({ label = "", value = "", delta = null, deltaUp = true, style = null, key = null } = {}) {
  const base = key ?? "stat";
  const children = [
    Text({
      content: label,
      key: `${base}-label`,
      style: Style({ color: COLOR_ROLES.on_surface_variant, font_size: 13.0 }),
    }),
    Text({
      content: value,
      key: `${base}-value`,
      style: Style({ color: COLOR_ROLES.on_surface, font_size: 28.0, font_weight: 700 }),
    }),
  ];
  if (delta != null) {
    children.push(
      Text({
        content: `${deltaUp ? "▲" : "▼"} ${delta}`,
        key: `${base}-delta`,
        style: Style({
          color: deltaUp ? COLOR_ROLES.success : COLOR_ROLES.error,
          font_size: 13.0,
          font_weight: 500,
        }),
      }),
    );
  }
  return Column({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.xs }, style),
    children,
  });
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
function stepCell(index, label, current, colorScheme, base) {
  const doneOrActive = index <= current;
  const muted = COLOR_ROLES.on_surface_variant;
  const disc = doneOrActive
    ? Style({
        width: 28.0,
        height: 28.0,
        radius: 14.0,
        background: COLOR_ROLES[colorScheme],
        color: COLOR_ROLES[`on_${colorScheme}`],
        align: "center",
        text_align: "center",
        font_weight: 700,
        font_size: 13.0,
      })
    : Style({
        width: 28.0,
        height: 28.0,
        radius: 14.0,
        border: { width: 1.0, color: COLOR_ROLES.outline },
        color: muted,
        align: "center",
        text_align: "center",
        font_size: 13.0,
      });
  return Column({
    key: `${base}-step-${index}`,
    style: Style({ gap: SPACING_STEPS.xs, align: "center" }),
    children: [
      Text({ content: String(index + 1), key: `${base}-step-disc-${index}`, style: disc }),
      Text({
        content: label,
        key: `${base}-step-label-${index}`,
        style: Style({
          color: doneOrActive ? COLOR_ROLES.on_surface : muted,
          font_size: 12.0,
        }),
      }),
    ],
  });
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
              index <= current ? COLOR_ROLES[colorScheme] : COLOR_ROLES.outline_variant,
          }),
        }),
      );
    }
    children.push(stepCell(index, label, current, colorScheme, base));
  });
  return Row({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.xs, align: "center" }, style),
    children,
  });
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
} = {}) {
  const base = key ?? "metric-card";
  const stat = Stat({
    label,
    value,
    delta,
    deltaUp,
    key: `${base}-stat`,
    style: Style({ grow: 1.0 }),
  });
  const body =
    trailing == null
      ? stat
      : Row({
          key: `${base}-row`,
          style: Style({ gap: SPACING_STEPS.md, align: "center" }),
          children: [stat, trailing],
        });
  return Card({
    key: base,
    variant,
    colorScheme,
    style,
    children: [body],
  });
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
    key: key ?? "stat-card",
  });
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
} = {}) {
  const percent = `${(confidence * 100).toFixed(0)}%`;
  return Badge({
    key: key ?? "confidence-badge",
    label: label ? `${label} ${percent}`.trim() : percent,
    colorScheme: confidence_scheme(confidence, { high, mid }),
    variant: "subtle",
    style,
  });
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
} = {}) {
  const base = key ?? "accordion";
  const header = Button({
    label: `${open ? "▾" : "▸"}  ${title}`,
    onClick: onToggle,
    key: `${base}-header`,
    style: Style({
      ...surfaceStyle(variant, colorScheme, null, "sm"),
      padding: Edge.all(SPACING_STEPS.sm),
      font_weight: 700,
    }),
  });
  const body = open
    ? [
        Column({
          key: `${base}-body`,
          style: Style({
            gap: SPACING_STEPS.sm,
            padding: Edge.all(SPACING_STEPS.md),
          }),
          children,
        }),
      ]
    : [];
  return Column({
    key: base,
    style: mergeStyle({ gap: SPACING_STEPS.xs }, style),
    children: [header, ...body],
  });
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
} = {}) {
  const base = key ?? "tabs";
  const accent = COLOR_ROLES[colorScheme] ?? COLOR_ROLES.primary;
  const children = tabs.map((label, index) => {
    const chosen = index === active;
    const resting = resolveWidgetStyle(
      "Button",
      "ghost",
      size,
      chosen ? colorScheme : "neutral",
      null,
    );
    const overrides = chosen
      ? { grow: 1.0, border: SideBorder({ bottom: Border({ width: 2.0, color: accent }) }) }
      : { grow: 1.0 };
    return Button({
      label,
      key: `${base}-item-${index}`,
      onClick: onSelect == null ? null : () => onSelect(index),
      style: mergeStyle(resting, overrides),
    });
  });
  const strip = {
    ...surfaceStyle("filled", "neutral", null, "none"),
    gap: 4.0,
    padding: Edge.symmetric({ vertical: 0.0, horizontal: 4.0 }),
    justify: "center",
    align: "stretch",
  };
  return Row({ key: base, style: mergeStyle(strip, style), children });
}

/**
 * The muted label shown above a labelled field.
 *
 * @param {string} label  The label text.
 * @param {string} key    The reconciler key.
 * @returns {import("../transport.js").Node}
 */
function labelText(label, key) {
  return Text({
    content: label,
    key,
    style: Style({ font_size: 13.0, font_weight: 500, color: COLOR_ROLES.on_surface_variant }),
  });
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
function labelledField(label, field, error, key, style) {
  const children = [];
  if (label) {
    children.push(labelText(label, `${key}-field-label`));
  }
  children.push(field);
  if (error) {
    children.push(
      Text({
        content: error,
        key: `${key}-field-error`,
        style: Style({ font_size: 12.0, color: COLOR_ROLES.error }),
      }),
    );
  }
  return Column({ key, style: mergeStyle({ gap: 4.0 }, style), children });
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
    colorScheme,
  });
  return labelledField(label, field, error, base, style);
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
    colorScheme,
  });
  return labelledField(label, field, error, base, style);
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
}) {
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
    colorScheme,
  });
  return labelledField(label, field, error, base, style);
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
  });
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
  });
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
  });
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
} = {}) {
  const base = key ?? "address-input";
  const report = (fieldName) =>
    onChange == null ? null : (event) => onChange(fieldName, event.value);
  const children = [];
  if (label) {
    children.push(labelText(label, "address-label"));
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
      colorScheme,
    }),
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
        colorScheme,
      }),
    );
  }
  return Column({
    key: base,
    style: mergeStyle({ gap: 8.0 }, style),
    children,
  });
}

/**
 * The label color the tempestweb-native fields paint with (`#49454f`).
 *
 * These fields predate the theme-resolved BR inputs above and carry their own
 * two constants, tuned for the light Material 3 surface the base stylesheet
 * renders against. They are not the theme's `on_surface_variant`/`error` roles —
 * porting them as such would shift the color a few units and break parity.
 * @type {Readonly<Object>}
 */
const FIELD_LABEL_COLOR = Object.freeze({ r: 73, g: 69, b: 79, a: 1.0 });

/**
 * The error color the tempestweb-native fields paint with (`#b3261e`).
 * @type {Readonly<Object>}
 */
const FIELD_ERROR_COLOR = Object.freeze({ r: 179, g: 38, b: 30, a: 1.0 });

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
 * @returns {import("../transport.js").Node}
 */
function tempestwebField(label, field, error, key) {
  const children = [];
  if (label) {
    children.push(
      Text({
        content: label,
        key: `${key}-label`,
        style: Style({ font_size: 13.0, font_weight: 500, color: FIELD_LABEL_COLOR }),
      }),
    );
  }
  children.push(field);
  if (error) {
    children.push(
      Text({
        content: error,
        key: `${key}-error`,
        style: Style({ font_size: 12.0, color: FIELD_ERROR_COLOR }),
      }),
    );
  }
  return Column({ key, style: Style({ gap: 4.0 }), children });
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
} = {}) {
  const base = key ?? "text-field";
  const children = [];
  if (label) {
    children.push(Text({ content: label, key: `${base}-label` }));
  }
  children.push(
    Input({ value, placeholder, onChange: onValue(onChange), key: `${base}-input` }),
  );
  if (error) {
    children.push(
      Text({ content: error, key: `${base}-error`, style: Style({ color: FIELD_ERROR_COLOR }) }),
    );
  }
  return Column({
    key: base,
    style: Style({ gap: 4.0, padding: Edge.symmetric({ vertical: 4.0 }) }),
    children,
  });
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
} = {}) {
  const base = key ?? "email-field";
  const field = Input({
    value,
    placeholder,
    keyboard: "email",
    onChange: onValue(onChange),
    key: `${base}-input`,
  });
  return tempestwebField(label, field, error, base);
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
} = {}) {
  const base = key ?? "password-field";
  const field = Input({
    value,
    placeholder,
    secure: true,
    onChange: onValue(onChange),
    key: `${base}-input`,
  });
  return tempestwebField(label, field, error, base);
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
} = {}) {
  const base = key ?? "login";
  const children = [];
  if (title) {
    children.push(Text({ content: title, key: `${base}-title` }));
  }
  children.push(
    EmailField({
      value: email,
      onChange: onEmailChange,
      error: emailError,
      key: `${base}-email`,
    }),
    PasswordField({
      value: password,
      onChange: onPasswordChange,
      error: passwordError,
      key: `${base}-password`,
    }),
    Button({ label: submitLabel, onClick: onSubmit, key: `${base}-submit` }),
  );
  return Column({
    key: key ?? "login-form",
    style: Style({ gap: 12.0, padding: Edge.all(16) }),
    children,
  });
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
} = {}) {
  const base = key ?? "signup";
  const children = [];
  if (title) {
    children.push(Text({ content: title, key: `${base}-title` }));
  }
  children.push(
    EmailField({
      value: email,
      onChange: onEmailChange,
      error: emailError,
      key: `${base}-email`,
    }),
    PasswordField({
      value: password,
      onChange: onPasswordChange,
      error: passwordError,
      key: `${base}-password`,
    }),
    PasswordField({
      value: confirm,
      onChange: onConfirmChange,
      error: confirmError,
      label: "Confirmar senha",
      key: `${base}-confirm`,
    }),
    Button({ label: submitLabel, onClick: onSubmit, key: `${base}-submit` }),
  );
  return Column({
    key: key ?? "signup-form",
    style: Style({ gap: 12.0, padding: Edge.all(16) }),
    children,
  });
}

export {
  AddressInput as AddressField,
  CNPJInput as CNPJField,
  CPFInput as CPFField,
  PhoneInput as PhoneField,
};
