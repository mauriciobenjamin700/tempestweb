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
import { applyThemeMode } from "../theme.js";
import { diff } from "./diff.js";
import { NavStack, Route, pathToRoutes, routeToPath } from "./nav.js";
import { MediaQueryData, Theme } from "./theme.js";
import { setSlidWindows } from "./widget-support.js";
// `Form.validate` is the one widget *method* Mode C ports, and the emitted code
// reaches every helper through this module — so it is re-exported here rather
// than given a second import site.
export { formValidate } from "./widget-support.js";

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
 * Mark the document with a theme's resolved mode, for the base stylesheet.
 *
 * Mode C's counterpart of Mode B's `theme` envelope: the colours the widgets
 * resolve are already inline, but the page background, a field's surface and
 * every hover/focus state are CSS, so the sheet needs the mode. Resolved the way
 * a widget resolves it (`is_dark()` with no platform flag), so the sheet and the
 * tree never disagree.
 *
 * @param {?Object} theme  The active theme.
 * @returns {void}
 */
function markThemeMode(theme) {
  const dark = theme != null && typeof theme.is_dark === "function" && theme.is_dark();
  applyThemeMode(dark ? "dark" : "light");
}

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
    /** @type {Set<Object>} — registered animation controllers (App clock). */
    this._animations = new Set();
    /** @type {?() => void} — hook the runtime installs to start the frame loop. */
    this._onAnimate = null;
    /**
     * Visible-window overrides for virtualized lists, keyed by the list's `key`
     * (mirrors the core App._windows). Published to the builders for the
     * duration of each build, so a slid window survives the view re-running.
     * @type {Map<string, number[]>}
     */
    this._windows = new Map();
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
    markThemeMode(theme);
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

  /**
   * Set a virtualized list's visible window and re-render (mirrors the core
   * App.slide_window).
   *
   * The client reports a list's `[start, end)` as it scrolls; recording it by
   * key is what makes the next build materialize the slid items, which the
   * keyed diff turns into a minimal remove/reorder/insert.
   *
   * @param {string} key   The list widget's key.
   * @param {number} start The first visible index (inclusive).
   * @param {number} end   The one-past-last visible index (exclusive).
   * @returns {void}
   */
  slide_window(key, start, end) {
    this._windows.set(key, [start, end]);
    this._rerender();
  }

  /**
   * Register an animation controller on the app's frame clock (mirrors the core
   * App.register_animation): binds it and starts the runtime's frame loop.
   * @param {Object} ctrl  An AnimationController.
   * @returns {void}
   */
  register_animation(ctrl) {
    ctrl.bind(this);
    this._animations.add(ctrl);
    if (this._onAnimate !== null) {
      this._onAnimate();
    }
  }

  /**
   * Unregister an animation controller from the frame clock.
   * @param {Object} ctrl  An AnimationController.
   * @returns {void}
   */
  unregister_animation(ctrl) {
    this._animations.delete(ctrl);
  }

  /**
   * Whether any animation is currently registered (mirrors the core property).
   * @returns {boolean}
   */
  get has_animations() {
    return this._animations.size > 0;
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
 * The URL round-trips in both directions. `lastPath` tracks the top-route path the
 * URL currently reflects: a `navigate` event (deep link / back-forward) resets the
 * nav stack from the path and updates `lastPath` without echoing it back, while an
 * imperative push/pop/replace that changes the top path tells the router to
 * pushState the new URL (params included). A `media` event (resize / dark-mode /
 * orientation change) updates `app.media`, and `installMedia` keeps it in sync so
 * the app renders responsively.
 *
 * An event handler may be async (e.g. `await native.http.request(...)` then
 * set_state); the re-render fires when set_state runs, after the await, and any
 * rejection is logged and swallowed so an unhandled promise never crashes the tab.
 * While animation controllers are registered, a requestAnimationFrame loop (with a
 * setTimeout fallback) ticks each with the per-frame dt, re-renders so the view
 * reads their new `value`, and drops any that have settled.
 *
 * @param {HTMLElement} root  The host element to mount into.
 * @param {TranspileModule} mod  The generated module (`makeState` + `view`).
 * @returns {TranspileMountHandle}  A handle to inspect and tear down the app.
 */
/**
 * Shape a wire event the way an app handler reads it.
 *
 * A handler in Modes A and B receives a typed event object whose fields are
 * flat — `e.value` for a text change, `e.x`/`e.y` for a tap — built by Python
 * from the wire payload. Mode C used to hand the handler the wire event itself
 * (`{type, key, payload}`), so `e.value` was `undefined` and a text input wrote
 * undefined into the state: the page rendered, typing did nothing, and the
 * first read of the draft threw. The payload's own fields win, because they are
 * exactly what the typed event exposes; `payload` stays reachable for a handler
 * written against the wire shape.
 *
 * @param {TWEvent} event  The wire event.
 * @returns {Object}  The event the handler sees.
 */
/**
 * Run the app's view with its tracked list windows published to the builders.
 *
 * The core injects a slid window into the widget tree before children are
 * materialized; a Mode C builder materializes as it runs, so the map is ambient
 * for exactly the duration of the build and cleared right after — a build that
 * threw must not leave a stale window visible to the next one.
 *
 * @param {function(App): import("../transport.js").Node} view  The app's view.
 * @param {App} app  The application handle.
 * @returns {import("../transport.js").Node}  The freshly built tree.
 */
function buildView(view, app) {
  setSlidWindows(app._windows);
  try {
    return view(app);
  } finally {
    setSlidWindows(null);
  }
}

function appEvent(event) {
  const payload = event.payload ?? {};
  return { type: event.type, key: event.key, payload, ...payload };
}

export function mountApp(root, { makeState, view }) {
  const app = new App(makeState());

  /** @type {Node} */
  let node = buildView(view, app);
  /** @type {Map<string, Function>} */
  let handlers = collectHandlers(node);
  /** @type {Patch[][]} */
  const patchLog = [];

  /** @type {?(patches: Patch[]) => void} */
  let deliver = null;
  /** @type {?(path: string) => void} — view→URL sink (wired by mount via router). */
  let navSink = null;
  let lastPath = routeToPath(app.nav.top);

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
      if (event.type === "navigate") {
        const path = event.payload?.path;
        if (typeof path === "string" && path) {
          lastPath = path;
          app.reset(pathToRoutes(path));
        }
        return;
      }
      if (event.type === "media") {
        app._setMedia(new MediaQueryData(event.payload ?? {}));
        return;
      }
      if (event.type === "scroll") {
        const { start, end } = event.payload ?? {};
        if (
          event.key != null &&
          Number.isInteger(start) &&
          Number.isInteger(end) &&
          end >= start
        ) {
          app.slide_window(event.key, start, end);
        }
        return;
      }
      if (event.key == null) {
        return;
      }
      const handler = handlers.get(`${event.type}:${event.key}`);
      if (typeof handler !== "function") {
        return;
      }
      // `fn.length` counts the parameters *before* the first default, which is
      // exactly Python's question: a parameter with a default is not something
      // the caller has to supply, so it does not mean "give me the event". The
      // loop-capture idiom `(i = index) => …` has length 0 and must keep its
      // captured index — feeding it the event made the app store a ClickEvent
      // where an index belonged (measured in examples/faq-accordion).
      const result = handler.length > 0 ? handler(appEvent(event)) : handler();
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
    const next = buildView(view, app);
    const patches = diff(node, next);
    node = next;
    handlers = collectHandlers(next);
    if (patches.length > 0) {
      patchLog.push(patches);
      if (deliver !== null) {
        deliver(patches);
      }
    }
    const path = routeToPath(app.nav.top);
    if (path !== lastPath) {
      lastPath = path;
      if (navSink !== null) {
        navSink(path);
      }
    }
  };

  const handle = mount(root, transport, node);

  let running = false;
  /** @type {?number} — previous frame timestamp; null before the first frame. */
  let lastFrame = null;
  const raf =
    typeof globalThis.requestAnimationFrame === "function"
      ? globalThis.requestAnimationFrame.bind(globalThis)
      : (fn) => setTimeout(() => fn(Date.now()), 16);
  const frame = (now) => {
    const dt = lastFrame === null ? 0 : (now - lastFrame) / 1000;
    lastFrame = now;
    for (const ctrl of [...app._animations]) {
      if (ctrl._advance(dt)) {
        app.unregister_animation(ctrl);
      }
    }
    app._rerender();
    if (app._animations.size > 0) {
      raf(frame);
    } else {
      running = false;
    }
  };
  app._onAnimate = () => {
    if (!running) {
      running = true;
      lastFrame = null;
      raf(frame);
    }
  };

  return {
    root: handle.root,
    app,
    get node() {
      return node;
    },
    patchLog,
    unmount() {
      handle.unmount();
    },
  };
}

