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
// Reverse direction (view → URL): when the app navigates imperatively (app.push /
// pop / reset inside a handler), the Python side emits a `navigate` envelope with
// the new path; the bootstrap routes it to `navigateTo`, which `pushState`s the
// URL so back/forward + bookmarks stay correct. pushState does NOT fire popstate,
// so this never echoes back as a navigate event; and a no-op when the path
// already matches the URL (which is the case right after a URL → view round-trip).

/**
 * Install URL→navigation reporting on `window`.
 *
 * Sends the current path immediately (so a deep-linked load opens the right
 * screen) and on every `popstate`. No-ops when there is no `window` (tests).
 *
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @param {Window} [win]  The window to bind (defaults to the global).
 * @returns {{dispose: () => void, navigateTo: (path: string) => void}}
 *          `dispose` removes the popstate listener; `navigateTo` pushes a new URL
 *          when the app navigates (view → URL), guarded against echoing back.
 */
export function installRouter(transport, win) {
  const target = win ?? (typeof window !== "undefined" ? window : null);
  if (target == null) {
    return { dispose() {}, navigateTo() {} };
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

    /**
     * Sync the browser URL to a path the app navigated to (view → URL).
     *
     * No-op when the URL already matches `path` — which is exactly the case
     * right after a URL → view round-trip (deep link / back-forward), so the
     * server's confirming `navigate` envelope never adds a duplicate history
     * entry. `pushState` does not fire `popstate`, so this never re-reports.
     *
     * @param {string} path  The new top-route path (e.g. "/settings").
     * @returns {void}
     */
    navigateTo(path) {
      if (typeof path !== "string" || !path) return;
      const current = target.location?.pathname || "/";
      if (path === current) return;
      target.history?.pushState({}, "", path);
    },
  };
}
