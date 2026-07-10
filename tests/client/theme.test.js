// Tests for client/transpile/theme.js + media.js — theme + responsiveness.
import { test } from "node:test";
import assert from "node:assert/strict";
import { Breakpoints, MediaQueryData, Theme, ThemeMode } from "../../client/transpile/theme.js";
import { installMedia } from "../../client/transpile/media.js";

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
