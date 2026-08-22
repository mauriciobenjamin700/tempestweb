// theme.js — the always-on Material 3 base stylesheet.  UI MODERNIZATION.
//
// Core widgets render with no intrinsic visual style (a Button is a bare
// <button>), so unstyled apps fall back to the browser's ugly chrome defaults.
// This module injects ONE base stylesheet — once, at mount — that gives every
// widget a modern Material 3 look: filled buttons with state layers + elevation,
// outlined text fields, themed checkboxes, smooth focus rings.
//
// Why a stylesheet and not inline Style: inline CSS cannot express :hover,
// :focus-visible, :active or :disabled — the very states that make a control feel
// modern. Those live here, keyed off the `data-tw-type` attribute dom.js stamps on
// every element.
//
// Override order: an app's inline Style (emitted by style.js onto the element's
// `style` attribute) ALWAYS wins over this sheet — inline declarations beat a
// stylesheet rule of equal-or-lower specificity, and nothing here uses
// `!important`. So the base is a floor, not a cage: set `background`/`radius`/etc.
// on a widget's Style and your value takes over while the interaction states stay.
//
// Tokens are CSS custom properties on :root, so an app can rebrand the whole UI by
// overriding e.g. `--tw-primary` from its own <style> without touching this file.

import { BASE_THEME_STYLE_ID as STYLE_ID } from "./constants.js";

/**
 * The Material 3 base theme CSS, exported so tests can assert its content
 * without a live DOM. Tokens (`--tw-*`) are overridable by the app.
 * @type {string}
 */
