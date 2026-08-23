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


/* ── Dark mode ───────────────────────────────────────────────────────────────
   The other half of dark mode. What tempest-core resolves travels as inline
   style, so a Card and a Button follow the app's theme on their own; what only
   this sheet paints — the page, a field's surface, every hover/focus state — had
   no mode axis at all, so a dark app showed a white field inside a dark card.

   The trigger is the data-tw-theme attribute on the root, which the renderer
   writes from the app's own theme (Mode B/SSE receive a "theme" envelope; Mode A
   and Mode C write it in-process). Deliberately NOT prefers-color-scheme: the
   core resolves a SYSTEM theme as light for every widget (a widget never sees the
   OS), so darkening the sheet from the OS alone would put a light tree on a dark
   page. An app that wants to follow the OS reads app.media.platform_dark_mode in
   its view and calls set_theme — then both halves move together.

   The block redefines only tokens: no rule below this point knows which mode is
   active, which is what keeps each widget's styling in one place. */
:root[data-tw-theme="dark"] {
  --tw-primary: #d0bcff;
  --tw-on-primary: #381e72;
  --tw-primary-container: #4f378b;
  --tw-on-primary-container: #eaddff;
  --tw-secondary-container: #4a4458;
  --tw-on-secondary-container: #e8def8;
  --tw-surface: #141218;
  --tw-on-surface: #e6e0e9;
  --tw-on-surface-variant: #cac4d0;
  --tw-outline: #938f99;
  --tw-error: #f2b8b5;
  --tw-success: #7ddc9a;
  --tw-warning: #f5c26b;
  --tw-info: #a8c7fa;
  --tw-neutral: #c9c8cf;
  --tw-elevation-1: 0 1px 2px rgba(0,0,0,0.60), 0 1px 3px 1px rgba(0,0,0,0.40);
  --tw-elevation-2: 0 1px 2px rgba(0,0,0,0.60), 0 2px 6px 2px rgba(0,0,0,0.40);
}

/* The page itself. Without this the tree went dark over a white document — the
   app looked broken in exactly the way a theme is supposed to prevent. */
body {
  background: var(--tw-surface);
  color: var(--tw-on-surface);
}

/* Sensible page baseline so apps don't sit on Times New Roman. */
[data-tw-type] { box-sizing: border-box; }

/* ── Button: interaction layer over the core's resolved variant ────────────
   tempest-core resolves each Button variant's resting look inline — fill, text
   color, pill radius, padding and min-height all come from the core. This sheet
   adds only what inline Style cannot express: the structural bits a <button>
   needs for the overlay (position/overflow), the modern font family, and the
   MD3 interaction state layer (::before) — a translucent overlay of the
   on-color tinting the surface on hover/focus/press.

   IconButton shares every rule: it is the same control with a glyph instead of
   a label, and it renders as a real <button>, so it needs the same UA reset and
   the same state layer. Painting only Button left the icon-only control with
   the browser's own border and no hover/focus feedback. */
