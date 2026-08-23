// Tests for client/transpile/theme.js + client/media.js — theme + responsiveness.
import { test } from "node:test";
import assert from "node:assert/strict";
import { Breakpoints, MediaQueryData, Theme, ThemeMode } from "../../client/transpile/theme.js";
import { installMedia } from "../../client/media.js";
import { freshDom } from "./setup.js";
import {
  BASE_THEME_CSS,
  THEME_MODE_ATTR,
  applyThemeMode,
} from "../../client/theme.js";

test("Theme.is_dark resolves LIGHT/DARK absolutely, SYSTEM by platform", () => {
  assert.equal(new Theme({ mode: ThemeMode.DARK }).is_dark(), true);
  assert.equal(new Theme({ mode: ThemeMode.LIGHT }).is_dark({ platform_dark_mode: true }), false);
  assert.equal(new Theme({ mode: ThemeMode.SYSTEM }).is_dark({ platform_dark_mode: true }), true);
  assert.equal(new Theme().is_dark(), false); // default SYSTEM, platform light
});

test("MediaQueryData + Breakpoints carry the core defaults", () => {
  const m = new MediaQueryData();
  assert.equal(m.width, 0);
  assert.equal(m.orientation, "portrait");
  const bp = new Breakpoints();
  assert.equal(bp.md, 600);
});

test("installMedia reports a viewport snapshot to the transport", () => {
  const events = [];
  const transport = { sendEvent: (e) => events.push(e) };
  const fakeWin = {
    innerWidth: 800,
    innerHeight: 600,
    devicePixelRatio: 2,
    matchMedia: (q) => ({ matches: q.includes("dark"), addEventListener() {}, removeEventListener() {} }),
    addEventListener() {},
    removeEventListener() {},
  };
  installMedia(transport, fakeWin);
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "media");
  assert.equal(events[0].payload.width, 800);
  assert.equal(events[0].payload.platform_dark_mode, true);
  assert.equal(events[0].payload.orientation, "landscape");
});

test("the sheet carries a dark token block, keyed by the mode attribute", () => {
  // The half of dark mode that lives in CSS: the app's inline styles already
  // follow the theme, but the page, a field's surface and every hover/focus state
  // are painted here — and had no mode axis at all (#148).
  const dark = BASE_THEME_CSS.slice(BASE_THEME_CSS.indexOf(':root[data-tw-theme="dark"]'));
  assert.ok(dark.startsWith(':root[data-tw-theme="dark"]'), "dark block is present");
  for (const token of ["--tw-surface", "--tw-on-surface", "--tw-primary", "--tw-outline"]) {
    assert.ok(dark.includes(`${token}:`), `${token} is redefined for dark`);
  }
  // Deliberately NOT prefers-color-scheme: the core resolves a SYSTEM theme as
  // light for every widget, so darkening from the OS alone would put a light tree
  // on a dark page.
  assert.ok(!BASE_THEME_CSS.includes("@media (prefers-color-scheme"));
});

test("the sheet paints the page, not just the widgets", () => {
  assert.match(BASE_THEME_CSS, /body \{[^}]*background: var\(--tw-surface\)/);
});

test("applyThemeMode marks the document, and unsets on anything else", () => {
  const dom = freshDom();
  globalThis.document = dom.document;

  applyThemeMode("dark");
  assert.equal(dom.document.documentElement.getAttribute(THEME_MODE_ATTR), "dark");

  applyThemeMode("light");
  assert.equal(dom.document.documentElement.getAttribute(THEME_MODE_ATTR), "light");

  // "system" never reaches the client — the app resolves it — so anything else
  // hands the page back to its own default instead of pinning a wrong mode.
  applyThemeMode("system");
  assert.equal(dom.document.documentElement.hasAttribute(THEME_MODE_ATTR), false);
});
