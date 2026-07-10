// runtime.js — the native (no-Python) runtime for Mode C (transpile).
//
// Essentially "Mode A without Pyodide": it holds the app state, runs `view(app)`
// to produce IR, diffs successive trees in JS (client/transpile/diff.js), and
// hands the resulting patches to the SHARED renderer through the same `Transport`
// interface (client/transport.js) that Modes A/B use. The generated app module
// (e.g. client/transpile/counter.gen.js) imports { App, State } from here.
//
// Render cycle:
//   1. mountApp(root, mod) creates App(mod.makeState()) and a native transport.
//   2. node = view(app); mount(root, transport, node) builds the initial DOM.
//   3. After each render the runtime walks the IR collecting key -> click handler
//      (from each node's non-wire `onClick` field; see widgets.js).
//   4. A click -> events.js -> transport.sendEvent({type:"click", key}) -> the
//      handler for that key runs.
//   5. Handler calls app.setState(fn) -> mutates state -> re-render: next =
//      view(app); patches = diff(node, next); transport delivers them to the
//      renderer; node = next. Granular patches keep the DOM tree stable (no
//      root-Replace churn that would strand the mounted tree reference).
//
// See docs/modo-c-transpile.md for the full contract.

import { mount } from "../tempestweb.js";
import { diff } from "./diff.js";
import { NavStack, Route, routesFromPath } from "./nav.js";
import { MediaQueryData, Theme } from "./theme.js";
import { installMedia } from "./media.js";

/**
 * @typedef {import("../transport.js").Node} Node
 * @typedef {import("../transport.js").Patch} Patch
 * @typedef {import("../transport.js").TWEvent} TWEvent
 */

/**
 * Base class for transpiled `@dataclass` state objects.
 *
 * The generated module subclasses this and assigns its fields in the constructor
 * (e.g. `this.value = 0`). It carries no behavior of its own — mutation happens
 * inside `App.setState` mutators — but gives every generated state a common,
 * `instanceof`-checkable base.
 */
export class State {}

/**
 * The application handle passed to `view(app)` and closed over by handlers.
 *
 * Exposes the current `state` (read-only) and `setState(mutator)`, which mutates
 * the state in place and triggers a re-render. The re-render itself is wired by
 * {@link mountApp}, which installs the render callback — `App` stays free of any
 * renderer or DOM knowledge.
 */
export class App {
  /**
   * @param {State} state  The initial application state.
   */
  constructor(state) {
    /** @type {State} */
    this._state = state;
    /** @type {?() => void} */
    this._onSetState = null;
    /** @type {NavStack} — the navigation stack (mirrors the core App.nav). */
    this._nav = new NavStack({ stack: [new Route({ name: "/" })] });
    /** @type {Theme} — the active theme (mirrors the core App.theme). */
    this._theme = new Theme();
    /** @type {MediaQueryData} — the viewport snapshot (mirrors App.media). */
    this._media = new MediaQueryData();
  }

  /**
   * The current application state.
   * @returns {State}
   */
  get state() {
    return this._state;
  }

  /**
   * The navigation stack. `app.nav.top` is the current route.
   * @returns {NavStack}
   */
  get nav() {
    return this._nav;
  }

  /**
   * The active theme (mirrors the core App.theme).
   * @returns {Theme}
   */
  get theme() {
    return this._theme;
  }

  /**
   * The current viewport snapshot (mirrors the core App.media).
   * @returns {MediaQueryData}
   */
  get media() {
    return this._media;
  }

  /**
   * Swap the active theme and re-render.
   * @param {Theme} theme  The new theme.
   * @returns {void}
   */
  set_theme(theme) {
    this._theme = theme;
    this._rerender();
  }

  /**
   * Update the viewport snapshot and re-render (called by the runtime on a
   * `media` event from the browser).
   * @param {MediaQueryData} media  The new viewport snapshot.
   * @returns {void}
   */
  _setMedia(media) {
    this._media = media;
    this._rerender();
  }

  /**
   * Mutate the state in place, then re-render.
   *
   * @param {(state: State) => void} mutator  Applies the state change in place.
   * @returns {void}
   */
  setState(mutator) {
    mutator(this._state);
    this._rerender();
  }

  /**
   * Push a route onto the navigation stack and re-render.
   * @param {Route} route  The route to push.
   * @returns {void}
   */
  push(route) {
    this._nav = new NavStack({ stack: [...this._nav.stack, route] });
    this._rerender();
  }

  /**
   * Pop the top route (never pops the root). Re-renders when it popped.
   * @returns {boolean}  Whether a route was popped.
   */
  pop() {
    if (this._nav.stack.length <= 1) {
      return false;
    }
    this._nav = new NavStack({ stack: this._nav.stack.slice(0, -1) });
    this._rerender();
    return true;
  }

  /**
   * Replace the top route with another and re-render.
   * @param {Route} route  The replacement route.
   * @returns {void}
   */
  replace(route) {
    this._nav = new NavStack({ stack: [...this._nav.stack.slice(0, -1), route] });
    this._rerender();
  }

  /**
   * Reset the whole navigation stack (used by deep-link / back-forward).
   * @param {Route[]} routes  The new stack, root-first.
   * @returns {void}
   */
  reset(routes) {
    this._nav = new NavStack({ stack: routes });
    this._rerender();
  }

  /** Trigger the mounted re-render, if wired. @returns {void} */
  _rerender() {
    if (this._onSetState !== null) {
      this._onSetState();
    }
  }
}

