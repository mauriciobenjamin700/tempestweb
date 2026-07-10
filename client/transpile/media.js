// media.js — viewport → app reporting for Mode C responsiveness.
//
// The browser owns the viewport; the app reads it via `app.media`. This reports
// the current size, dark-mode preference and orientation to the runtime as a
// `media` event on mount and on every resize / color-scheme change, so the app
// re-renders responsively (breakpoints, dark/light). No-op without a window.
//
// Reported as `{ type: "media", key: "", payload: {width, height,
// device_pixel_ratio, platform_dark_mode, orientation} }`, handled by the Mode C
// runtime before handler resolution (like the `navigate` event).

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
 * Install viewport reporting on `win`.
 *
 * Sends the current snapshot immediately (so the first render is responsive) and
 * on every `resize` and `prefers-color-scheme` change. No-ops without a window.
 *
 * @param {import("../transport.js").Transport} transport  The event sink.
 * @param {Window} [win]  The window to bind (defaults to the global).
 * @returns {{dispose: () => void}}  Removes the listeners.
 */
export function installMedia(transport, win) {
  const target = win ?? (typeof window !== "undefined" ? window : null);
  if (target == null) {
    return { dispose() {} };
  }

  const report = () => {
    transport.sendEvent({ type: "media", key: "", payload: snapshot(target) });
  };

  report();
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
      target.removeEventListener("resize", report);
      if (darkQuery && typeof darkQuery.removeEventListener === "function") {
        darkQuery.removeEventListener("change", report);
      }
    },
  };
}
