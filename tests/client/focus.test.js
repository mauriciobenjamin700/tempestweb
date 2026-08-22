// Tests for client/focus.js — the focus half of the modal contract.
//
// A modal already had role=dialog, aria-modal, a scrim and a dismiss. What it did
// not have was the keyboard: focus stayed on the opener, so Tab walked the page
// behind the scrim. These pin the three obligations that closes — take focus,
// keep it, give it back.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { installFocusTrap } from "../../client/focus.js";

/**
 * A page with an opener button and a lazily-attached overlay host.
 * @returns {{doc: Document, win: Window, root: HTMLElement, opener: HTMLElement,
 *            host: () => (HTMLElement|null), openModal: (type?: string,
 *            buttons?: string[]) => HTMLElement, closeAll: () => void,
 *            tab: (shift?: boolean) => boolean}}
 */
function page() {
  const dom = freshDom();
  const doc = dom.document;
  const opener = doc.createElement("button");
  opener.textContent = "Open";
  dom.root.appendChild(opener);

  let overlayRoot = null;
  const host = () => overlayRoot;

  return {
    doc,
    win: dom.window,
    root: dom.root,
    opener,
    host,
    openModal(type = "Dialog", buttons = ["OK", "Cancel"]) {
      if (overlayRoot === null) {
        overlayRoot = doc.createElement("div");
        overlayRoot.setAttribute("data-tw-overlays", "");
        dom.root.appendChild(overlayRoot);
      }
      const modal = doc.createElement("div");
      modal.setAttribute("data-tw-type", type);
      for (const label of buttons) {
        const b = doc.createElement("button");
        b.textContent = label;
        modal.appendChild(b);
      }
      overlayRoot.appendChild(modal);
      return modal;
    },
    closeAll() {
      if (overlayRoot !== null) {
        overlayRoot.innerHTML = "";
      }
    },
    /**
     * Dispatch a Tab keydown and report whether it was prevented.
     * @param {boolean} [shift]
     */
    tab(shift = false) {
      const event = new dom.window.KeyboardEvent("keydown", {
        key: "Tab",
        shiftKey: shift,
        bubbles: true,
        cancelable: true,
      });
      doc.dispatchEvent(event);
      return event.defaultPrevented;
    },
  };
}

test("opening a modal moves focus into it", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  p.opener.focus();
  assert.equal(p.doc.activeElement, p.opener);

  const modal = p.openModal();
  trap.sync();

  assert.equal(p.doc.activeElement, modal.firstChild, "the first tabbable takes it");
});

test("Tab past the last stop wraps to the first", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  const modal = p.openModal("Dialog", ["OK", "Cancel"]);
  trap.sync();
  const [ok, cancel] = Array.from(modal.children);
  cancel.focus();

  const prevented = p.tab();

  assert.equal(prevented, true, "the browser's own move was replaced");
  assert.equal(p.doc.activeElement, ok);
});

test("Shift+Tab before the first stop wraps to the last", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  const modal = p.openModal("BottomSheet", ["One", "Two", "Three"]);
  trap.sync();
  const stops = Array.from(modal.children);
  stops[0].focus();

  const prevented = p.tab(true);

  assert.equal(prevented, true);
  assert.equal(p.doc.activeElement, stops[stops.length - 1]);
});

test("Tab from outside the modal is pulled back in", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  const modal = p.openModal();
  trap.sync();
  // Whatever put focus behind the scrim — a stray script, a click that slipped
  // through — the next Tab belongs to the modal.
  p.opener.focus();

  const prevented = p.tab();

  assert.equal(prevented, true);
  assert.equal(p.doc.activeElement, modal.firstChild);
});

test("a modal with nothing tabbable still takes the keyboard", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  const modal = p.openModal("Dialog", []);
  trap.sync();

  assert.equal(modal.getAttribute("tabindex"), "-1");
  assert.equal(p.doc.activeElement, modal);
  assert.equal(p.tab(), true, "Tab has nowhere to go, so it goes nowhere");
});

test("closing the last modal gives focus back to the opener", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  p.opener.focus();
  p.openModal();
  trap.sync();

  p.closeAll();
  trap.sync();

  assert.equal(p.doc.activeElement, p.opener);
});

test("a stacked modal takes over, and closing it returns to the one below", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  p.opener.focus();
  const first = p.openModal("Dialog", ["Back"]);
  trap.sync();
  const second = p.openModal("ActionSheet", ["Confirm"]);
  trap.sync();

  assert.equal(p.doc.activeElement, second.firstChild, "the top one owns it");

  second.remove();
  trap.sync();

  assert.equal(p.doc.activeElement, first.firstChild, "not the opener, the one below");
});

test("a Menu is not trapped: it is anchored, not modal", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  p.opener.focus();
  p.openModal("Menu", ["Copy"]);
  trap.sync();

  assert.equal(p.doc.activeElement, p.opener, "focus stayed where it was");
  assert.equal(p.tab(), false, "and Tab is the browser's again");
});

test("dispose stops trapping", () => {
  const p = page();
  const trap = installFocusTrap(p.host, p.doc);
  p.openModal();
  trap.sync();

  trap.dispose();

  assert.equal(p.tab(), false);
});

test("no document is a no-op, not a crash", () => {
  const trap = installFocusTrap(() => null, null);
  trap.sync();
  trap.dispose();
});
