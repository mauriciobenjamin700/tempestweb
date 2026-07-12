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

/**
 * Resolve a URL (path + optional query) into a navigation stack.
 *
 * Mirrors `tempestweb.runtime.routing.path_to_routes` (Modes A/B): the path
 * builds the cumulative back stack; a query string, when present, is parsed into
 * the top route's `params` so the linked screen receives them (deep link /
 * reload). Query values are strings.
 *
 * @param {string} url  The browser URL, e.g. `"/shop/item?ref=home"`.
 * @returns {Route[]}  Routes from the root to the linked screen; the top route
 *   carries the parsed query params.
 */
export function pathToRoutes(url) {
  const [path, query = ""] = String(url).split("?");
  const routes = routesFromPath(path);
  if (query) {
    const params = {};
    for (const [key, value] of new URLSearchParams(query)) params[key] = value;
    const top = routes[routes.length - 1];
    routes[routes.length - 1] = new Route({
      name: top.name,
      params: { ...top.params, ...params },
    });
  }
  return routes;
}

/**
 * Serialize a route to a URL path, encoding `params` as the query string.
 *
 * Mirrors `tempestweb.runtime.routing.route_to_path`: `name` when it has no
 * params, else `name?k=v&...` with the params URL-encoded (values as strings).
 *
 * @param {Route} route  The route to serialize (typically `app.nav.top`).
 * @returns {string}  The URL path.
 */
export function routeToPath(route) {
  const params = route.params ?? {};
  const keys = Object.keys(params);
  if (keys.length === 0) return route.name;
  const query = new URLSearchParams();
  for (const key of keys) query.set(key, String(params[key]));
  return `${route.name}?${query.toString()}`;
}
