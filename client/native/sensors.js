// native/sensors.js — DeviceOrientation / DeviceMotion event glue for the
// sensors.orientation and sensors.motion streaming caps.
//
// These are window events (no explicit permission grant on most platforms), so
// the handlers simply attach a window listener and shape each event. Reached via
// `deps.window` (falling back to globalThis) so the router stays testable.

/**
 * Stream device orientation (compass/tilt) readings per update (T-EV).
 *
 * Each "deviceorientation" event emits
 * `{ event: {alpha, beta, gamma, absolute} }`. The returned function removes the
 * window listener.
 *
 * @param {Object} _args
 * @param {(payload:Object) => void} emit  Sink for shaped stream payloads.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void}  Teardown that removes the orientation listener.
 */
export function sensorsOrientation(_args, emit, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  const handler = (e) =>
    emit({
      event: {
        alpha: e.alpha,
        beta: e.beta,
        gamma: e.gamma,
        absolute: !!e.absolute,
      },
    });
  win.addEventListener("deviceorientation", handler);
  return () => win.removeEventListener("deviceorientation", handler);
}

/**
 * Stream device motion (accelerometer/gyroscope) readings per update (T-EV).
 *
 * Each "devicemotion" event emits `{ event: {acceleration, rotation_rate,
 * interval} }`, where acceleration is `{x, y, z}` and rotation_rate is
 * `{alpha, beta, gamma}`. The returned function removes the window listener.
 *
 * @param {Object} _args
 * @param {(payload:Object) => void} emit  Sink for shaped stream payloads.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void}  Teardown that removes the motion listener.
 */
export function sensorsMotion(_args, emit, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  const handler = (e) => {
    const a = e.acceleration || {};
    const r = e.rotationRate || {};
    emit({
      event: {
        acceleration: { x: a.x, y: a.y, z: a.z },
        rotation_rate: { alpha: r.alpha, beta: r.beta, gamma: r.gamma },
        interval: e.interval || 0,
      },
    });
  };
  win.addEventListener("devicemotion", handler);
  return () => win.removeEventListener("devicemotion", handler);
}
