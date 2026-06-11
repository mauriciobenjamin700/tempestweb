// router.js — URL ↔ navigation bridge (deep links + back/forward).  PHASE E.1.
//
// The browser owns the URL; the Python app owns the navigation stack. This module
// reports the document path to Python so `view` can render the linked screen:
//   - on mount, the initial path (a deep link / bookmark);
//   - on `popstate` (back/forward), the new path.
// Python resolves the path to a route stack (routes_from_path) and re-renders.
// Reported as a `navigate` wire event { type:"navigate", key:"", payload:{path} },
// special-cased by the runtime before handler resolution.
//
// Note: the reverse direction (pushState when the app navigates imperatively)
// needs a server→client nav envelope and is a follow-up; today the URL drives the
// view (deep links + back/forward), not the other way around.

/**
 * Install URL→navigation reporting on `window`.
 *
 * Sends the current path immediately (so a deep-linked load opens the right
 * screen) and on every `popstate`. No-ops when there is no `window` (tests).
 *
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @param {Window} [win]  The window to bind (defaults to the global).
 * @returns {{dispose: () => void}}  `dispose` removes the popstate listener.
 */
export function installRouter(transport, win) {
  const target = win ?? (typeof window !== "undefined" ? window : null);
  if (target == null) {
    return { dispose() {} };
  }

  const report = () => {
    const path = target.location?.pathname || "/";
    transport.sendEvent({ type: "navigate", key: "", payload: { path } });
  };

  // Deep link on load, then every back/forward.
  report();
  target.addEventListener("popstate", report);
  return {
    dispose() {
      target.removeEventListener("popstate", report);
    },
  };
}