/**
 * Python's `re` semantics, which JS does not give for free.
 *
 * Three differences the emitted code would otherwise get wrong:
 * `Pattern.match` anchors at the **start** of the string (JS `test`/`exec` do
 * not), `Pattern.fullmatch` anchors at both ends, and `re.sub` replaces **every**
 * occurrence (a JS `replace` with a string pattern replaces one). Each helper
 * takes either a compiled `RegExp` or a raw pattern string, so `re.sub(r"\D", …)`
 * and a module-level `re.compile(...)` both work.
 *
 * The pattern source travels unchanged: the shared syntax (`\d`, `\s`, classes,
 * quantifiers, groups) means the common case is identical, while Python-only
 * syntax (`(?P<name>…)`, inline `(?i)`) is not translated and would throw in the
 * browser the same way an invalid pattern does.
 *
 * @param {RegExp|string} pattern  A compiled pattern or its source.
 * @param {string} [anchor]        `"^"`, `"^$"`, or `""` for a free search.
 * @param {string} [extraFlags]    Flags to add (e.g. `"g"`).
 * @returns {RegExp}  The equivalent JS pattern.
 */
function pythonRegExp(pattern, anchor = "", extraFlags = "") {
  const compiled = pattern instanceof RegExp;
  const source = compiled ? pattern.source : String(pattern);
  const base = compiled ? pattern.flags.replace(/g/g, "") : "";
  const flags = [...new Set(`${base}${extraFlags}`.split(""))].join("");
  const head = anchor.startsWith("^") ? "^" : "";
  const tail = anchor.endsWith("$") ? "$" : "";
  return new RegExp(`${head}(?:${source})${tail}`, flags);
}

