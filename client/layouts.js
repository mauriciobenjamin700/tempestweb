// layouts.js — the always-on stylesheet behind the layout presets.
//
// `tempestweb.presets` builds whole screens — an admin shell, a dashboard, a
// list page, a form, an auth screen — out of core widgets. What it cannot
// express inline is exactly what makes those screens usable on a real device:
// a sidebar that collapses under a breakpoint, a KPI row that reflows from four
// columns to one, a table header that stays put while the body scrolls, a page
// that prints without its chrome. CSS media queries and `position: sticky` have
// no inline equivalent, so they live here.
//
// How a rule finds its target: every preset stamps `data-tw-layout="<role>"` on
// the container it owns, through the core's `attrs` escape hatch (applied by
// dom.js on every renderer). Roles are a closed, documented set — this is not a
// utility-class engine and apps are not meant to sprinkle these attributes by
// hand; they get them by using a preset.
//
// Two hard constraints shaped these rules:
//
//   1. `Column`/`Row` always carry an inline `display: flex` (style.js writes it
//      per widget type), and inline beats a stylesheet. So every container this
//      sheet lays out is a `Stack`, which renders a bare div with no inline
//      display of its own.
//   2. An app's inline `Style` always wins, here as in theme.js — nothing below
//      uses `!important`. The sheet is a floor, not a cage.
//
// Tokens (`--tw-layout-*`) are overridable from the app, same as the theme's.

import { BASE_THEME_STYLE_ID, LAYOUT_STYLE_ID as STYLE_ID } from "./constants.js";

/**
 * The layout CSS, exported so tests can assert its content without a live DOM.
 * @type {string}
 */