[data-tw-type="Button"],
[data-tw-type="IconButton"] {
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
[data-tw-type="Button"]::before,
[data-tw-type="IconButton"]::before {
  content: "";
  position: absolute;
  inset: 0;
  background: currentColor;
  opacity: 0;
  transition: opacity var(--tw-motion);
  pointer-events: none;
}
/* State-layer overlay — universal, correct for every button variant. */
[data-tw-type="Button"]:hover::before,
[data-tw-type="IconButton"]:hover::before { opacity: 0.08; }
[data-tw-type="Button"]:focus-visible,
[data-tw-type="IconButton"]:focus-visible { outline: none; }
[data-tw-type="Button"]:focus-visible::before,
[data-tw-type="IconButton"]:focus-visible::before { opacity: 0.12; }
[data-tw-type="Button"]:active::before,
[data-tw-type="IconButton"]:active::before { opacity: 0.12; }
[data-tw-type="Button"]:disabled,
[data-tw-type="Button"][aria-disabled="true"],
[data-tw-type="IconButton"]:disabled,
[data-tw-type="IconButton"][aria-disabled="true"] {
  background: rgba(29,27,32,0.12);
  color: rgba(29,27,32,0.38);
  box-shadow: none;
  cursor: default;
}
[data-tw-type="Button"]:disabled::before,
[data-tw-type="IconButton"]:disabled::before { opacity: 0; }

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

/* ── Switch: the same <label> + real checkbox, drawn as an M3 track ──────────
   role="switch" keeps it a native checkbox for the keyboard and the screen
   reader; this paints the track and the knob, which is the only part the browser
   has no look for. The knob grows when it lands on, the way M3's does. */
[data-tw-type="Switch"] {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  width: fit-content;
  cursor: pointer;
  font-family: var(--tw-font);
  font-size: 14px;
  color: var(--tw-on-surface);
}
[data-tw-type="Switch"] > input {
  appearance: none;
  -webkit-appearance: none;
  position: relative;
  flex: 0 0 auto;
  width: 52px;
  height: 32px;
  margin: 0;
  border: 2px solid var(--tw-outline);
  border-radius: var(--tw-radius-full);
  background: var(--tw-surface);
  cursor: pointer;
  transition: background var(--tw-motion), border-color var(--tw-motion);
}
[data-tw-type="Switch"] > input::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 6px;
  width: 16px;
  height: 16px;
  border-radius: var(--tw-radius-full);
  background: var(--tw-outline);
  transform: translateY(-50%);
  transition: left var(--tw-motion), width var(--tw-motion), height var(--tw-motion),
    background var(--tw-motion);
}
[data-tw-type="Switch"] > input:checked {
  background: var(--tw-control-accent, var(--tw-primary));
  border-color: var(--tw-control-accent, var(--tw-primary));
}
[data-tw-type="Switch"] > input:checked::after {
  left: 24px;
  width: 24px;
  height: 24px;
  background: var(--tw-on-primary);
}
[data-tw-type="Switch"] > input:focus-visible {
  outline: 2px solid var(--tw-primary);
  outline-offset: 2px;
}

/* ── Sliders: the native range control, tinted ───────────────────────────────
   A range input already knows how to be dragged, arrow-keyed and announced, so
   the sheet only gives it room and the accent. A RangeSlider stacks its two
   thumbs instead of overlapping them: overlapping reads as one broken slider
   when both ends meet, and each thumb stays separately reachable. */
[data-tw-type="Slider"],
[data-tw-type="RangeSlider"] > input {
  width: 100%;
  height: 24px;
  margin: 0;
  accent-color: var(--tw-primary);
  cursor: pointer;
}
[data-tw-type="RangeSlider"] {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
}

/* ── Dropdown: a <select> that matches the Input next to it ────────────────── */
[data-tw-type="Dropdown"] {
  min-height: 40px;
  padding: 9px 12px;
  background: var(--tw-surface);
  color: var(--tw-on-surface);
  font-family: var(--tw-font);
  font-size: 16px;
  line-height: 22px;
  cursor: pointer;
  transition: border-color var(--tw-motion), box-shadow var(--tw-motion);
}
[data-tw-type="Dropdown"]:hover { border-color: var(--tw-on-surface); }
[data-tw-type="Dropdown"]:focus,
[data-tw-type="Dropdown"]:focus-visible {
  outline: none;
  border-color: var(--tw-primary);
  box-shadow: inset 0 0 0 1px var(--tw-primary);
}

/* ── Autocomplete: the field is the wrapper, the input is transparent ────────
   The core resolves the field's outline and radius onto the keyed <label>, so
   the nested input drops its own chrome and just fills it — otherwise the page
   showed a box inside a box. The focus ring follows :focus-within, since what
   takes focus is the child. */
[data-tw-type="Autocomplete"] {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 40px;
  padding: 0 12px;
  background: var(--tw-surface);
  color: var(--tw-on-surface);
  font-family: var(--tw-font);
  font-size: 16px;
  transition: border-color var(--tw-motion), box-shadow var(--tw-motion);
}
[data-tw-type="Autocomplete"] > input {
  flex: 1 1 auto;
  min-width: 0;
  padding: 9px 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  outline: none;
}
[data-tw-type="Autocomplete"] > input::placeholder { color: var(--tw-on-surface-variant); }
[data-tw-type="Autocomplete"]:focus-within {
  border-color: var(--tw-primary);
  box-shadow: inset 0 0 0 1px var(--tw-primary);
}

