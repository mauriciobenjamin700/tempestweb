// Tests for client/pwa/post-install-redirect.js — P0 post-install overlay.
import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import {
  POST_INSTALL_OVERLAY_ID,
  createPostInstallOverlay,
  mountPostInstallRedirect,
} from "../../client/pwa/post-install-redirect.js";

function freshDoc() {
  return new JSDOM("<!doctype html><body></body>").window.document;
}

/** A window whose appinstalled listeners the test can fire. */
function fakeWin(opts = {}) {
  const listeners = {};
  return {
    navigator: { standalone: opts.standalone ?? undefined },
    matchMedia: () => ({ matches: Boolean(opts.standalone) }),
    close: opts.close,
    addEventListener(t, fn) {
      (listeners[t] ||= new Set()).add(fn);
    },
    removeEventListener(t, fn) {
      listeners[t]?.delete(fn);
    },
    fire(t) {
      for (const fn of listeners[t] || []) fn();
    },
    count(t) {
      return (listeners[t] || new Set()).size;
    },
  };
}

test("createPostInstallOverlay builds a modal overlay with a button", () => {
  const doc = freshDoc();
  const o = createPostInstallOverlay(doc, { message: "Instalado", buttonLabel: "Abrir" });
  assert.equal(o.id, POST_INSTALL_OVERLAY_ID);
  assert.equal(o.getAttribute("role"), "dialog");
  assert.match(o.textContent, /Instalado/);
  assert.equal(o.querySelector("button").textContent, "Abrir");
});

test("mountPostInstallRedirect shows the overlay on appinstalled", () => {
  const doc = freshDoc();
  const win = fakeWin();
  mountPostInstallRedirect({ document: doc, window: win });
  assert.equal(doc.getElementById(POST_INSTALL_OVERLAY_ID), null, "hidden until installed");
  win.fire("appinstalled");
  assert.ok(doc.getElementById(POST_INSTALL_OVERLAY_ID), "shown after appinstalled");
});

test("the overlay button best-effort closes the tab", () => {
  const doc = freshDoc();
  let closed = false;
  const win = fakeWin({ close: () => (closed = true) });
  mountPostInstallRedirect({ document: doc, window: win });
  win.fire("appinstalled");
  doc.getElementById(POST_INSTALL_OVERLAY_ID).querySelector("button").click();
  assert.equal(closed, true);
});

test("mountPostInstallRedirect is a no-op when already standalone", () => {
  const doc = freshDoc();
  const win = fakeWin({ standalone: true });
  mountPostInstallRedirect({ document: doc, window: win });
  win.fire("appinstalled");
  assert.equal(doc.getElementById(POST_INSTALL_OVERLAY_ID), null, "no overlay in the installed app");
});

test("teardown removes the overlay and the listener", () => {
  const doc = freshDoc();
  const win = fakeWin();
  const teardown = mountPostInstallRedirect({ document: doc, window: win });
  win.fire("appinstalled");
  assert.ok(doc.getElementById(POST_INSTALL_OVERLAY_ID));
  teardown();
  assert.equal(doc.getElementById(POST_INSTALL_OVERLAY_ID), null);
  assert.equal(win.count("appinstalled"), 0);
});
