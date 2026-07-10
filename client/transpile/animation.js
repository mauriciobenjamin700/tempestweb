// animation.js — Mode C imperative animation (port of tempest_core.animation).
//
// AnimationController drives a normalized `value` (0..1) on the app's frame clock
// — an eased ramp over a duration, or a damped-spring integration. Tween maps
// that value to a float / Color / Edge for a Style. The runtime (runtime.js)
// registers controllers on a requestAnimationFrame loop, ticks them with the
// per-frame dt, re-renders, and unregisters each when it settles.
//
// The curve math, ramp/spring integration and lerps mirror the core exactly, so
// a controller-driven animation runs identically to Modes A/B (which use the
// core on a Python clock). Curve values come from ./motion.js.

import { Curve } from "./motion.js";

const TAU3 = (2.0 * Math.PI) / 3.0; // elastic constant (c4)

/**
 * Map linear progress `t` (0..1) through an easing curve — mirrors the core.
 * @param {string} curve  A {@link Curve} value.
 * @param {number} t  Linear progress.
 * @returns {number}  Eased progress.
 */
export function applyCurve(curve, t) {
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  if (curve === Curve.LINEAR) return t;
  if (curve === Curve.EASE_IN) return t * t;
  if (curve === Curve.EASE_OUT) return 1.0 - (1.0 - t) * (1.0 - t);
  if (curve === Curve.EASE_IN_OUT || curve === Curve.EASE) {
    if (t < 0.5) return 4.0 * t * t * t;
    const f = 2.0 * t - 2.0;
    return 1.0 + (f * f * f) / 2.0;
  }
  if (curve === Curve.BOUNCE) return bounceOut(t);
  if (curve === Curve.ELASTIC) {
    if (t === 0.0 || t === 1.0) return t;
    return -(2.0 ** (10.0 * t - 10.0)) * Math.sin((t * 10.0 - 10.75) * TAU3);
  }
  return t;
}

/** The ease-out bounce curve (mirrors the core `_bounce_out`). */
function bounceOut(t) {
  const n1 = 7.5625;
  const d1 = 2.75;
  if (t < 1.0 / d1) return n1 * t * t;
  if (t < 2.0 / d1) {
    t -= 1.5 / d1;
    return n1 * t * t + 0.75;
  }
  if (t < 2.5 / d1) {
    t -= 2.25 / d1;
    return n1 * t * t + 0.9375;
  }
  t -= 2.625 / d1;
  return n1 * t * t + 0.984375;
}

const lerp = (a, b, t) => a + (b - a) * t;

/**
 * A damped-spring config. Mirrors `tempest_core.animation.Spring`.
 */
export class Spring {
  /** @param {{stiffness?: number, damping?: number, mass?: number}} [args] */
  constructor({ stiffness = 300.0, damping = 30.0, mass = 1.0 } = {}) {
    this.stiffness = stiffness;
    this.damping = damping;
    this.mass = mass;
  }
}

/**
 * Drives a normalized `value` (0..1) toward 1 (forward) or 0 (reverse), eased
 * over a duration or integrated as a spring. Mirrors
 * `tempest_core.animation.AnimationController`.
 */
export class AnimationController {
  /**
   * @param {number} duration_s  Ramp duration in seconds (ignored for a spring).
   * @param {{curve?: string, spring?: ?Spring}} [opts]  Easing curve (a
   *        {@link Curve} value) and/or a spring. The transpiler passes the
   *        Python keyword args (`curve=`, `spring=`) as this options object.
   */
  constructor(duration_s, opts = {}) {
    this.duration_s = duration_s;
    this.curve = opts.curve ?? Curve.EASE_IN_OUT;
    this.spring = opts.spring ?? null;
    this.value = 0.0;
    this._dir = 0;
    this._elapsed = 0.0;
    this._velocity = 0.0;
    /** @type {?{register_animation: Function, unregister_animation: Function}} */
    this._app = null;
  }