/* ── Pickers: caption first, the platform's own control after ────────────────
   dom.js appends the caption after the nested input (that is what keeps a
   Checkbox reading "box, then label"), so the pickers put the control back on
   the right with flex order — a field's label belongs before it. A FilePicker
   cannot be told its value by the page, so the chosen file's name is printed
   from the attribute the renderer reflects. */
[data-tw-type="DatePicker"],
[data-tw-type="TimePicker"],
[data-tw-type="FilePicker"] {
  display: inline-flex;
  align-items: center;
  /* A file input is as wide as its button plus the file name, and it does not
     shrink: on a 390px screen one pushed the page 100px sideways. Wrapping puts
     the caption on its own line and lets the control take the width it has. */
  flex-wrap: wrap;
  gap: 8px;
  max-width: 100%;
  width: fit-content;
  cursor: pointer;
  font-family: var(--tw-font);
  font-size: 14px;
  color: var(--tw-on-surface);
}
[data-tw-type="DatePicker"] > input,
[data-tw-type="TimePicker"] > input,
[data-tw-type="FilePicker"] > input {
  order: 1;
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
  min-height: 40px;
  margin: 0;
  padding: 9px 12px;
  border: 1px solid var(--tw-outline);
  border-radius: 4px;
  background: var(--tw-surface);
  color: var(--tw-on-surface);
  font-family: var(--tw-font);
  font-size: 16px;
  cursor: pointer;
}
[data-tw-type="DatePicker"] > input:focus-visible,
[data-tw-type="TimePicker"] > input:focus-visible,
[data-tw-type="FilePicker"] > input:focus-visible {
  outline: none;
  border-color: var(--tw-primary);
  box-shadow: inset 0 0 0 1px var(--tw-primary);
}
[data-tw-type="FilePicker"][data-tw-value]::after {
  order: 2;
  content: attr(data-tw-value);
  color: var(--tw-on-surface-variant);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 18ch;
}

/* ── TabBar: the strip that makes a tabbed screen switchable ─────────────────
   Renderer-owned <button role="tab">s in a role="tablist". The selected tab is
   marked by aria-selected — state as an attribute the sheet reads, so nothing
   here depends on a class the app would have to remember to pass. It scrolls
   sideways rather than wrapping: five tabs on a phone belong in a strip that
   scrolls, not in two rows that shift the content down. */
[data-tw-type="TabBar"] {
  display: flex;
  align-items: stretch;
  gap: 4px;
  width: 100%;
  overflow-x: auto;
  border-bottom: 1px solid var(--tw-outline);
  font-family: var(--tw-font);
}
[data-tw-type="TabBar"] > [role="tab"] {
  flex: 0 0 auto;
  padding: 12px 16px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--tw-on-surface-variant);
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color var(--tw-motion), border-color var(--tw-motion);
}
[data-tw-type="TabBar"] > [role="tab"]:hover { color: var(--tw-on-surface); }
[data-tw-type="TabBar"] > [role="tab"][aria-selected="true"] {
  border-bottom-color: var(--tw-primary);
  color: var(--tw-primary);
}
[data-tw-type="TabBar"] > [role="tab"]:focus-visible {
  outline: 2px solid var(--tw-primary);
  outline-offset: -2px;
}

/* ── RouteDrawer: "open" has to be visible, or the prop is a lie ─────────────
   The drawer is the second child (the core builds content, then drawer). It
   slides over the content instead of sitting next to it — inline, it pushed the
   page sideways and was on screen with open=False. */
[data-tw-type="RouteDrawer"] {
  position: relative;
  display: block;
  overflow: hidden;
}
[data-tw-type="RouteDrawer"] > :nth-child(2) {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 20;
  width: min(320px, 80%);
  overflow: auto;
  background: var(--tw-surface);
  box-shadow: var(--tw-elevation-2);
  transform: translateX(-100%);
  transition: transform var(--tw-motion);
}
[data-tw-type="RouteDrawer"][data-tw-open] > :nth-child(2) { transform: translateX(0); }

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
  display: flex;
  align-items: center;
  gap: 12px;
}
[data-tw-type="Menu"] > [data-tw-part="item"] > svg,
[data-tw-type="ActionSheet"] > [data-tw-part="item"] > svg {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
}
/* The label takes the rest of the row, so a long one wraps inside the item
   instead of pushing the glyph around. */
