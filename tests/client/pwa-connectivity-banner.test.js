// Tests for client/pwa/connectivity-banner.js — P2 offline/online banner.
import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import {
  CONNECTIVITY_BANNER_ID,
  createConnectivityBanner,
  mountConnectivityBanner,
} from "../../client/pwa/connectivity-banner.js";

/** A jsdom document with an empty body. */
function freshDoc() {
  return new JSDOM("<!doctype html><body></body>").window.document;
}

/** A fake window whose online/offline listeners the test can dispatch. */
function fakeWin() {
  const listeners = {};
  return {
    addEventListener(type, fn) {
      (listeners[type] ||= new Set()).add(fn);
    },
    removeEventListener(type, fn) {
      listeners[type]?.delete(fn);
    },
    fire(type) {
      for (const fn of listeners[type] || []) fn();
    },
    count(type) {
      return (listeners[type] || new Set()).size;
    },
  };
}

test("createConnectivityBanner builds an accessible offline banner", () => {
  const doc = freshDoc();
  const banner = createConnectivityBanner(doc, { message: "Sem conexão" });
  assert.equal(banner.id, CONNECTIVITY_BANNER_ID);
  assert.equal(banner.getAttribute("role"), "status");
  assert.equal(banner.getAttribute("aria-live"), "polite");
  assert.match(banner.textContent, /Sem conexão/);
});

test("mountConnectivityBanner shows the banner when starting offline", () => {
  const doc = freshDoc();
  mountConnectivityBanner({
    document: doc,
    window: fakeWin(),
    navigator: { onLine: false },
  });
  assert.ok(doc.getElementById(CONNECTIVITY_BANNER_ID), "banner shown offline");
});

test("mountConnectivityBanner stays hidden when starting online", () => {
  const doc = freshDoc();
  mountConnectivityBanner({
    document: doc,
    window: fakeWin(),
    navigator: { onLine: true },
  });
  assert.equal(doc.getElementById(CONNECTIVITY_BANNER_ID), null);
});

test("mountConnectivityBanner reacts to offline then online transitions", () => {
  const doc = freshDoc();
  const win = fakeWin();
  const nav = { onLine: true };
  mountConnectivityBanner({ document: doc, window: win, navigator: nav });
  assert.equal(doc.getElementById(CONNECTIVITY_BANNER_ID), null, "starts online");

  nav.onLine = false;
  win.fire("offline");
  assert.ok(doc.getElementById(CONNECTIVITY_BANNER_ID), "appears when offline");

  nav.onLine = true;
  win.fire("online");
  assert.equal(doc.getElementById(CONNECTIVITY_BANNER_ID), null, "gone when online");
});

test("mountConnectivityBanner does not duplicate the banner", () => {
  const doc = freshDoc();
  const win = fakeWin();
  mountConnectivityBanner({ document: doc, window: win, navigator: { onLine: false } });
  win.fire("offline");
  assert.equal(doc.querySelectorAll(`#${CONNECTIVITY_BANNER_ID}`).length, 1);
});

test("teardown removes the banner and detaches every listener", () => {
  const doc = freshDoc();
  const win = fakeWin();
  const nav = { onLine: false };
  const teardown = mountConnectivityBanner({ document: doc, window: win, navigator: nav });
  assert.ok(doc.getElementById(CONNECTIVITY_BANNER_ID));

  teardown();
  assert.equal(doc.getElementById(CONNECTIVITY_BANNER_ID), null, "banner removed");
  assert.equal(win.count("offline"), 0, "offline listener detached");
  assert.equal(win.count("online"), 0, "online listener detached");

  win.fire("offline");
  assert.equal(doc.getElementById(CONNECTIVITY_BANNER_ID), null, "no resurrection");
});

test("mountConnectivityBanner is a no-op without a document body", () => {
  const teardown = mountConnectivityBanner({ document: null });
  assert.equal(typeof teardown, "function");
  teardown();
});
