// The overlay layer: a scene's dialogs/sheets/toasts must actually float.
//
// `mount` patches overlays into their own host, but the host was an unstyled
// <div> appended after the tree and the widgets had no rules of their own — so a
// "floating dialog" rendered inline at the bottom of the page, with no card, no
// backdrop, and its `title` (a prop, not a child) never drawn at all.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { applyPatches, buildElement, TITLE_ATTR } from "../../client/dom.js";
import { BASE_THEME_CSS } from "../../client/theme.js";

/** Install jsdom's `document` globally so dom.js's `document.createElement` works. */
function withDocument() {
  const dom = freshDom();
  globalThis.document = dom.document;
  return dom;
}

test("a Dialog carries its title as an attribute and an accessible name", () => {
  withDocument();
  const el = buildElement({
    type: "Dialog",
    key: "d1",
    props: { title: "Hello" },
    children: [
      { type: "Text", key: "body", props: { content: "I float" }, children: [] },
    ],
  });

  assert.equal(el.getAttribute(TITLE_ATTR), "Hello");
  assert.equal(el.getAttribute("aria-label"), "Hello");
  assert.equal(el.getAttribute("role"), "dialog");
  assert.equal(el.getAttribute("aria-modal"), "true");
  // The title must not become a child: child patch paths are index-relative.
  assert.equal(el.children.length, 1);
  assert.equal(el.children[0].textContent, "I float");
});

test("a cleared Dialog title stops being announced", () => {
  withDocument();
  const el = buildElement({
    type: "Dialog",
    key: "d1",
    props: { title: "Hello" },
    children: [],
  });
  applyPatches(el, [{ path: [], set_props: { title: "" } }]);
  assert.equal(el.hasAttribute(TITLE_ATTR), false);
  assert.equal(el.hasAttribute("aria-label"), false);
});

test("a Toast renders its message and announces itself politely", () => {
  withDocument();
  const el = buildElement({
    type: "Toast",
    key: "t1",
    props: { message: "Saved" },
    children: [],
  });
  assert.equal(el.textContent, "Saved");
  assert.equal(el.getAttribute("role"), "status");
  assert.equal(el.getAttribute("aria-live"), "polite");

  applyPatches(el, [{ path: [], set_props: { message: "Deleted" } }]);
  assert.equal(el.textContent, "Deleted");
});

test("a BottomSheet is a modal dialog for assistive tech", () => {
  withDocument();
  const el = buildElement({
    type: "BottomSheet",
    key: "s1",
    props: {},
    children: [],
  });
  assert.equal(el.getAttribute("role"), "dialog");
  assert.equal(el.getAttribute("aria-modal"), "true");
});

test("the base sheet positions the overlay host and its widgets", () => {
  // Without these the layer is not a layer: the host sits in the flow after the
  // tree and everything patched into it renders inline at the end of the page.
  assert.match(BASE_THEME_CSS, /\[data-tw-overlays\]\s*\{[^}]*position:\s*fixed/);
  assert.match(BASE_THEME_CSS, /\[data-tw-overlays\]\s*\{[^}]*z-index:\s*1000/);
  assert.match(BASE_THEME_CSS, /\[data-tw-overlays\]\s*>\s*\*\s*\{\s*pointer-events:\s*auto/);
  assert.match(BASE_THEME_CSS, /\[data-tw-type="Dialog"\]\s*\{[^}]*position:\s*fixed/);
  assert.match(BASE_THEME_CSS, /\[data-tw-type="Dialog"\]\[data-tw-title\]::before/);
  assert.match(BASE_THEME_CSS, /\[data-tw-type="Toast"\]\s*\{[^}]*position:\s*fixed/);
  assert.match(BASE_THEME_CSS, /\[data-tw-type="BottomSheet"\]\s*\{[^}]*position:\s*fixed/);
  // A scrim behind a dialog, and none behind a toast (a toast is not modal).
  assert.match(BASE_THEME_CSS, /:has\(\[data-tw-type="Dialog"\]\)::before/);
});