[data-tw-type="Menu"] > [data-tw-part="item"] > [data-tw-part="item-label"],
[data-tw-type="ActionSheet"] > [data-tw-part="item"] > [data-tw-part="item-label"] {
  flex: 1 1 auto;
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

/* ── Pull-to-refresh: an affordance for a gesture the DOM has none for ─────
   A widget that declares on_refresh is marked [data-tw-refresh] by dom.js;
   client/lists.js arms it while the reader drags past the threshold, and the
   app's own refreshing flag marks the reload in flight. Both states are drawn
   as an inset band at the pull edge rather than a background or a child, so an
   app's inline Style (which owns the element's own declarations) and the
   virtualized list's spacer pseudo-elements are both left alone. */
[data-tw-refresh] { overscroll-behavior: contain; }
[data-tw-refresh][data-tw-pull-armed],
[data-tw-refresh][data-tw-refreshing="true"] {
  box-shadow: inset 0 3px 0 0 var(--tw-primary);
}
[data-tw-refresh="x"][data-tw-pull-armed],
[data-tw-refresh="x"][data-tw-refreshing="true"] {
  box-shadow: inset 3px 0 0 0 var(--tw-primary);
}
[data-tw-refresh][data-tw-refreshing="true"] {
  animation: tw-refresh-pulse 1200ms ease-in-out infinite;
}
/* A standalone RefreshControl has no content of its own, so the spinner the
   renderer owns *is* the widget: invisible at rest, shown once the pull is
   armed, spinning while the app reloads. */
[data-tw-type="RefreshControl"] {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  touch-action: pan-y;
}
[data-tw-type="RefreshControl"] > [data-tw-part="spinner"] {
  box-sizing: border-box;
  width: 20px;
  height: 20px;
  border: 2px solid var(--tw-primary-container);
  border-top-color: var(--tw-primary);
  border-radius: var(--tw-radius-full);
  opacity: 0;
  transition: opacity var(--tw-motion);
}
[data-tw-type="RefreshControl"][data-tw-pull-armed] > [data-tw-part="spinner"] { opacity: 1; }
[data-tw-type="RefreshControl"][data-tw-refreshing="true"] > [data-tw-part="spinner"] {
  opacity: 1;
  animation: tw-spin 900ms linear infinite;
}

/* ── PageView: a snapping carousel ─────────────────────────────────────────
   The core declares page + on_page_change and the widget used to render as a
   plain box: no pages, nothing to swipe. One child per viewport width plus
   scroll snapping gets touch swipe, trackpad and shift+wheel from the browser;
   client/pages.js reports which page the scroll landed on. */
[data-tw-type="PageView"] {
  display: flex;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}
[data-tw-type="PageView"] > * {
  flex: 0 0 100%;
  scroll-snap-align: start;
  min-width: 0;
}

/* ── ReorderableList: rows you can pick up ─────────────────────────────────
   The children are marked draggable by the renderer after each patch batch;
   these are the affordances that make that discoverable. */
[data-tw-reorder] > * {
  cursor: grab;
}
[data-tw-reorder] > *:active {
  cursor: grabbing;
}

/* ── PinInput: a code field that looks like one ────────────────────────────
   One input, spaced out: the platform fills a one-time-code field from an SMS
   and pastes a whole code into it, which N separate boxes throw away. The width
   follows the cap, so the box is the size of the code it takes. */
[data-tw-type="PinInput"] {
  font-family: var(--tw-font);
  font-size: 20px;
  letter-spacing: 0.5em;
  text-align: center;
  padding: 10px 12px;
  width: 100%;
  max-width: 12ch;
  background: var(--tw-surface);
  color: var(--tw-on-surface);
}
[data-tw-type="PinInput"]:focus,
[data-tw-type="PinInput"]:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 1px var(--tw-primary);
}

/* ── FormField: the error the widget declared and nobody drew ───────────────
   The error is a prop, so the renderer cannot make it a child without shifting
   the index the field's own child is addressed by. It arrives as an attribute and is
   painted here, under the control, in the error colour — and the invalid state
   outlines the control itself so the two read as one thing. */
