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
  }

  /**
   * The current application state.
   * @returns {State}
   */
  get state() {
    return this._state;
  }

  /**
   * Mutate the state in place, then re-render.
   *
   * @param {(state: State) => void} mutator  Applies the state change in place.
   * @returns {void}
   */
  setState(mutator) {
    mutator(this._state);
    if (this._onSetState !== null) {
      this._onSetState();
    }
  }
}

/**
 * Walk an IR tree collecting a `key -> click handler` map.
 *
 * A handler is a node's non-wire `onClick` closure (set by `Button`, see
 * widgets.js). Rebuilt after every render so the map always points at the current
 * tree's closures.
 *
 * @param {Node} node  The root of the IR tree to walk.
 * @returns {Map<string, Function>}  Keyed click handlers.
 */
function collectHandlers(node) {
  /** @type {Map<string, Function>} */
  const handlers = new Map();
  /** @param {Node & {onClick?: ?Function}} current */
  const walk = (current) => {
    if (current.key != null && typeof current.onClick === "function") {
      handlers.set(current.key, current.onClick);
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

  /** @type {import("../transport.js").Transport} */
  const transport = {
    onPatches(handler) {
      deliver = handler;
    },
    /** @param {TWEvent} event */
    sendEvent(event) {
      if (event.key == null) {
        return;
      }
      const handler = handlers.get(event.key);
      if (typeof handler === "function") {
        handler(event);
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
  };

  const handle = mount(root, transport, node);

  return {
    root: handle.root,
    app,
    get node() {
      return node;
    },
    patchLog,
    unmount: handle.unmount,
  };
}
