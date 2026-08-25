// scroll.test.js — a ScrollView scrolls, and the frame around it stays put.
//
// `Scaffold(scroll=True)` lowers to a ScrollView, and a ScrollView reached the
// DOM as a plain div: no overflow, no axis, nothing. The tree said the body
// scrolled inside the frame and the browser scrolled the document instead, so a
// frame bounded to the viewport height kept its bars only until the content grew
// past it. Measured in Chrome on a real app: 900px of frame over 3249px of
// content, with the app bar and the action bar riding away up the page.
//
// Same family as the ProgressBar that was emitted with no paint (0.65.0): the
// widget crossed the IR correctly and the renderer had nothing to say about it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { BASE_THEME_CSS } from "../../client/theme.js";
import { applyPatches, buildElement, HORIZONTAL_ATTR } from "../../client/dom.js";
import { freshDom } from "./setup.js";

/**
 * Render one node through the real renderer.
 *
 * @param {Object} node  A wire node.
 * @returns {HTMLElement}  The rendered element.
 */
function rendered(node) {
  globalThis.document = freshDom().document;
  return buildElement(node);
}

/**
 * Build a ScrollView wire node.
 *
 * @param {Object} [props]  Props to carry, e.g. `{ horizontal: true }`.
 * @returns {Object}        The node.
 */
function scroller(props = {}) {
  return { type: "ScrollView", key: "body", props, children: [] };
}

test("the base sheet scrolls a ScrollView along the vertical axis", () => {
  const rule = BASE_THEME_CSS.slice(
    BASE_THEME_CSS.indexOf('[data-tw-type="ScrollView"] {'),
  );

  assert.match(rule, /overflow-y: auto/);
  assert.match(rule, /overflow-x: hidden/);
  // A flex item's automatic minimum is its content, so without this the scroller
  // grows inside a bounded column instead of scrolling — the half of the fix that
  // looks redundant and is not.
  assert.match(rule, /min-height: 0/);
});

test("the horizontal axis flips both overflows and the minimum", () => {
  const rule = BASE_THEME_CSS.slice(
    BASE_THEME_CSS.indexOf(`[data-tw-type="ScrollView"][${HORIZONTAL_ATTR}]`),
  );

  assert.match(rule, /overflow-x: auto/);
  assert.match(rule, /overflow-y: hidden/);
  assert.match(rule, /min-width: 0/);
});

test("a horizontal ScrollView says so in an attribute the sheet can match", () => {
  assert.equal(rendered(scroller({ horizontal: true })).hasAttribute(HORIZONTAL_ATTR), true);
});

test("a vertical ScrollView carries no axis attribute", () => {
  assert.equal(rendered(scroller({ horizontal: false })).hasAttribute(HORIZONTAL_ATTR), false);
});

test("a patch that flips the axis back clears the attribute", () => {
  const el = rendered(scroller({ horizontal: true }));

  // The IR keeps a widget's prop set fixed, so a prop the app stops asking for
  // arrives as `false` rather than disappearing. Treating that as "leave it
  // alone" is what leaves a horizontal scroller scrolling sideways forever.
  applyPatches(el, [{ kind: "update", path: [], set_props: { horizontal: false } }]);

  assert.equal(el.hasAttribute(HORIZONTAL_ATTR), false);
});