/**
 * Walk an IR tree collecting an `"eventType:key" -> handler` map.
 *
 * A widget builder (see widgets.gen.js) stashes its event closures in a non-wire
 * `__handlers` map keyed by DOM event type — e.g. a Button's `{ click }`, an
 * Input's `{ input, change }`. This flattens every keyed node's `__handlers` into
 * a `"<eventType>:<key>"` lookup so the transport can dispatch by the wire event's
 * type and key. Rebuilt after every render so it always points at the current
 * tree's closures.
 *
 * @param {Node} node  The root of the IR tree to walk.
 * @returns {Map<string, Function>}  Handlers keyed by `"eventType:key"`.
 */
function collectHandlers(node) {
  /** @type {Map<string, Function>} */
  const handlers = new Map();
  /** @param {Node & {__handlers?: Object<string, ?Function>}} current */
  const walk = (current) => {
    if (current.key != null && current.__handlers != null) {
      for (const [eventType, handler] of Object.entries(current.__handlers)) {
        if (typeof handler === "function") {
          handlers.set(`${eventType}:${current.key}`, handler);
        }
      }
    }
    for (const child of current.children ?? []) {
      walk(child);
    }
  };
  walk(node);
  return handlers;
}

/**
 * @typedef {Object} TranspileModule
 * @property {() => State} makeState  Build the initial application state.
 * @property {(app: App) => Node} view  Build the IR tree from the current state.
 */

/**
 * @typedef {Object} TranspileMountHandle
 * @property {HTMLElement} root  The mounted host element.
 * @property {App} app  The live application handle.
 * @property {Node} node  The current IR tree (getter; updated each render).
 * @property {Patch[][]} patchLog  Every tick's emitted patch batch, in order.
 * @property {() => void} unmount  Tear down the app.
 */

/**
 * Mount a transpiled app onto `root`.
 *
 * Wires an `App` over `mod.makeState()` to the shared renderer via a native
 * transport: renders `mod.view(app)`, mounts it, and re-renders on every
 * `setState` by diffing the previous IR tree against the new one and delivering
 * the granular patches to the renderer. Click events resolve to the handler
 * registered for the originating widget key.
 *
 * @param {HTMLElement} root  The host element to mount into.
 * @param {TranspileModule} mod  The generated module (`makeState` + `view`).
 * @returns {TranspileMountHandle}  A handle to inspect and tear down the app.
 */
export function mountApp(root, { makeState, view }) {
  const app = new App(makeState());

  /** @type {Node} */
  let node = view(app);
  /** @type {Map<string, Function>} */
  let handlers = collectHandlers(node);
  /** @type {Patch[][]} */
  const patchLog = [];

  /** @type {?(patches: Patch[]) => void} */
  let deliver = null;
  /** @type {?(path: string) => void} — view→URL sink (wired by mount via router). */
  let navSink = null;
  // The last top-route path the URL reflects, so an imperative push/pop that
  // changes it triggers a pushState (mirrors the server session's view→URL leg).
  let lastPath = app.nav.top.name;

  /** @type {import("../transport.js").Transport} */
  const transport = {
    onPatches(handler) {
      deliver = handler;
    },
    /** Register the view→URL sink (mount wires it to the router's navigateTo). */
    onNavigate(handler) {
      navSink = handler;
    },
    /** @param {TWEvent} event */
    sendEvent(event) {
      // URL→view: a deep link / back-forward resets the nav stack from the path.
      if (event.type === "navigate") {
        const path = event.payload?.path;
        if (typeof path === "string" && path) {
          lastPath = path; // this change came FROM the URL; don't echo it back
          app.reset(routesFromPath(path));
        }
        return;
      }
      // Viewport → view: a resize / dark-mode change updates app.media.
      if (event.type === "media") {
        app._setMedia(new MediaQueryData(event.payload ?? {}));
        return;
      }
      if (event.key == null) {
        return;
      }
      const handler = handlers.get(`${event.type}:${event.key}`);
      if (typeof handler !== "function") {
        return;
      }
      // A handler may be async (e.g. `await native.http.request(...)` then
      // set_state); the re-render fires when set_state runs, after the await.
      // Swallow a rejection so an unhandled promise never crashes the tab.
      const result = handler(event);
      if (result != null && typeof result.then === "function") {
        result.then(undefined, (err) => {
          if (typeof console !== "undefined") {
            console.error("tempestweb: async handler failed", err);
          }
        });
      }
    },
    async close() {},
  };

  app._onSetState = () => {
    const next = view(app);
    const patches = diff(node, next);
    node = next;
    handlers = collectHandlers(next);
    if (patches.length > 0) {
      patchLog.push(patches);
      if (deliver !== null) {
        deliver(patches);
      }
    }
    // view→URL: if the app navigated imperatively (push/pop/replace) the top
    // path changed — tell the router to pushState the new URL.
    const path = app.nav.top.name;
    if (path !== lastPath) {
      lastPath = path;
      if (navSink !== null) {
        navSink(path);
      }
    }
  };

  const handle = mount(root, transport, node);
  // Report the viewport (size + dark mode + orientation) so the app renders
  // responsively; keeps app.media in sync on resize / color-scheme change.
  const media = installMedia(transport);

  return {
    root: handle.root,
    app,
    get node() {
      return node;
    },
    patchLog,
    unmount() {
      media.dispose();
      handle.unmount();
    },
  };
}