export const BASE_THEME_CSS = `
:root {
  /* Material 3 baseline palette (light scheme). Override any of these from the
     app to rebrand: e.g. \`:root { --tw-primary: #0b57d0; }\`. */
  --tw-primary: #6750a4;
  --tw-on-primary: #ffffff;
  --tw-primary-container: #eaddff;
  --tw-on-primary-container: #21005d;
  --tw-secondary-container: #e8def8;
  --tw-on-secondary-container: #1d192b;
  --tw-surface: #fef7ff;
  --tw-on-surface: #1d1b20;
  --tw-on-surface-variant: #49454f;
  --tw-outline: #79747e;
  --tw-error: #b3261e;
  /* Status families the core's "color_scheme" vocabulary names but the M3
     baseline palette does not: success, warning, info and neutral. A widget
     tinted by family reads these, so an app rebrands its statuses the same way
     it rebrands "--tw-primary". */
  --tw-success: #146c2e;
  --tw-warning: #8a5300;
  --tw-info: #0b57d0;
  --tw-neutral: #5f5f66;

  /* MD3 elevation levels (umbra + penumbra). */
  --tw-elevation-1: 0 1px 2px rgba(0,0,0,0.30), 0 1px 3px 1px rgba(0,0,0,0.15);
  --tw-elevation-2: 0 1px 2px rgba(0,0,0,0.30), 0 2px 6px 2px rgba(0,0,0,0.15);

  --tw-radius-full: 9999px;
  --tw-font: "Roboto", "Segoe UI", system-ui, -apple-system, sans-serif;
  --tw-motion: 180ms cubic-bezier(0.2, 0, 0, 1);
}

/* Sensible page baseline so apps don't sit on Times New Roman. */
[data-tw-type] { box-sizing: border-box; }

/* ── Button: interaction layer over the core's resolved variant ────────────
   tempest-core resolves each Button variant's resting look inline — fill, text
   color, pill radius, padding and min-height all come from the core. This sheet
   adds only what inline Style cannot express: the structural bits a <button>
   needs for the overlay (position/overflow), the modern font family, and the
   MD3 interaction state layer (::before) — a translucent overlay of the
   on-color tinting the surface on hover/focus/press. */
[data-tw-type="Button"] {
  position: relative;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  font-family: var(--tw-font);
  letter-spacing: 0.1px;
  line-height: 20px;
  cursor: pointer;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  transition: box-shadow var(--tw-motion), background var(--tw-motion);
}
/* The state layer: an overlay tinted with the foreground color, invisible at
   rest and fading in for hover (8%) / focus & press (12%) per MD3 specs. */
[data-tw-type="Button"]::before {
  content: "";
  position: absolute;
  inset: 0;
  background: currentColor;
  opacity: 0;
  transition: opacity var(--tw-motion);
  pointer-events: none;
}
/* State-layer overlay — universal, correct for every button variant. */
[data-tw-type="Button"]:hover::before { opacity: 0.08; }
[data-tw-type="Button"]:focus-visible { outline: none; }
[data-tw-type="Button"]:focus-visible::before { opacity: 0.12; }
[data-tw-type="Button"]:active::before { opacity: 0.12; }
[data-tw-type="Button"]:disabled,
[data-tw-type="Button"][aria-disabled="true"] {
  background: rgba(29,27,32,0.12);
  color: rgba(29,27,32,0.38);
  box-shadow: none;
  cursor: default;
}
[data-tw-type="Button"]:disabled::before { opacity: 0; }

/* ── Input: interaction layer over the core's resolved outlined field ──────
   tempest-core resolves the Input's outline and radius inline; this sheet adds
   the surface fill, type ramp and the focus ring. The focus indicator is an
   inset box-shadow (not a border-color change) because the core's inline border
   would otherwise win over a stylesheet :focus rule. */
[data-tw-type="Input"] {
  min-height: 40px;
  padding: 9px 16px;
  background: var(--tw-surface);
  color: var(--tw-on-surface);
  font-family: var(--tw-font);
  font-size: 16px;
  line-height: 22px;
  transition: border-color var(--tw-motion), box-shadow var(--tw-motion);
}
[data-tw-type="Input"]::placeholder { color: var(--tw-on-surface-variant); }
[data-tw-type="Input"]:hover { border-color: var(--tw-on-surface); }
[data-tw-type="Input"]:focus,
[data-tw-type="Input"]:focus-visible {
  outline: none;
  border-color: var(--tw-primary);
  box-shadow: inset 0 0 0 1px var(--tw-primary);
}
[data-tw-type="Input"]:disabled {
  border-color: rgba(29,27,32,0.12);
  color: rgba(29,27,32,0.38);
}

/* ── Checkbox: a <label> wrapping the real <input type=checkbox> ─────────────
   dom.js renders a Checkbox as a keyed <label> with the caption text and lays
   the row out inline (display/gap/align/width), so the base only sets the
   caption type ramp + cursor on the label and themes the nested box itself. */
[data-tw-type="Checkbox"] {
  cursor: pointer;
  font-family: var(--tw-font);
  font-size: 14px;
  color: var(--tw-on-surface);
}
[data-tw-type="Checkbox"] > input {
  width: 18px;
  height: 18px;
  margin: 0;
  accent-color: var(--tw-primary);
  cursor: pointer;
}

/* ── Text: inherit the modern font instead of the UA serif default ─────────── */
[data-tw-type="Text"] { font-family: var(--tw-font); }

/* ── Progress indicators ───────────────────────────────────────────────────────
   A ProgressBar and a Spinner have no intrinsic size, so without a sheet they
   render as empty zero-height divs — present in the DOM, invisible on screen,
   which is worse than absent: the tree says the app is showing progress and the
   user sees nothing. The accent is picked from the widget's "data-tw-scheme"
   family (dom.js writes it), defaulting to primary. */
[data-tw-type="ProgressBar"] {
  --tw-indicator: var(--tw-primary);
  display: block;
  width: 100%;
  height: 4px;
  overflow: hidden;
  border-radius: var(--tw-radius-full);
  background: var(--tw-primary-container);
}
[data-tw-type="ProgressBar"] > [data-tw-part="fill"] {
  display: block;
  width: 0%;
  height: 100%;
  border-radius: inherit;
  background: var(--tw-indicator);
  transition: width var(--tw-motion);
}
[data-tw-type="ProgressBar"][data-tw-indeterminate] > [data-tw-part="fill"] {
  width: 40%;
  transition: none;
  animation: tw-progress-slide 1200ms ease-in-out infinite;
}
[data-tw-type="Spinner"] {
  --tw-indicator: var(--tw-primary);
  display: inline-block;
  box-sizing: border-box;
  width: 20px;
  height: 20px;
  border: 2px solid var(--tw-primary-container);
  border-top-color: var(--tw-indicator);
  border-radius: var(--tw-radius-full);
  animation: tw-spin 900ms linear infinite;
}
[data-tw-scheme="secondary"] { --tw-indicator: var(--tw-secondary-container); }
[data-tw-scheme="error"] { --tw-indicator: var(--tw-error); }
[data-tw-scheme="success"] { --tw-indicator: var(--tw-success); }
[data-tw-scheme="warning"] { --tw-indicator: var(--tw-warning); }
[data-tw-scheme="info"] { --tw-indicator: var(--tw-info); }
[data-tw-scheme="neutral"] { --tw-indicator: var(--tw-neutral); }

/* ── Overlay layer: dialogs, sheets, toasts ────────────────────────────────
   A scene is a root tree plus a z-ordered overlay layer, and mount() patches
   the layer into its own host. The host used to be an unstyled <div> appended
   after the tree, so "floating" overlays were not floating at all: a Dialog
   rendered inline at the bottom of the page, in the flow, with no card and no
   backdrop. These rules are what make the layer a layer.

   The host itself is transparent to the pointer so it never swallows clicks on
   the app behind it; each overlay takes the pointer back. */
[data-tw-overlays] {
  position: fixed;
  inset: 0;
  z-index: 1000;
  pointer-events: none;
}
[data-tw-overlays] > * { pointer-events: auto; }

/* The scrim sits on the host, not on the dialog: a dialog is the card, and a
   card cannot also be the full-viewport backdrop behind itself. */
[data-tw-overlays]:has([data-tw-type="Dialog"])::before,
[data-tw-overlays]:has([data-tw-type="BottomSheet"])::before,
[data-tw-overlays]:has([data-tw-type="ActionSheet"])::before {
  content: "";
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  pointer-events: auto;
}

[data-tw-type="Dialog"] {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: min(280px, 90vw);
  max-width: min(560px, 90vw);
  max-height: 85vh;
  overflow: auto;
  padding: 24px;
  border-radius: 28px;
  background: var(--tw-surface);
  color: var(--tw-on-surface);
  box-shadow: var(--tw-elevation-2);
  font-family: var(--tw-font);
}

/* A Dialog's title is a prop, not a child: inserting an element for it would
   shift the indices every child patch is relative to. The sheet paints it, and
   dom.js mirrors it to aria-label so it is announced, not just drawn. */
[data-tw-type="Dialog"][data-tw-title]::before {
  content: attr(data-tw-title);
  font-size: 22px;
  line-height: 28px;
  font-weight: 500;
  color: var(--tw-on-surface);
}

[data-tw-type="BottomSheet"] {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 80vh;
  overflow: auto;
  padding: 24px 24px 32px;
  border-radius: 28px 28px 0 0;
  background: var(--tw-surface);
  color: var(--tw-on-surface);
  box-shadow: var(--tw-elevation-2);
  font-family: var(--tw-font);
}

/* A toast is transient and never modal: no scrim, and it must not cover the
   controls the user is still working with. */
[data-tw-type="Toast"] {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  max-width: min(560px, 90vw);
  padding: 14px 16px;
  border-radius: 8px;
  background: var(--tw-on-surface);
  color: var(--tw-surface);
  box-shadow: var(--tw-elevation-2);
  font-family: var(--tw-font);
  font-size: 14px;
  line-height: 20px;
}

/* A menu and an action sheet are cards of choices. Their items are
   renderer-owned buttons (the widgets are IR leaves), so they are styled here
   rather than by the core: full-width rows with a hover state, which inline
   Style cannot express. */
[data-tw-type="Menu"],
[data-tw-type="ActionSheet"],
[data-tw-type="Popover"] {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  min-width: min(220px, 90vw);
  max-width: min(420px, 90vw);
  max-height: 80vh;
  overflow: auto;
  padding: 8px;
  border-radius: 12px;
  background: var(--tw-surface);
  color: var(--tw-on-surface);
  box-shadow: var(--tw-elevation-2);
  font-family: var(--tw-font);
}

/* An action sheet names itself; the title is a prop, not a child. */
[data-tw-type="ActionSheet"][data-tw-title]::before {
  content: attr(data-tw-title);
  padding: 8px 12px 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--tw-on-surface-variant);
}

[data-tw-type="Menu"] > [data-tw-part="item"],
[data-tw-type="ActionSheet"] > [data-tw-part="item"] {
  appearance: none;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 14px;
  text-align: start;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  min-height: 44px;
}
[data-tw-type="Menu"] > [data-tw-part="item"]:hover,
[data-tw-type="ActionSheet"] > [data-tw-part="item"]:hover {
  background: var(--tw-secondary-container);
}
[data-tw-type="Menu"] > [data-tw-part="item"]:focus-visible,
[data-tw-type="ActionSheet"] > [data-tw-part="item"]:focus-visible {
  outline: 2px solid var(--tw-primary);
  outline-offset: -2px;
}

@keyframes tw-progress-slide {
  0% { margin-inline-start: -40%; }
  100% { margin-inline-start: 100%; }
}
@keyframes tw-spin {
  to { transform: rotate(360deg); }
}

/* A moving bar is decoration; the reader who asked for less motion still needs
   to see that something is running, so the animation stops and the
   indeterminate fill stays as a static band. */
@media (prefers-reduced-motion: reduce) {
  [data-tw-type="ProgressBar"] > [data-tw-part="fill"],
  [data-tw-type="Spinner"] {
    animation: none;
    transition: none;
  }
}
`;

/**
 * Inject the Material 3 base stylesheet into the document head, once.
 *
 * Idempotent: if a sheet with {@link BASE_THEME_STYLE_ID} already exists (a
 * previous mount, or the page provided its own) it is left untouched. A no-op
 * when there is no `document` (e.g. a non-DOM test harness). The sheet is
 * prepended to the head so app- and inline-styles declared later still win the
 * cascade.
 *
 * @returns {?HTMLStyleElement}  The injected (or pre-existing) style element, or
 *                               `null` when no document is available.
 */
export function installBaseTheme() {
  if (typeof document === "undefined") {
    return null;
  }
  const existing = document.getElementById(STYLE_ID);
  if (existing != null) {
    return /** @type {HTMLStyleElement} */ (existing);
  }
  const el = document.createElement("style");
  el.id = STYLE_ID;
  el.textContent = BASE_THEME_CSS;
  document.head.insertBefore(el, document.head.firstChild);
  return el;
}
