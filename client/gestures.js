// gestures.js — one pointer recognizer for every gesture widget the core has.
//
// The single-pointer half (tap / swipe / long press on a `GestureDetector`) lived
// inline in events.js and worked. The multi-pointer half did not exist at all, so
// four handlers the core declares were inert in every mode:
//
//   * `PanHandler.on_pan`            — a drag, reported continuously
//   * `ScaleHandler.on_scale`        — a pinch (scale, focus, rotation)
//   * `ScaleHandler.on_double_tap`   — the zoom-to-fit shortcut a pinch surface needs
//   * `GestureDetector.on_double_tap`— the same shortcut on the general detector
//   * `InteractiveViewer.on_interaction` — pan and zoom together
//
// They are all one recognizer now, because they share one state machine: the same
// pointerdown starts a tap, a pan, a pinch, or the second half of a double tap,
// and only the pointers still down tell you which. Two recognizers on the same
// root would each see half the story.
//
// What the browser reports, and what it does not: pointer events give position
// and pointerId, so pan and pinch are arithmetic. What the browser will *not* do
// is send pointermove at all while it is busy panning or zooming the page itself
// — that is what `touch-action: none` in the base sheet is for, on exactly the
// widgets that want the pointer for themselves.
//
// Continuous gestures (`pan`, `interaction`, `scale`) are reported at most once
// per frame, keeping the latest payload rather than the first, and the pending one
// is flushed when a pointer leaves — otherwise the gesture's final position is
// wherever the last frame happened to land (measured: a 2x pinch settling at
// 1.5x). A pointermove stream is 60–120 events a second, and in Mode B every one
// of them is a round trip; one per frame is what a smooth drag actually needs.

import { DOUBLE_TAP_MS, LONG_PRESS_MS, SWIPE_MIN_PX } from "./constants.js";
import { KEY_ATTR, TYPE_ATTR } from "./dom.js";

/** Widget types that want the pointer, and the gestures each one reports. */
const GESTURE_WIDGETS = Object.freeze({
  GestureDetector: Object.freeze(["tap", "swipe", "long_press", "double_tap"]),
  PanHandler: Object.freeze(["pan"]),
  ScaleHandler: Object.freeze(["scale", "double_tap"]),
  InteractiveViewer: Object.freeze(["interaction"]),
});

/** Movement (px) allowed between two taps for them to count as a double tap. */
const DOUBLE_TAP_SLOP_PX = 24;

/**
 * Find the nearest ancestor-or-self element that is a gesture widget.
 *
 * @param {EventTarget|null} target  The event's target node.
 * @param {HTMLElement} root         The delegation root.
 * @returns {?{el: HTMLElement, key: string, type: string, reports: readonly string[]}}
 */
function gestureTarget(target, root) {
  let node = /** @type {Node|null} */ (target);
  while (node != null && node.nodeType !== 1) {
    node = node.parentNode;
  }
  let el = /** @type {HTMLElement|null} */ (node);
  while (el != null) {
    const type = el.getAttribute?.(TYPE_ATTR);
    const reports = type == null ? undefined : GESTURE_WIDGETS[type];
    if (reports !== undefined && el.hasAttribute(KEY_ATTR)) {
      const key = el.getAttribute(KEY_ATTR);
      if (key != null) {
        return { el, key, type, reports };
      }
    }
    if (el === root) {
      break;
    }
    el = el.parentElement;
  }
  return null;
}

/**
 * Classify a completed single-pointer interaction.
 *
 * Swipe wins when travel crosses {@link SWIPE_MIN_PX} (direction from the
 * dominant axis); otherwise a hold past {@link LONG_PRESS_MS} is a long press,
 * and a quick release is a tap. Coordinates are the press origin.
 *
 * @param {{x:number, y:number, t:number}} start  The pointerdown origin.
 * @param {{x:number, y:number, t:number}} end    The pointerup point.
 * @returns {{type:string, payload:Object}}        The gesture type + payload.
 */
export function classifyGesture(start, end) {
  const dx = Math.round(end.x - start.x);
  const dy = Math.round(end.y - start.y);
  const dist = Math.hypot(dx, dy);
  if (dist >= SWIPE_MIN_PX) {
    const horizontal = Math.abs(dx) >= Math.abs(dy);
    const direction = horizontal ? (dx > 0 ? "right" : "left") : dy > 0 ? "down" : "up";
    return { type: "swipe", payload: { direction, dx, dy } };
  }
  if (end.t - start.t >= LONG_PRESS_MS) {
    return { type: "long_press", payload: { x: Math.round(start.x), y: Math.round(start.y) } };
  }
  return { type: "tap", payload: { x: Math.round(start.x), y: Math.round(start.y) } };
}

