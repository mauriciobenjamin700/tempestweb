// media.js — viewport → app reporting, shared by every mode.
//
// The browser owns the viewport; the app reads it via `app.media`, and a `view`
// that branches on `media.width` (a column on a phone, a row on a laptop) or
// bounds itself by `media.height` (a Scaffold whose bars must not scroll away) is
// only correct while that snapshot is current. This reports the size, pixel
// ratio, dark-mode preference and orientation on mount and on every resize /
// color-scheme change. No-op without a window.
//
// Reported as `{ type: "media", key: "", payload: {width, height,
// device_pixel_ratio, platform_dark_mode, orientation} }` and handled before
// handler resolution (like `navigate`): in Mode C by the JS runtime, in Modes A
// and B by `apply_media`, which builds a `MediaQueryData` and hands it to
// `App._update_media` — the same call the docstring of `MediaQueryData` always
// promised a renderer would make.
//
// It lived under client/transpile/ and was installed by the Mode C runtime alone,
// which is why a Mode B app ran forever with width = height = 0 (#74). mount()
// installs it now, so all three modes report.
//
// Reports are coalesced to one per animation frame and dropped when the snapshot
// is unchanged. `resize` fires continuously while a window edge is dragged, and
// in Mode B each report is a socket round-trip plus a rebuild and a diff — the
// unthrottled stream that is free in Mode C is not free there.

/**
 * Read the current viewport snapshot from a window.
 * @param {Window} win
 * @returns {{width: number, height: number, device_pixel_ratio: number,
 *            platform_dark_mode: boolean, orientation: string}}
 */
function snapshot(win) {
  const width = win.innerWidth || 0;
  const height = win.innerHeight || 0;
  const dark =
    typeof win.matchMedia === "function" &&
    win.matchMedia("(prefers-color-scheme: dark)").matches;
  return {
    width,
    height,
    device_pixel_ratio: win.devicePixelRatio || 1,
    platform_dark_mode: Boolean(dark),
    orientation: height >= width ? "portrait" : "landscape",
  };
}

/**
 * Whether two snapshots describe the same environment.
 * @param {ReturnType<typeof snapshot> | null} a
 * @param {ReturnType<typeof snapshot>} b
 * @returns {boolean}
 */
function same(a, b) {
  return (
    a != null &&
    a.width === b.width &&
    a.height === b.height &&
    a.device_pixel_ratio === b.device_pixel_ratio &&
    a.platform_dark_mode === b.platform_dark_mode &&
    a.orientation === b.orientation
  );
}

/**
 * Pick the frame scheduler a window offers, newest first.
 *
 * Prefers `requestAnimationFrame`, falls back to `setTimeout`, and degrades to
 * running the callback inline when the window has neither — a bare test double
 * or a non-browser host still reports, it just does not coalesce.
 *
 * @param {Window} target
 * @returns {[(fn: () => void) => number, (id: number) => void]}
 */
function scheduler(target) {
  if (typeof target.requestAnimationFrame === "function") {
    const cancel =
      typeof target.cancelAnimationFrame === "function"
        ? target.cancelAnimationFrame.bind(target)
        : () => {};
    return [target.requestAnimationFrame.bind(target), cancel];
  }
  if (typeof target.setTimeout === "function") {
    const cancel =
      typeof target.clearTimeout === "function"
        ? target.clearTimeout.bind(target)
        : () => {};
    return [(fn) => target.setTimeout(fn, 16), cancel];
  }
  return [
    (fn) => {
      fn();
      return 0;
    },
    () => {},
  ];
}

/**
 * Install viewport reporting on `win`.
 *
 * Sends the current snapshot immediately, so the first render is already
 * responsive, and then on every `resize` and `prefers-color-scheme` change.
 * Bursts collapse to one report per animation frame, and a frame whose snapshot
 * equals the last one sent reports nothing. No-ops without a window.
 *
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @param {Window} [win]  The window to bind (defaults to the global).
 * @returns {{dispose: () => void}}  Removes the listeners.
 */
export function installMedia(transport, win) {
  const target = win ?? (typeof window !== "undefined" ? window : null);
  if (target == null) {
    return { dispose() {} };
  }

  let last = null;
  let frame = 0;
  const [schedule, unschedule] = scheduler(target);

  const send = () => {
    const next = snapshot(target);
    if (same(last, next)) {
      return;
    }
    last = next;
    transport.sendEvent({ type: "media", key: "", payload: next });
  };

  const report = () => {
    if (frame !== 0) {
      return;
    }
    frame = schedule(() => {
      frame = 0;
      send();
    });
  };

  send();
  target.addEventListener("resize", report);
  const darkQuery =
    typeof target.matchMedia === "function"
      ? target.matchMedia("(prefers-color-scheme: dark)")
      : null;
  if (darkQuery && typeof darkQuery.addEventListener === "function") {
    darkQuery.addEventListener("change", report);
  }

  return {
    dispose() {
      if (frame !== 0) {
        unschedule(frame);
        frame = 0;
      }
      target.removeEventListener("resize", report);
      if (darkQuery && typeof darkQuery.removeEventListener === "function") {
        darkQuery.removeEventListener("change", report);
      }
    },
  };
}