/**
 * `Pattern.match(text)` / `re.match(pattern, text)` — anchored at the start.
 *
 * @param {RegExp|string} pattern  The pattern.
 * @param {string} text            The subject.
 * @returns {?RegExpExecArray}  The match, or null — truthy exactly as in Python.
 */
export function reMatch(pattern, text) {
  return pythonRegExp(pattern, "^").exec(String(text));
}

/**
 * `Pattern.search(text)` / `re.search(pattern, text)` — anywhere in the string.
 *
 * @param {RegExp|string} pattern  The pattern.
 * @param {string} text            The subject.
 * @returns {?RegExpExecArray}  The match, or null.
 */
export function reSearch(pattern, text) {
  return pythonRegExp(pattern).exec(String(text));
}

/**
 * `Pattern.fullmatch(text)` — the whole string must match.
 *
 * @param {RegExp|string} pattern  The pattern.
 * @param {string} text            The subject.
 * @returns {?RegExpExecArray}  The match, or null.
 */
export function reFullmatch(pattern, text) {
  return pythonRegExp(pattern, "^$").exec(String(text));
}

/**
 * `re.sub(pattern, replacement, text)` — replaces every occurrence.
 *
 * @param {RegExp|string} pattern      The pattern.
 * @param {string} replacement         The replacement text.
 * @param {string} text                The subject.
 * @returns {string}  The substituted string.
 */
export function reSub(pattern, replacement, text) {
  return String(text).replace(pythonRegExp(pattern, "", "g"), replacement);
}

/**
 * `re.findall(pattern, text)` — every non-overlapping match, as strings.
 *
 * @param {RegExp|string} pattern  The pattern.
 * @param {string} text            The subject.
 * @returns {string[]}  The matched substrings.
 */
export function reFindall(pattern, text) {
  return [...String(text).matchAll(pythonRegExp(pattern, "", "g"))].map((m) => m[0]);
}