export const LAYOUT_CSS = `
:root {
  --tw-layout-sidebar-width: 260px;
  --tw-layout-content-max: 1200px;
  --tw-layout-gap: 16px;
  --tw-layout-page-padding: 24px;
  --tw-layout-kpi-min: 200px;
  --tw-layout-section-min: 320px;
  --tw-layout-field-min: 220px;
  --tw-layout-scrim: rgba(0, 0, 0, 0.42);
  --tw-layout-zebra: rgba(0, 0, 0, 0.025);
  --tw-layout-hover: rgba(0, 0, 0, 0.045);
  --tw-layout-divider: rgba(0, 0, 0, 0.12);
  --tw-layout-sidebar-muted: #9ca3af;
}

/* ── Type scale: colours resolve from the theme, never from Python ─────────
   A preset that hard-coded a heading colour would pick one palette's value and
   land on a page themed with another — the exact way a title ends up white on
   white. These read the same --tw-* tokens theme.js defines, so rebranding the
   theme rebrands the presets with it. */
[data-tw-layout="title"] {
  color: var(--tw-on-surface, #1d1b20);
  font-weight: 600;
  line-height: 1.25;
}
[data-tw-layout="title"][data-tw-level="page"] { font-size: 1.5rem; }
[data-tw-layout="title"][data-tw-level="section"] { font-size: 1.25rem; }
[data-tw-layout="title"][data-tw-level="group"] { font-size: 1.05rem; }
[data-tw-layout="subtitle"] {
  color: var(--tw-on-surface-variant, #49454f);
  font-size: 0.85rem;
  line-height: 1.4;
}
[data-tw-layout="label"] {
  color: var(--tw-on-surface, #1d1b20);
  font-size: 0.8rem;
  font-weight: 600;
}
[data-tw-layout="error"] {
  color: var(--tw-error, #b3261e);
  font-size: 0.78rem;
}

/* ── Shell: sidebar + header + scrolling main ─────────────────────────────
   A grid, so the sidebar owns a column at every width without the main area
   needing a margin that must be kept in sync. Under 1024px the sidebar leaves
   the grid and becomes an overlay the app opens with data-tw-open. */
[data-tw-layout="shell"] {
  display: grid;
  grid-template-columns: var(--tw-layout-sidebar-width) minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  grid-template-areas: "sidebar header" "sidebar main";
  min-height: 100dvh;
}
[data-tw-layout="shell-sidebar"] {
  grid-area: sidebar;
  position: sticky;
  top: 0;
  align-self: start;
  height: 100dvh;
  overflow-y: auto;
  border-right: 1px solid var(--tw-layout-divider);
}
/* The shell's chrome is a dark surface by design — the contrast is what makes
   the content area read as the page. Its own text therefore opts out of the
   content type scale's colour, which is tuned for the light surface. */
[data-tw-layout="shell-sidebar"] [data-tw-layout="subtitle"] {
  color: var(--tw-layout-sidebar-muted);
}
[data-tw-layout="shell-header"] {
  grid-area: header;
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid var(--tw-layout-divider);
}
[data-tw-layout="shell-main"] {
  grid-area: main;
  min-width: 0;
}
[data-tw-layout="shell-scrim"] { display: none; }

/* A nav row reacts to the pointer. The hover cue is a filter, not a background:
   a nav item is a Button, and the core resolves its variant fill *inline*, which
   beats any rule here. Filtering the rendered pixels sidesteps that instead of
   reaching for !important. Which item is current comes from Python as
   data-tw-active, so the state survives a re-render. */
[data-tw-layout="nav-item"] {
  cursor: pointer;
  width: 100%;
  justify-content: flex-start;
  text-align: left;
  transition: filter var(--tw-motion, 180ms ease);
}
[data-tw-layout="nav-item"]:hover { filter: brightness(0.95); }
[data-tw-layout="nav-item"]:active { filter: brightness(0.9); }
[data-tw-layout="nav-item"][data-tw-active="true"] { font-weight: 600; }

@media (max-width: 1023px) {
  [data-tw-layout="shell"] {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas: "header" "main";
  }
  [data-tw-layout="shell-sidebar"] {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 40;
    width: min(80vw, var(--tw-layout-sidebar-width));
    transform: translateX(-100%);
    transition: transform var(--tw-motion, 180ms ease);
  }
  [data-tw-layout="shell-sidebar"][data-tw-open="true"] { transform: translateX(0); }
  /* Flex, not block: the scrim's only child is the button that closes it, and a
     block parent leaves that button at its intrinsic (zero) size — the backdrop
     would dim the page and swallow nothing. Stretching it is what makes tapping
     outside the drawer work. */
  [data-tw-layout="shell-scrim"][data-tw-open="true"] {
    display: flex;
    position: fixed;
    inset: 0;
    z-index: 30;
    background: var(--tw-layout-scrim);
  }
  [data-tw-layout="shell-scrim"][data-tw-open="true"] > * { flex: 1; }
}

/* The burger only makes sense where the sidebar is an overlay. */
[data-tw-layout="shell-burger"] { display: none; }
@media (max-width: 1023px) {
  [data-tw-layout="shell-burger"] { display: inline-flex; }
}

/* ── Page: vertical rhythm, header, toolbars ──────────────────────────────── */
[data-tw-layout="page"] {
  display: flex;
  flex-direction: column;
  gap: calc(var(--tw-layout-gap) * 1.5);
  padding: var(--tw-layout-page-padding);
  max-width: var(--tw-layout-content-max);
  margin: 0 auto;
  width: 100%;
}
[data-tw-layout="page-header"] {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: var(--tw-layout-gap);
  flex-wrap: wrap;
}
[data-tw-layout="page-actions"],
[data-tw-layout="toolbar"] {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
[data-tw-layout="toolbar"] { justify-content: space-between; }

@media (max-width: 639px) {
  [data-tw-layout="page"] { padding: 16px; }
  [data-tw-layout="page-header"],
  [data-tw-layout="toolbar"] { align-items: stretch; flex-direction: column; }
}

/* ── Grids: reflow by available width, no breakpoint needed ───────────────── */
[data-tw-layout="kpi-grid"] {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(var(--tw-layout-kpi-min), 1fr));
  gap: var(--tw-layout-gap);
}
[data-tw-layout="section-grid"] {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(var(--tw-layout-section-min), 1fr));
  gap: var(--tw-layout-gap);
  align-items: start;
}
[data-tw-layout="section"][data-tw-span="full"] { grid-column: 1 / -1; }

/* ── Table: scrolls sideways, header stays, rows read as rows ─────────────── */
[data-tw-layout="table-scroll"] {
  display: block;
  overflow-x: auto;
  max-width: 100%;
}
[data-tw-layout="table"] {
  display: table;
  width: 100%;
  min-width: max-content;
  border-collapse: collapse;
}
[data-tw-layout="table-head"] {
  display: table-row;
  position: sticky;
  top: 0;
  z-index: 1;
}
[data-tw-layout="table-row"] { display: table-row; }
[data-tw-layout="table-row"]:hover { background: var(--tw-layout-hover); }
[data-tw-layout="table-row"]:nth-of-type(even) { background: var(--tw-layout-zebra); }
[data-tw-layout="table-row"]:nth-of-type(even):hover { background: var(--tw-layout-hover); }
[data-tw-layout="table-cell"],
[data-tw-layout="table-header-cell"] {
  display: table-cell;
  padding: 10px 12px;
  text-align: left;
  vertical-align: middle;
  border-bottom: 1px solid var(--tw-layout-divider);
}
[data-tw-layout="table-header-cell"] {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--tw-surface, #ffffff);
  font-weight: 600;
  white-space: nowrap;
}
[data-tw-layout="table-cell"][data-tw-align="end"],
[data-tw-layout="table-header-cell"][data-tw-align="end"] { text-align: right; }
[data-tw-layout="table-cell"][data-tw-align="center"],
[data-tw-layout="table-header-cell"][data-tw-align="center"] { text-align: center; }

/* ── Forms: label/field pairs, one column on a phone ──────────────────────── */
[data-tw-layout="form-grid"] {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(var(--tw-layout-field-min), 1fr));
  gap: var(--tw-layout-gap);
  align-items: start;
}
[data-tw-layout="form-field"][data-tw-span="full"] { grid-column: 1 / -1; }
[data-tw-layout="form-actions"] {
  display: flex;
  flex-direction: row;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: var(--tw-layout-gap);
  border-top: 1px solid var(--tw-layout-divider);
}
@media (max-width: 639px) {
  [data-tw-layout="form-grid"] { grid-template-columns: minmax(0, 1fr); }
  [data-tw-layout="form-actions"] { flex-direction: column-reverse; align-items: stretch; }
}

/* ── Auth: one card, centred at every size ────────────────────────────────── */
[data-tw-layout="auth"] {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100dvh;
  padding: 24px;
}
[data-tw-layout="auth-card"] {
  width: 100%;
  max-width: 420px;
}

/* ── Print: the chrome is screen furniture ────────────────────────────────── */
@media print {
  [data-tw-layout="shell"] { display: block; }
  [data-tw-layout="shell-sidebar"],
  [data-tw-layout="shell-header"],
  [data-tw-layout="shell-scrim"],
  [data-tw-layout="page-actions"],
  [data-tw-layout="toolbar"],
  [data-tw-layout="form-actions"] { display: none; }
  [data-tw-layout="page"] { max-width: none; padding: 0; }
  [data-tw-layout="table-scroll"] { overflow: visible; }
}

/* ── Reduced motion: the sidebar slide is the only transition here ────────── */
@media (prefers-reduced-motion: reduce) {
  [data-tw-layout="shell-sidebar"] { transition: none; }
}
`;