/**
 * Distance and midpoint between two live pointers.
 *
 * @param {{x:number,y:number}} a  One pointer.
 * @param {{x:number,y:number}} b  The other.
 * @returns {{dist:number, cx:number, cy:number, angle:number}}
 */
function span(a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return {
    dist: Math.hypot(dx, dy),
    cx: (a.x + b.x) / 2,
    cy: (a.y + b.y) / 2,
    angle: (Math.atan2(dy, dx) * 180) / Math.PI,
  };
}

/**
 * Install the pointer-gesture recognizer for every gesture widget under `root`.
 *
 * One set of listeners, one state machine. Pointers are tracked per element, so
 * two fingers on the same widget become a pinch while two fingers on two widgets
 * stay two independent drags.
 *
 * @param {HTMLElement} root  The mount root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {{dispose: () => void}}
 */
export function installGestures(root, transport) {
  const now = () => globalThis.performance?.now?.() ?? 0;

  /**
   * Live pointers, by pointerId.
   * @type {Map<number, {el: HTMLElement, key: string, type: string, reports: readonly string[],
   *   x: number, y: number, t: number, startX: number, startY: number, moved: boolean}>}
   */
  const pointers = new Map();

  /** Per-element pinch baseline, captured when the second pointer lands. */
  const pinches = new Map();

  /** Last completed tap per element, for double-tap detection. */
  const lastTap = new Map();

  /** The latest un-sent report per element. @type {Map<HTMLElement, () => void>} */
  const pending = new Map();

  /**
   * Report at most once per frame per element, keeping the **latest** payload.
   *
   * A pointermove stream is 60–120 events a second and in Mode B each one is a
   * round trip, so they coalesce. Keeping the latest rather than the first is
   * what makes the coalescing invisible: the reader's fingers are already at the
   * new position, and reporting where they were two events ago shows up as a
   * gesture that lags and then snaps.
   *
   * @param {HTMLElement} el   The gesture element.
   * @param {() => void} send  The report to make when the frame comes.
   * @returns {void}
   */
  const perFrame = (el, send) => {
    const already = pending.has(el);
    pending.set(el, send);
    if (already) {
      return;
    }
    const run = () => {
      const latest = pending.get(el);
      pending.delete(el);
      latest?.();
    };
    if (typeof globalThis.requestAnimationFrame === "function") {
      globalThis.requestAnimationFrame(run);
    } else {
      Promise.resolve().then(run);
    }
  };

  /**
   * Send an element's pending report now, if it has one.
   *
   * Called when a pointer leaves, and this is not housekeeping: without it the
   * gesture's **final** position is whatever was last flushed by a frame, so
   * lifting two fingers from a pinch left the app a step behind. Measured in
   * Chrome: a 100px → 200px pinch (2x) settled at 1.5x, because the frame that
   * would have carried the last move never came.
   *
   * @param {HTMLElement} el  The gesture element.
   * @returns {void}
   */
  const flushPending = (el) => {
    const latest = pending.get(el);
    if (latest !== undefined) {
      pending.delete(el);
      latest();
    }
  };

  /** Live pointers currently on `el`. @returns {Array<{x:number,y:number}>} */
  const pointersOn = (el) => {
    const live = [];
    for (const state of pointers.values()) {
      if (state.el === el) {
        live.push(state);
      }
    }
    return live;
  };

  /** @param {PointerEvent} event */
  const onPointerDown = (event) => {
    const found = gestureTarget(event.target, root);
    if (found == null) {
      return;
    }
    pointers.set(event.pointerId, {
      ...found,
      x: event.clientX,
      y: event.clientY,
      t: now(),
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    });
    const live = pointersOn(found.el);
    if (live.length === 2) {
      const base = span(live[0], live[1]);
      pinches.set(found.el, { dist: base.dist || 1, angle: base.angle });
    }
  };

  /** @param {PointerEvent} event */
  const onPointerMove = (event) => {
    const state = pointers.get(event.pointerId);
    if (state === undefined) {
      return;
    }
    const previous = { x: state.x, y: state.y, t: state.t };
    state.x = event.clientX;
    state.y = event.clientY;
    state.t = now();
    if (Math.hypot(state.x - state.startX, state.y - state.startY) > 2) {
      state.moved = true;
    }

    const live = pointersOn(state.el);
    const baseline = pinches.get(state.el);
    if (live.length >= 2 && baseline !== undefined) {
      const current = span(live[0], live[1]);
      const payload = {
        scale: current.dist / baseline.dist,
        focus_x: current.cx,
        focus_y: current.cy,
        rotation: current.angle - baseline.angle,
      };
      if (state.reports.includes("scale")) {
        perFrame(state.el, () =>
          transport.sendEvent({ type: "scale", key: state.key, payload }),
        );
      } else if (state.reports.includes("interaction")) {
        perFrame(state.el, () =>
          transport.sendEvent({ type: "interaction", key: state.key, payload }),
        );
      }
      return;
    }

    const dt = Math.max(1, state.t - previous.t) / 1000;
    if (state.reports.includes("pan")) {
      const payload = {
        dx: state.x - previous.x,
        dy: state.y - previous.y,
        vx: (state.x - previous.x) / dt,
        vy: (state.y - previous.y) / dt,
      };
      perFrame(state.el, () => transport.sendEvent({ type: "pan", key: state.key, payload }));
      return;
    }
    if (state.reports.includes("interaction")) {
      // A one-pointer drag on an InteractiveViewer is a pan, but the event the
      // core declares for it is a ScaleEvent: the app reads the moving focus and
      // derives the translation, with the scale unchanged.
      const payload = {
        scale: 1,
        focus_x: state.x,
        focus_y: state.y,
        rotation: 0,
      };
      perFrame(state.el, () =>
        transport.sendEvent({ type: "interaction", key: state.key, payload }),
      );
    }
  };

  /**
   * Report a double tap when this release is the second quick tap in place.
   *
   * @param {{el: HTMLElement, key: string, x: number, y: number}} release
   * @returns {boolean}  True when a double tap was reported.
   */
  const reportDoubleTap = (release) => {
    const previous = lastTap.get(release.el);
    lastTap.set(release.el, { x: release.x, y: release.y, t: now() });
    if (previous === undefined) {
      return false;
    }
    const quick = now() - previous.t <= DOUBLE_TAP_MS;
    const close =
      Math.hypot(release.x - previous.x, release.y - previous.y) <= DOUBLE_TAP_SLOP_PX;
    if (!quick || !close) {
      return false;
    }
    // Consumed: a triple tap is a double tap followed by a fresh single one,
    // not two overlapping doubles.
    lastTap.delete(release.el);
    transport.sendEvent({
      type: "double_tap",
      key: release.key,
      payload: { x: Math.round(release.x), y: Math.round(release.y) },
    });
    return true;
  };

  /** @param {PointerEvent} event */
  const onPointerUp = (event) => {
    const state = pointers.get(event.pointerId);
    if (state === undefined) {
      return;
    }
    pointers.delete(event.pointerId);
    flushPending(state.el);
    if (pointersOn(state.el).length < 2) {
      pinches.delete(state.el);
    }

    const end = { x: event.clientX, y: event.clientY, t: now() };
    const still = !state.moved;
    if (still && state.reports.includes("double_tap") && reportDoubleTap({ ...state, ...end })) {
      return;
    }
    if (!state.reports.includes("tap")) {
      // A pan / pinch surface has nothing to report on release: everything it
      // says was said while the pointer was moving.
      return;
    }
    const { type, payload } = classifyGesture(
      { x: state.startX, y: state.startY, t: state.t },
      end,
    );
    transport.sendEvent({ type, key: state.key, payload });
  };

  /** @param {PointerEvent} event */
  const onPointerCancel = (event) => {
    const state = pointers.get(event.pointerId);
    if (state === undefined) {
      return;
    }
    pointers.delete(event.pointerId);
    flushPending(state.el);
    if (pointersOn(state.el).length < 2) {
      pinches.delete(state.el);
    }
  };

  const bound = /** @type {Array<[string, (event: Event) => void]>} */ ([
    ["pointerdown", onPointerDown],
    ["pointermove", onPointerMove],
    ["pointerup", onPointerUp],
    ["pointercancel", onPointerCancel],
  ]);
  for (const [type, handler] of bound) {
    root.addEventListener(type, handler);
  }

  return {
    dispose() {
      for (const [type, handler] of bound) {
        root.removeEventListener(type, handler);
      }
      pointers.clear();
      pinches.clear();
      lastTap.clear();
      pending.clear();
    },
  };
}