  /** Attach to an app's frame clock (called by App.register_animation). */
  bind(app) {
    this._app = app;
  }

  /** Animate `value` toward 1.0 and (re)register on the app clock. */
  forward() {
    this._dir = 1;
    if (this._app !== null) {
      this._app.register_animation(this);
    }
  }

  /** Animate `value` toward 0.0 and (re)register on the app clock. */
  reverse() {
    this._dir = -1;
    if (this._app !== null) {
      this._app.register_animation(this);
    }
  }

  /** Halt and unregister from the app clock. */
  stop() {
    this._dir = 0;
    this._velocity = 0.0;
    if (this._app !== null) {
      this._app.unregister_animation(this);
    }
  }

  /**
   * Advance by `dt` seconds toward the target.
   * @param {number} dt  Elapsed seconds since the previous frame.
   * @returns {boolean}  True when settled (should be unregistered).
   */
  _advance(dt) {
    if (this._dir === 0) return true;
    if (dt < 0.0) dt = 0.0;
    return this.spring !== null ? this._advanceSpring(dt) : this._advanceRamp(dt);
  }

  /** @param {number} dt @returns {boolean} */
  _advanceRamp(dt) {
    const target = this._dir > 0 ? 1.0 : 0.0;
    if (this.duration_s <= 0.0) {
      this.value = target;
      this._dir = 0;
      return true;
    }
    this._elapsed += dt;
    const progress = this._elapsed / this.duration_s;
    if (progress >= 1.0) {
      this.value = target;
      this._elapsed = 0.0;
      this._dir = 0;
      return true;
    }
    const eased = applyCurve(this.curve, progress);
    this.value = this._dir > 0 ? eased : 1.0 - eased;
    return false;
  }

  /** @param {number} dt @returns {boolean} */
  _advanceSpring(dt) {
    const s = this.spring;
    const target = this._dir > 0 ? 1.0 : 0.0;
    const displacement = this.value - target;
    const force = -s.stiffness * displacement - s.damping * this._velocity;
    const acceleration = force / s.mass;
    this._velocity += acceleration * dt;
    this.value += this._velocity * dt;
    if (Math.abs(this.value - target) < 0.001 && Math.abs(this._velocity) < 0.001) {
      this.value = target;
      this._velocity = 0.0;
      this._dir = 0;
      return true;
    }
    return false;
  }
}

/**
 * A linear interpolator between two typed endpoints (float / Color / Edge).
 * Mirrors `tempest_core.animation.Tween`; `at(t)` reads an
 * {@link AnimationController}'s `value`.
 */
export class Tween {
  /** @param {{begin: *, end: *}} args */
  constructor({ begin, end } = {}) {
    this.begin = begin;
    this.end = end;
  }

  /**
   * Interpolate between `begin` and `end` at fraction `t`.
   * @param {number} t  Usually a controller's `value` (0..1).
   * @returns {*}  The interpolated value (same shape as the endpoints).
   */
  at(t) {
    const a = this.begin;
    const b = this.end;
    if (typeof a === "number" && typeof b === "number") {
      return lerp(a, b, t);
    }
    // Color: { r, g, b, a } — r/g/b rounded, alpha as float.
    if (a && b && "r" in a && "g" in a && "b" in a) {
      return {
        r: Math.round(lerp(a.r, b.r, t)),
        g: Math.round(lerp(a.g, b.g, t)),
        b: Math.round(lerp(a.b, b.b, t)),
        a: lerp(a.a ?? 1, b.a ?? 1, t),
      };
    }
    // Edge: { top, right, bottom, left }.
    if (a && b && "top" in a && "left" in a) {
      return {
        top: lerp(a.top, b.top, t),
        right: lerp(a.right, b.right, t),
        bottom: lerp(a.bottom, b.bottom, t),
        left: lerp(a.left, b.left, t),
      };
    }
    throw new TypeError("Tween: unsupported endpoint type");
  }
}