/**
 * Inject the layout stylesheet once, at mount.
 *
 * Position matters, and only in one direction: this sheet goes **after** the
 * base theme and **before** anything the app writes. Both sheets select on a
 * single attribute, so their rules tie on specificity and the later one wins —
 * with this sheet first, the theme's `[data-tw-type="Button"] { display: … }`
 * beat `[data-tw-layout="shell-burger"] { display: none }` and the burger stayed
 * visible on desktop. Landing right after the theme settles those ties in favour
 * of the layout, while app styles (declared later still) keep beating both.
 *
 * Idempotent: a second call (a re-mount, or a page that shipped the sheet
 * itself) leaves the existing element alone. A no-op without a `document`, so a
 * headless harness can import this module.
 *
 * @returns {?HTMLStyleElement}  The injected (or pre-existing) style element, or
 *                               `null` when no document is available.
 */
export function installLayoutStyles() {
  if (typeof document === "undefined") {
    return null;
  }
  const existing = document.getElementById(STYLE_ID);
  if (existing != null) {
    return /** @type {HTMLStyleElement} */ (existing);
  }
  const el = document.createElement("style");
  el.id = STYLE_ID;
  el.textContent = LAYOUT_CSS;
  const theme = document.getElementById(BASE_THEME_STYLE_ID);
  if (theme != null && theme.parentNode === document.head) {
    document.head.insertBefore(el, theme.nextSibling);
  } else {
    document.head.insertBefore(el, document.head.firstChild);
  }
  return el;
}
