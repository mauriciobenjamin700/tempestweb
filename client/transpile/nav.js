// nav.js — Mode C navigation primitives (a port of tempest_core.navigation).
//
// Route + NavStack + routesFromPath mirror the core so a transpiled app uses the
// same navigation API as Modes A/B: `app.push(Route(name=...))`, `app.pop()`,
// `app.nav.top`. The runtime (runtime.js) syncs this stack with the browser URL
// via client/router.js — a `navigate` event resets the stack from the path
// (deep link / back-forward), and an imperative push/pop pushes the new URL.
//
// Route is kept strictly at parity with the core (name + params) — the transpile
// build validates the app by rendering it through the *real* core, so a Mode
// C-only Route attribute would break `build --mode transpile`. Query/path params
// live in the route `name` (the full path), exactly as the core models them.
//
// See docs/native-modo-c.md (navigation) and tempest_core/navigation.py.

/**
 * A single navigation route — a name (path) plus optional params.
 *
 * Mirrors `tempest_core.navigation.Route`: `name` is the cumulative path and
 * `params` the explicit params dict. Kept at strict parity so the same `view`
 * runs under Modes A/B/C.
 */
export class Route {
  /**
   * @param {{name: string, params?: Object<string, *>}} args
   */
  constructor({ name, params = {} } = { name: "/" }) {
    this.name = name;
    this.params = params;
  }
}

/**
 * A navigation stack of {@link Route}s. Mirrors `tempest_core.navigation.NavStack`.
 */
export class NavStack {
  /**
   * @param {{stack?: Route[]}} [args]
   */
  constructor({ stack } = {}) {
    /** @type {Route[]} */
    this.stack = stack && stack.length ? stack : [new Route({ name: "/" })];
  }

  /** The current (top) route. @returns {Route} */
  get top() {
    return this.stack[this.stack.length - 1];
  }
}

/**
 * Resolve a deep-link path into a cumulative navigation stack.
 *
 * A faithful port of `tempest_core.navigation.routes_from_path`: split on `/`
 * into cumulative segments, so `"/a/b"` opens `["/", "/a", "/a/b"]`.
 *
 * @param {string} path  The deep-link path (e.g. `"/shop/item"`).
 * @returns {Route[]}  A non-empty list of routes from the root to the screen.
 */
export function routesFromPath(path) {
  const segments = String(path)
    .split("/")
    .filter((segment) => segment);
  const routes = [new Route({ name: "/" })];
  let accumulated = "";
  for (const segment of segments) {
    accumulated = `${accumulated}/${segment}`;
    routes.push(new Route({ name: accumulated }));
  }
  return routes;
}

// Python-name alias so a transpiled `from tempest_core import routes_from_path`
// resolves without a rename.
export { routesFromPath as routes_from_path };
