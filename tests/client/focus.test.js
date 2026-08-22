// Tests for client/focus.js — the rest of the modal contract (issue #77, item 4).
// A modal used to paint over the app while focus stayed behind the scrim: Tab
// walked the page the reader could not see, and closing left focus nowhere.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { buildElement } from "../../client/dom.js";
import { installFocusTrap } from "../../client/focus.js";

/** Build the app tree (a button that "opens" the overlay) plus an overlay host. */
function scene(dom) {
  const tree = buildElement({
    type: "Column",
    key: "root",
    props: {},
    children: [{ type: "Button", key: "open", props: { label: "Open" }, children: [] }],
  });
  dom.root.appendChild(tree);
  const host = dom.document.createElement("div");
  host.setAttribute("data-tw-overlays", "");
  dom.root.appendChild(host);
  return { tree, host };
}

/** Mount a Dialog with `n` buttons inside `host` and return it. */
function openDialog(dom, host, labels = ["Cancel", "Confirm"]) {
  const dialog = buildElement({
    type: "Dialog",
    key: "dlg",
    props: { title: "Sure?" },
    children: labels.map((label, index) => ({
      type: "Button",
      key: `b${index}`,
      props: { label },
      children: [],
    })),
  });
  host.appendChild(dialog);
  return dialog;
}

/** Press Tab (or Shift+Tab) on the document. */
function tab(dom, { shift = false } = {}) {
  dom.document.dispatchEvent(
    new dom.window.KeyboardEvent("keydown", { key: "Tab", shiftKey: shift, bubbles: true }),
  );
}

test("opening a modal moves focus into it", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);
  trap.sync();

  const opener = dom.root.querySelector("[data-tw-key=\"open\"]");
  opener.focus();
  assert.equal(dom.document.activeElement, opener);

  openDialog(dom, host);
  trap.sync();

  const cancel = host.querySelector("[data-tw-key=\"b0\"]");
  assert.equal(dom.document.activeElement, cancel, "focus lands on the first control");
  trap.dispose();
});

test("a modal with nothing focusable holds focus itself", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);
  const dialog = openDialog(dom, host, []);
  trap.sync();

  assert.equal(dialog.getAttribute("tabindex"), "-1");
  assert.equal(dom.document.activeElement, dialog);
  trap.dispose();
});

test("Tab wraps at the end of the modal instead of leaving it", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);
  const dialog = openDialog(dom, host);
  trap.sync();

  const [first, last] = [
    dialog.querySelector("[data-tw-key=\"b0\"]"),
    dialog.querySelector("[data-tw-key=\"b1\"]"),
  ];
  last.focus();
  tab(dom);
  assert.equal(dom.document.activeElement, first, "Tab from the last control wraps");

  first.focus();
  tab(dom, { shift: true });
  assert.equal(dom.document.activeElement, last, "Shift+Tab from the first wraps back");
  trap.dispose();
});

test("Tab from outside the modal is pulled back in", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);
  const dialog = openDialog(dom, host);
  trap.sync();

  // The page behind the scrim: focus there is exactly what the trap exists for.
  const behind = dom.root.querySelector("[data-tw-key=\"open\"]");
  behind.focus();
  tab(dom);

  assert.ok(dialog.contains(dom.document.activeElement), "focus returns to the modal");
  trap.dispose();
});

test("Tab in the middle of the modal is left alone", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);
  const dialog = openDialog(dom, host, ["A", "B", "C"]);
  trap.sync();

  const middle = dialog.querySelector("[data-tw-key=\"b1\"]");
  middle.focus();
  tab(dom);
  assert.equal(
    dom.document.activeElement,
    middle,
    "the browser's own Tab order handles the interior",
  );
  trap.dispose();
});

test("closing the modal gives focus back to what opened it", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);

  const opener = dom.root.querySelector("[data-tw-key=\"open\"]");
  opener.focus();
  const dialog = openDialog(dom, host);
  trap.sync();
  assert.notEqual(dom.document.activeElement, opener);

  dialog.remove();
  trap.sync();
  assert.equal(dom.document.activeElement, opener, "the reader lands back where they were");
  trap.dispose();
});

test("closing does not chase an opener the same batch removed", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { tree, host } = scene(dom);
  const trap = installFocusTrap(dom.root);

  const opener = dom.root.querySelector("[data-tw-key=\"open\"]");
  opener.focus();
  const dialog = openDialog(dom, host);
  trap.sync();

  tree.remove();
  dialog.remove();
  trap.sync();
  assert.equal(dom.document.activeElement, dom.document.body, "no throw, no stale focus");
  trap.dispose();
});

test("a non-modal overlay does not steal focus", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);

  const opener = dom.root.querySelector("[data-tw-key=\"open\"]");
  opener.focus();
  const menu = buildElement({
    type: "Menu",
    key: "menu",
    props: { items: [{ label: "Rename", value: "rename" }] },
    children: [],
  });
  host.appendChild(menu);
  trap.sync();

  assert.equal(dom.document.activeElement, opener, "a Menu has no scrim to trap behind");
  trap.dispose();
});

test("dispose stops trapping", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);
  const dialog = openDialog(dom, host);
  trap.sync();
  trap.dispose();

  const last = dialog.querySelector("[data-tw-key=\"b1\"]");
  last.focus();
  tab(dom);
  assert.equal(dom.document.activeElement, last, "the trap no longer intervenes");
});

test("a stacked modal takes over, and closing it returns to the one below", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);

  const first = openDialog(dom, host, ["Below"]);
  trap.sync();
  const below = first.querySelector("[data-tw-key=\"b0\"]");
  assert.equal(dom.document.activeElement, below);

  // Overlays stack in document order, so the second one is on top and owns the
  // keyboard while it is open.
  const second = openDialog(dom, host, ["Above"]);
  second.setAttribute("data-tw-key", "dlg2");
  trap.sync();
  assert.ok(second.contains(dom.document.activeElement), "the top modal takes over");

  second.remove();
  trap.sync();
  assert.ok(
    first.contains(dom.document.activeElement),
    "closing it hands the keyboard back to the modal below, not to the page",
  );
  trap.dispose();
});

test("a hidden control is not a tab stop", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);
  const dialog = openDialog(dom, host, ["Hidden", "Real"]);
  const hidden = dialog.querySelector("[data-tw-key=\"b0\"]");
  hidden.setAttribute("hidden", "");
  trap.sync();

  assert.equal(
    dom.document.activeElement,
    dialog.querySelector("[data-tw-key=\"b1\"]"),
    "focus skips the control the app hid",
  );
  trap.dispose();
});

test("an editable region counts as a tab stop", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const { host } = scene(dom);
  const trap = installFocusTrap(dom.root);
  const dialog = openDialog(dom, host, []);
  const editable = dom.document.createElement("div");
  editable.setAttribute("contenteditable", "true");
  dialog.appendChild(editable);
  trap.sync();

  // A note editor inside a dialog is the whole reason the dialog is modal.
  assert.equal(dom.document.activeElement, editable);
  trap.dispose();
});