[data-tw-field][aria-invalid="true"]::after {
  content: attr(data-tw-error);
  display: block;
  margin-top: 4px;
  font-family: var(--tw-font);
  font-size: 12px;
  line-height: 16px;
  color: var(--tw-error);
}
[data-tw-field][aria-invalid="true"] [data-tw-type="Input"],
[data-tw-field][aria-invalid="true"] [data-tw-type="PinInput"] {
  box-shadow: inset 0 0 0 1px var(--tw-error);
}

/* ── Gesture surfaces: the pointer belongs to the widget ───────────────────
   A browser will not send pointermove while it is busy panning or zooming the
   page itself, so a pan or pinch handler that does not claim the pointer gets
   silence. touch-action does exactly that, per widget, and nowhere else — the
   rest of the page keeps its native scrolling.

   GestureDetector is deliberately left out: tap, swipe and long press all read
   fine alongside page scrolling, and taking touch-action from it would break
   scrolling on any list that wraps its rows in one. */
[data-tw-type="PanHandler"],
[data-tw-type="ScaleHandler"],
[data-tw-type="InteractiveViewer"] {
  touch-action: none;
  -webkit-user-select: none;
  user-select: none;
}
/* A pinch surface is a viewport onto something bigger. */
[data-tw-type="InteractiveViewer"],
[data-tw-type="ScaleHandler"] {
  overflow: hidden;
}

/* ── Camera widgets: the preview fills the box the app gave it ─────────────
   A CameraPreview and a QrScanner are IR leaves holding a renderer-owned
   <video>. Without these rules the video shows at its intrinsic size, which is
   whatever the camera happens to deliver — a 1280x720 element inside a 240px
   card. object-fit: cover keeps the framing instead of stretching faces. */
[data-tw-camera] {
  display: block;
  position: relative;
  overflow: hidden;
  background: #000;
}
[data-tw-camera] > [data-tw-part="preview"] {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

@keyframes tw-progress-slide {
  0% { margin-inline-start: -40%; }
  100% { margin-inline-start: 100%; }
}
@keyframes tw-spin {
  to { transform: rotate(360deg); }
}
@keyframes tw-refresh-pulse {
  50% { box-shadow: inset 0 3px 0 0 var(--tw-primary-container); }
}

/* A moving bar is decoration; the reader who asked for less motion still needs
   to see that something is running, so the animation stops and the
   indeterminate fill stays as a static band. */
@media (prefers-reduced-motion: reduce) {
  [data-tw-type="ProgressBar"] > [data-tw-part="fill"],
  [data-tw-type="Spinner"],
  [data-tw-refresh][data-tw-refreshing="true"],
  [data-tw-type="RefreshControl"][data-tw-refreshing="true"] > [data-tw-part="spinner"] {
    animation: none;
    transition: none;
  }
  [data-tw-type="RouteDrawer"] > :nth-child(2),
  [data-tw-type="Switch"] > input,
  [data-tw-type="Switch"] > input::after {
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
/** Attribute the renderer writes on <html> to pin the active theme mode. */
export const THEME_MODE_ATTR = "data-tw-theme";

/**
 * Mark the document with the app's resolved theme mode.
 *
 * The base sheet reads this attribute to pick its token block, so this is how the
 * half of dark mode that lives in CSS follows the app instead of the OS. Only
 * `"light"` and `"dark"` are written; anything else (including `"system"`, which
 * the app resolves before sending) removes the attribute, which leaves the sheet
 * on its own `:root` tokens — the light palette. There is no
 * `prefers-color-scheme` fallback to hand the page back to, on purpose: the core
 * resolves a SYSTEM theme as light for every widget, so an OS-driven flip here
 * would darken the page under a light tree.
 *
 * @param {?string} mode  `"light"`, `"dark"`, or null/unknown to unset.
 * @returns {void}
 */
export function applyThemeMode(mode) {
  if (typeof document === "undefined" || document.documentElement == null) {
    return;
  }
  if (mode === "light" || mode === "dark") {
    document.documentElement.setAttribute(THEME_MODE_ATTR, mode);
  } else {
    document.documentElement.removeAttribute(THEME_MODE_ATTR);
  }
}

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