/**
 * Python's truthiness, which JS only half shares.
 *
 * `""`, `0`, `None` and `False` agree; the containers do not. An empty list, dict
 * or set is **falsy** in Python and **truthy** in JS, so `if s.errors:` entered
 * its branch on a fresh state and rendered an error banner nobody had earned —
 * measured in `examples/br-cadastro`, which read `undefined campo(s) com erro`
 * before a single submit.
 *
 * A dataclass instance is a Python object with no `__len__`, so it is always
 * truthy however few fields it carries; a plain object stands for a dict and is
 * judged by its keys.
 *
 * @param {*} value  Any value in a boolean position.
 * @returns {boolean}  What Python's `bool()` would answer.
 */
export function truthy(value) {
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  if (value instanceof Set || value instanceof Map) {
    return value.size > 0;
  }
  if (value !== null && typeof value === "object") {
    return value instanceof State ? true : Object.keys(value).length > 0;
  }
  return Boolean(value);
}

/**
 * Python's `len()`, which is not `.length` for a mapping or a set.
 *
 * `len(d)` on a dict emitted `d.length` and answered `undefined`, so a count of
 * failing fields rendered as `undefined campo(s) com erro`.
 *
 * @param {*} value  A sized value.
 * @returns {number}  Its length.
 */
export function pyLen(value) {
  if (value == null) {
    return 0;
  }
  if (value instanceof Set || value instanceof Map) {
    return value.size;
  }
  if (typeof value.length === "number") {
    return value.length;
  }
  return Object.keys(value).length;
}

/**
 * Python's `in`, which reads keys on a mapping and members everywhere else.
 *
 * `"k" in d` emitted `d.includes("k")` — an `Array` method a plain object does
 * not have — so a membership test on a dict threw instead of answering.
 *
 * @param {*} haystack  The container being searched.
 * @param {*} needle    What to look for (a key, for a mapping).
 * @returns {boolean}
 */
export function contains(haystack, needle) {
  if (haystack == null) {
    return false;
  }
  if (typeof haystack === "string" || Array.isArray(haystack)) {
    return haystack.includes(needle);
  }
  if (haystack instanceof Set || haystack instanceof Map) {
    return haystack.has(needle);
  }
  if (typeof haystack === "object") {
    return Object.hasOwn(haystack, needle);
  }
  return false;
}

/**
 * Copy a mapping or build one from pairs, the way Python's `dict()` does.
 *
 * A dict is a plain object in Mode C and a list of pairs is an array, and the
 * compiler cannot tell which one it holds — so `dict(x)` emitted
 * `Object.fromEntries(x)` unconditionally, which throws `object is not iterable`
 * on a mapping. Measured in `examples/form`, whose submit died on
 * `dict(result.errors)`.
 *
 * @param {Object|Iterable} value  A mapping to copy, or an iterable of pairs.
 * @returns {Object<string, *>}  A new plain object.
 */
export function toDict(value) {
  if (value == null) {
    return {};
  }
  if (typeof value[Symbol.iterator] === "function") {
    return Object.fromEntries(value);
  }
  return { ...value };
}

/**
 * Remove a key from a mapping and return its value, as `dict.pop` does.
 *
 * A dict is a plain object, which has no `pop`: the emitted `errors.pop(k, null)`
 * resolved to nothing at all and threw. Python raises `KeyError` for a missing
 * key with no default; only the two-argument form is emitted, and this mirrors
 * it.
 *
 * @param {Object<string, *>} mapping  The mapping to remove from (mutated).
 * @param {string} key  The key to remove.
 * @param {*} fallback  Returned when the key is absent.
 * @returns {*}  The removed value, or `fallback`.
 */
export function dictPop(mapping, key, fallback) {
  if (mapping == null || !Object.hasOwn(mapping, key)) {
    return fallback;
  }
  const value = mapping[key];
  delete mapping[key];
  return value;
}

/**
 * `asyncio.sleep(seconds)` — Python counts seconds, `setTimeout` milliseconds.
 *
 * @param {number} seconds  How long to wait.
 * @returns {Promise<void>}  Resolves after the delay.
 */
export function sleep(seconds) {
  return new Promise((resolve) => setTimeout(resolve, seconds * 1000));
}
