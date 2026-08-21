// Tests for the progress indicators in client/dom.js — the widgets the renderer
// used to emit as empty divs.
//
// The gap they close was not a missing widget but a silent one: `ProgressBar`
// existed in the core and in the IR, so a tree could say "58% done" while the
// element on screen had zero height and no fill. These assert the parts a user
// actually sees (a sized fill), the part a screen reader hears (the ARIA trio),
// and the part that moves (an Update patch resizing the fill without rebuilding).
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { applyPatches, buildElement } from "../../client/dom.js";

/** Install jsdom's `document` globally so dom.js's `document.createElement` works. */
function withDocument() {
  const dom = freshDom();
  globalThis.document = dom.document;
  return dom;
}

/**
 * Build a ProgressBar IR node.
 * @param {Object} props  The widget props.
 * @returns {Object}      The node.
 */
function bar(props) {
  return { type: "ProgressBar", key: "bar", props, children: [] };
}

test("a determinate ProgressBar renders a fill sized by its value", () => {
  withDocument();

  const el = buildElement(bar({ value: 0.42, indeterminate: false }));
  const fill = el.querySelector('[data-tw-part="fill"]');

  assert.equal(el.tagName, "DIV");
  assert.notEqual(fill, null);
  assert.equal(fill.style.width, "42%");
  assert.equal(el.getAttribute("role"), "progressbar");
  assert.equal(el.getAttribute("aria-valuenow"), "0.42");
  assert.equal(el.getAttribute("aria-valuemin"), "0");
  assert.equal(el.getAttribute("aria-valuemax"), "1");
});

test("an indeterminate ProgressBar claims no value", () => {
  withDocument();

  const el = buildElement(bar({ value: 0.0, indeterminate: true }));

  assert.ok(el.hasAttribute("data-tw-indeterminate"));
  assert.equal(el.getAttribute("aria-valuenow"), null);
  assert.equal(el.querySelector('[data-tw-part="fill"]').style.width, "");
});

test("a value outside [0, 1] is clamped rather than overflowing the track", () => {
  withDocument();

  const over = buildElement(bar({ value: 1.8 }));
  const under = buildElement(bar({ value: -0.5 }));

  assert.equal(over.querySelector('[data-tw-part="fill"]').style.width, "100%");
  assert.equal(under.querySelector('[data-tw-part="fill"]').style.width, "0%");
});

test("an Update patch moves the fill without rebuilding the bar", () => {
  withDocument();
  const root = buildElement(bar({ value: 0.1, indeterminate: false }));
  const fill = root.querySelector('[data-tw-part="fill"]');

  applyPatches(root, [{ kind: "update", path: [], set_props: { value: 0.75 } }]);

  assert.equal(root.querySelector('[data-tw-part="fill"]'), fill);
  assert.equal(fill.style.width, "75%");
  assert.equal(root.getAttribute("aria-valuenow"), "0.75");
});

test("a bar that turns indeterminate mid-flight drops its value", () => {
  withDocument();
  const root = buildElement(bar({ value: 0.6, indeterminate: false }));

  applyPatches(root, [
    { kind: "update", path: [], set_props: { indeterminate: true } },
  ]);

  assert.ok(root.hasAttribute("data-tw-indeterminate"));
  assert.equal(root.getAttribute("aria-valuenow"), null);
});

test("the color family travels as an attribute the stylesheet keys off", () => {
  withDocument();

  const el = buildElement(bar({ value: 0.5, color_scheme: "error" }));

  assert.equal(el.getAttribute("data-tw-scheme"), "error");
});

test("a Spinner is sized by its size prop and defaults to the sheet's size", () => {
  withDocument();

  const sized = buildElement({
    type: "Spinner",
    key: "s1",
    props: { size: 32.0, color_scheme: "primary" },
    children: [],
  });
  const plain = buildElement({
    type: "Spinner",
    key: "s2",
    props: { size: null },
    children: [],
  });

  assert.equal(sized.style.width, "32px");
  assert.equal(sized.style.height, "32px");
  assert.equal(sized.getAttribute("role"), "progressbar");
  assert.equal(plain.style.width, "");
});
