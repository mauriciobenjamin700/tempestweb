// layouts.test.js — the stylesheet behind the layout presets (jsdom).
//
// Two things to prove, and they are the two halves of the feature: the sheet
// reaches the document exactly once, and a real preset tree (the golden built by
// tempestweb.presets, mounted through the shared renderer) carries the layout
// roles its rules select on. jsdom does not do layout, so pixel behaviour is
// verified in a browser instead — what is mechanical is asserted here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture, freshDom } from "./setup.js";
import { LAYOUT_CSS, installLayoutStyles } from "../../client/layouts.js";
import { BASE_THEME_STYLE_ID, LAYOUT_STYLE_ID } from "../../client/constants.js";
import { installBaseTheme } from "../../client/theme.js";
import { buildElement } from "../../client/dom.js";

/** Install jsdom's `document` globally, as the renderer expects. */
function withDocument() {
  const dom = freshDom();
  globalThis.document = dom.document;
  return dom;
}

test("installLayoutStyles injects the sheet once", () => {
  const dom = withDocument();
  const first = installLayoutStyles();
  const second = installLayoutStyles();

  assert.equal(first.id, LAYOUT_STYLE_ID);
  assert.equal(first, second, "a second call must reuse the existing element");
  assert.equal(dom.document.querySelectorAll(`#${LAYOUT_STYLE_ID}`).length, 1);
  assert.ok(first.textContent.includes("data-tw-layout"));
});

test("installLayoutStyles is a no-op without a document", () => {
  const saved = globalThis.document;
  delete globalThis.document;
  try {
    assert.equal(installLayoutStyles(), null);
  } finally {
    globalThis.document = saved;
  }
});

test("the sheet is prepended so app styles declared later still win", () => {
  const dom = withDocument();
  const appStyle = dom.document.createElement("style");
  dom.document.head.appendChild(appStyle);
  const sheet = installLayoutStyles();
  assert.equal(dom.document.head.firstChild, sheet);
});

test("the sheet lands after the base theme so ties go to the layout", () => {
  // Both sheets select on one attribute, so their rules tie on specificity and
  // source order decides. Ahead of the theme, its `[data-tw-type="Button"]`
  // display rule beat `[data-tw-layout="shell-burger"] { display: none }` and
  // the burger stayed on screen at desktop widths.
  const dom = withDocument();
  installBaseTheme();
  const sheet = installLayoutStyles();
  const ids = [...dom.document.head.children].map((el) => el.id);
  assert.deepEqual(ids, [BASE_THEME_STYLE_ID, LAYOUT_STYLE_ID]);
  assert.equal(sheet.previousSibling.id, BASE_THEME_STYLE_ID);
});

test("the sheet carries the rules inline style cannot express", () => {
  assert.match(LAYOUT_CSS, /@media \(max-width: 1023px\)/);
  assert.match(LAYOUT_CSS, /@media \(max-width: 639px\)/);
  assert.match(LAYOUT_CSS, /@media print/);
  assert.match(LAYOUT_CSS, /position: sticky/);
  assert.match(LAYOUT_CSS, /overflow-x: auto/);
});

test("no declaration overrides an app's inline style", () => {
  // Comments are stripped first: the prose explains why the sheet avoids the
  // override, and matching that sentence would defeat the check.
  const declarations = LAYOUT_CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  assert.doesNotMatch(declarations, /!important/, "the sheet is a floor, not a cage");
});

test("a preset tree carries its layout roles into the DOM", () => {
  withDocument();
  const el = buildElement(fixture("presets_admin_shell.json"));

  assert.equal(el.getAttribute("data-tw-layout"), "shell");
  for (const role of [
    "shell-sidebar",
    "shell-header",
    "shell-main",
    "shell-scrim",
    "nav-item",
    "page",
    "page-header",
    "toolbar",
    "table-scroll",
    "table",
    "table-head",
    "table-row",
    "table-cell",
  ]) {
    assert.ok(
      el.querySelector(`[data-tw-layout="${role}"]`),
      `no element tagged ${role}`,
    );
  }
});

test("the mounted shell exposes the state its rules select on", () => {
  withDocument();
  const el = buildElement(fixture("presets_admin_shell.json"));

  const sidebar = el.querySelector('[data-tw-layout="shell-sidebar"]');
  assert.equal(sidebar.getAttribute("data-tw-open"), "false");

  const active = el.querySelectorAll('[data-tw-active="true"]');
  assert.equal(active.length, 1, "exactly one nav entry is current");
  assert.match(active[0].textContent, /Usuários/);

  const numeric = el.querySelector('[data-tw-layout="table-header-cell"][data-tw-align="end"]');
  assert.ok(numeric, "a right-aligned column keeps its alignment in the DOM");
});
