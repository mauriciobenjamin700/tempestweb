// Tests for client/sw/register.js — P1 register + update lifecycle.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  registerServiceWorker,
  skipWaiting,
  unregisterAllServiceWorkers,
  isServiceWorkerSupported,
} from "../../client/sw/register.js";

/** Minimal EventTarget-ish mock with addEventListener + dispatch. */
function emitter() {
  const listeners = {};
  return {
    addEventListener(type, fn) {
      (listeners[type] ??= []).push(fn);
    },
    dispatch(type, evt) {
      for (const fn of listeners[type] ?? []) fn(evt ?? {});
    },
  };
}

/** A mock waiting/installing worker tracking posted messages and state. */
function workerMock(state = "installing") {
  const e = emitter();
  return Object.assign(e, {
    state,
    posted: [],
    postMessage(msg) {
      this.posted.push(msg);
    },
    setState(s) {
      this.state = s;
      e.dispatch("statechange");
    },
  });
}

/** A mock registration with updatefound support. */
function registrationMock({ waiting = null, installing = null } = {}) {
  const e = emitter();
  return Object.assign(e, {
    waiting,
    installing,
    unregister: async () => true,
  });
}

/** A mock ServiceWorkerContainer. */
function containerMock({ controller = null, registration } = {}) {
  const e = emitter();
  return Object.assign(e, {
    controller,
    registered: [],
    async register(url, opts) {
      this.registered.push({ url, opts });
      return registration;
    },
    async getRegistrations() {
      return [registration];
    },
  });
}

test("isServiceWorkerSupported: container override is supported", () => {
  assert.equal(isServiceWorkerSupported({}), true);
});

test("registerServiceWorker: returns null when unsupported", async () => {
  const reg = await registerServiceWorker({ container: null });
  // container:null still falls through to navigator (absent in node) -> null.
  assert.equal(reg, null);
});

test("registerServiceWorker: registers at the given url", async () => {
  const registration = registrationMock();
  const container = containerMock({ registration });
  const reg = await registerServiceWorker({ url: "/sw.js", container });
  assert.equal(reg, registration);
  assert.equal(container.registered[0].url, "/sw.js");
});

test("registerServiceWorker: fires onUpdate when a worker is already waiting", async () => {
  const registration = registrationMock({ waiting: workerMock("installed") });
  const container = containerMock({ controller: {}, registration });
  let updated = null;
  await registerServiceWorker({ container, onUpdate: (r) => (updated = r) });
  assert.equal(updated, registration);
});

test("registerServiceWorker: updatefound -> installed -> onUpdate (controlled)", async () => {
  const registration = registrationMock();
  const container = containerMock({ controller: {}, registration });
  let updated = null;
  let ready = null;
  await registerServiceWorker({
    container,
    onUpdate: (r) => (updated = r),
    onReady: (r) => (ready = r),
  });
  const installing = workerMock("installing");
  registration.installing = installing;
  registration.dispatch("updatefound");
  installing.setState("installed");
  assert.equal(updated, registration);
  assert.equal(ready, null);
});

test("registerServiceWorker: first install -> onReady (no controller)", async () => {
  const registration = registrationMock();
  const container = containerMock({ controller: null, registration });
  let updated = null;
  let ready = null;
  await registerServiceWorker({
    container,
    onUpdate: (r) => (updated = r),
    onReady: (r) => (ready = r),
  });
  const installing = workerMock("installing");
  registration.installing = installing;
  registration.dispatch("updatefound");
  installing.setState("installed");
  assert.equal(ready, registration);
  assert.equal(updated, null);
});

test("registerServiceWorker: onError on failure, returns null", async () => {
  const container = emitter();
  container.register = async () => {
    throw new Error("boom");
  };
  let err = null;
  const reg = await registerServiceWorker({ container, onError: (e) => (err = e) });
  assert.equal(reg, null);
  assert.equal(err.message, "boom");
});

test("skipWaiting: posts SKIP_WAITING and reloads once on controllerchange", () => {
  const waiting = workerMock("installed");
  const registration = registrationMock({ waiting });
  const container = containerMock({ registration });
  let reloads = 0;
  skipWaiting(registration, { container, reload: () => (reloads += 1) });
  assert.deepEqual(waiting.posted, [{ type: "SKIP_WAITING" }]);
  container.dispatch("controllerchange");
  container.dispatch("controllerchange"); // second event must not double-reload
  assert.equal(reloads, 1);
});

test("skipWaiting: no-op when nothing is waiting", () => {
  const registration = registrationMock({ waiting: null });
  let reloads = 0;
  skipWaiting(registration, { container: containerMock({ registration }), reload: () => (reloads += 1) });
  assert.equal(reloads, 0);
});

test("unregisterAllServiceWorkers: removes registrations and counts them", async () => {
  const registration = registrationMock();
  const container = containerMock({ registration });
  const removed = await unregisterAllServiceWorkers(container);
  assert.equal(removed, 1);
});
