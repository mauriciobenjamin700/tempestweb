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
