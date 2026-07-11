// native/idle.js — Idle Detection API glue for the idle.watch streaming cap.
//
// `new IdleDetector()` fires "change" events carrying userState ("active"/"idle")
// and screenState ("locked"/"unlocked"). `start({threshold, signal})` begins
// detection; aborting the passed AbortSignal both stops detection and (because the
// listener is bound to the same signal) removes the "change" listener. The
// returned teardown is synchronous even though `start` is async.

import { CapabilityError } from "./index.js";

/**
 * Watch the user's idle state, streaming a shaped payload per change (T-EV).
 *
 * Each transition emits `{ event: {user, screen} }`. If `start` rejects (e.g.
 * permission denied), emits `{ error: "unavailable" }`. The returned function
 * aborts the AbortController handed to `start`, tearing down the detector.
 *
 * @param {{threshold_seconds?:number}} args
 * @param {(payload:Object) => void} emit  Sink for shaped stream payloads.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void}  Teardown that aborts the idle detector.
 * @throws {CapabilityError} unavailable — when the Idle Detection API is absent.
 */
export function idleWatch(args, emit, deps) {
  const Ctor = deps.IdleDetector || /** @type {any} */ (globalThis).IdleDetector;
  if (!Ctor) {
    throw new CapabilityError("unavailable", "the Idle Detection API is not available");
  }
  const controller = new (deps.AbortController || /** @type {any} */ (globalThis).AbortController)();
  const d = new Ctor();
  d.addEventListener(
    "change",
    () => emit({ event: { user: d.userState, screen: d.screenState } }),
    { signal: controller.signal },
  );
  Promise.resolve(
    d.start({ threshold: (args.threshold_seconds || 60) * 1000, signal: controller.signal }),
  ).catch((err) => {
    emit({ error: "unavailable", message: (err && err.message) || "" });
  });
  return () => controller.abort();
}
