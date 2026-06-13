// Tests for client/theme.js — the always-on MD3 base stylesheet injection.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { BASE_THEME_CSS, installBaseTheme } from "../../client/theme.js";
import { BASE_THEME_STYLE_ID } from "../../client/constants.js";

test("installBaseTheme injects one style element carrying the MD3 CSS", () => {
  const dom = freshDom();
  globalThis.document = dom.document;

  const el = installBaseTheme();

  assert.ok(el, "returns the injected element");
  assert.equal(el.id, BASE_THEME_STYLE_ID);
  assert.equal(el.tagName, "STYLE");
  assert.equal(dom.document.getElementById(BASE_THEME_STYLE_ID), el);
  assert.equal(el.textContent, BASE_THEME_CSS);
});

test("the base CSS styles the Button, Input and Checkbox by data-tw-type", () => {
  // Buttons get a filled background + interaction states; inputs an outline.
  assert.ok(BASE_THEME_CSS.includes('[data-tw-type="Button"]'), "buttons");
  assert.ok(BASE_THEME_CSS.includes('[data-tw-type="Button"]:hover'), "hover state");
  assert.ok(BASE_THEME_CSS.includes('[data-tw-type="Button"]:focus-visible'), "focus");
  assert.ok(BASE_THEME_CSS.includes('[data-tw-type="Button"]:active'), "press state");
  assert.ok(BASE_THEME_CSS.includes('[data-tw-type="Input"]'), "inputs");
  assert.ok(BASE_THEME_CSS.includes('[data-tw-type="Checkbox"]'), "checkbox");
  assert.ok(BASE_THEME_CSS.includes("--tw-primary"), "overridable token");
  // No !important anywhere: an app's inline Style must still win the cascade.
  assert.ok(!BASE_THEME_CSS.includes("!important"), "no !important");
});

test("installBaseTheme is idempotent — a second call adds no second sheet", () => {
  const dom = freshDom();
  globalThis.document = dom.document;

  const first = installBaseTheme();
  const second = installBaseTheme();

  assert.equal(first, second, "returns the same element");
  assert.equal(
    dom.document.querySelectorAll(`#${BASE_THEME_STYLE_ID}`).length,
    1,
    "exactly one base sheet",
  );
});

test("installBaseTheme prepends the sheet so later styles win the cascade", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  // A pre-existing app stylesheet sits in the head.
  const appSheet = dom.document.createElement("style");
  appSheet.id = "app-styles";
  dom.document.head.appendChild(appSheet);

  installBaseTheme();

  assert.equal(
    dom.document.head.firstElementChild.id,
    BASE_THEME_STYLE_ID,
    "base theme is first, app sheet after it",
  );
});

test("installBaseTheme is a no-op without a document", () => {
  const saved = globalThis.document;
  delete globalThis.document;
  try {
    assert.equal(installBaseTheme(), null);
  } finally {
    globalThis.document = saved;
  }
});
