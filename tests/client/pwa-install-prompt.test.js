// Tests for client/pwa/install-prompt.js — P0 soft install prompt.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  createInstallPrompt,
  isStandalone,
} from "../../client/pwa/install-prompt.js";

/**
 * A minimal window/EventTarget mock with dispatch + matchMedia.
 * @param {Object} [opts]
 * @param {boolean} [opts.standalone]
 * @param {boolean} [opts.iosStandalone]
 */
function fakeWindow(opts = {}) {
  /** @type {Record<string, Set<Function>>} */
  const listeners = {};
  return {
    navigator: { standalone: opts.iosStandalone ?? undefined },
    matchMedia(query) {
      return {
        media: query,
        matches: query.includes("standalone") ? Boolean(opts.standalone) : false,
      };
    },
    addEventListener(type, fn) {
      (listeners[type] = listeners[type] || new Set()).add(fn);
    },
    removeEventListener(type, fn) {
      listeners[type]?.delete(fn);
    },
    dispatch(type, event) {
      for (const fn of listeners[type] || []) fn(event);
    },
    listenerCount(type) {
      return listeners[type] ? listeners[type].size : 0;
    },
  };
}

/** A fake beforeinstallprompt event. */
function bipEvent(outcome = "accepted") {
  return {
    prevented: false,
    prompted: false,
    preventDefault() {
      this.prevented = true;
    },
    async prompt() {
      this.prompted = true;
    },
    userChoice: Promise.resolve({ outcome, platform: "web" }),
  };
}

test("isStandalone: detects display-mode standalone", () => {
  assert.equal(isStandalone(fakeWindow({ standalone: true })), true);
  assert.equal(isStandalone(fakeWindow()), false);
});

test("isStandalone: detects iOS navigator.standalone", () => {
  assert.equal(isStandalone(fakeWindow({ iosStandalone: true })), true);
});

test("createInstallPrompt: starts with canInstall=false", () => {
  const win = fakeWindow();
  const ctrl = createInstallPrompt({ window: win });
  assert.deepEqual(ctrl.getState(), { canInstall: false, installed: false });
});

test("createInstallPrompt: captures beforeinstallprompt and suppresses infobar", () => {
  const win = fakeWindow();
  const ctrl = createInstallPrompt({ window: win });
  const ev = bipEvent();
  win.dispatch("beforeinstallprompt", ev);
  assert.equal(ev.prevented, true, "must call preventDefault (no cold prompt)");
  assert.equal(ctrl.getState().canInstall, true);
});

test("promptInstall: returns unavailable when nothing captured", async () => {
  const ctrl = createInstallPrompt({ window: fakeWindow() });
  assert.equal(await ctrl.promptInstall(), "unavailable");
});

test("promptInstall: fires the deferred prompt and reports accepted", async () => {
  const win = fakeWindow();
  const ctrl = createInstallPrompt({ window: win });
  const ev = bipEvent("accepted");
  win.dispatch("beforeinstallprompt", ev);
  const outcome = await ctrl.promptInstall();
  assert.equal(ev.prompted, true);
  assert.equal(outcome, "accepted");
  // The deferred prompt is single-use.
  assert.equal(ctrl.getState().canInstall, false);
  assert.equal(await ctrl.promptInstall(), "unavailable");
});

test("promptInstall: reports dismissed", async () => {
  const win = fakeWindow();
  const ctrl = createInstallPrompt({ window: win });
  win.dispatch("beforeinstallprompt", bipEvent("dismissed"));
  assert.equal(await ctrl.promptInstall(), "dismissed");
});

test("appinstalled: flips installed and clears the prompt", () => {
  const win = fakeWindow();
  const ctrl = createInstallPrompt({ window: win });
  win.dispatch("beforeinstallprompt", bipEvent());
  win.dispatch("appinstalled", {});
  assert.deepEqual(ctrl.getState(), { canInstall: false, installed: true });
});

test("subscribe: notifies immediately and on change, unsubscribe stops it", () => {
  const win = fakeWindow();
  const ctrl = createInstallPrompt({ window: win });
  /** @type {InstallState[]} */
  const seen = [];
  const off = ctrl.subscribe((s) => seen.push(s));
  assert.equal(seen.length, 1, "immediate snapshot");
  win.dispatch("beforeinstallprompt", bipEvent());
  assert.equal(seen.length, 2);
  assert.equal(seen[1].canInstall, true);
  off();
  win.dispatch("appinstalled", {});
  assert.equal(seen.length, 2, "no notification after unsubscribe");
});

test("destroy: removes all window listeners", () => {
  const win = fakeWindow();
  const ctrl = createInstallPrompt({ window: win });
  assert.equal(win.listenerCount("beforeinstallprompt"), 1);
  ctrl.destroy();
  assert.equal(win.listenerCount("beforeinstallprompt"), 0);
  assert.equal(win.listenerCount("appinstalled"), 0);
});
