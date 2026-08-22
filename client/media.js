// media.js — viewport → app reporting, shared by every mode.
//
// The browser owns the viewport; the app reads it via `app.media`, and a `view`
// that branches on `media.width` (a column on a phone, a row on a laptop) or
// bounds itself by `media.height` (a Scaffold whose bars must not scroll away)
// is only correct while that snapshot is current. This reports the size, pixel
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
// It lived under client/transpile/ and was installed by the Mode C runtime
// alone, which is why a Mode B app ran forever with width = height = 0 (#74).
// mount() installs it now, so all three modes report.

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
 * @param {import("./transport.js").Transport} transport  The event sink.
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
