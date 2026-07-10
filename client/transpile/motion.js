// motion.js — Mode C animation primitives (declarative transitions).
//
// `Transition` + `Curve` mirror tempest_core.style's animation values. A widget
// whose `Style` carries a `transition` animates in the browser via a CSS
// `transition` — the shared renderer (client/style.js `transitionToCss`) already
// emits it, so declarative animation works in Mode C with no Python runtime and
// no per-frame driver: change a styled prop (width, color, opacity) and the
// browser tweens it.
//
// `Transition` returns the plain wire object style.js reads ({duration_ms, curve,
// delay_ms}) — it is a Style field value, not a widget, so no `new`.

/**
 * Easing curves — CSS `transition-timing-function` values. Mirrors
 * `tempest_core.style.Curve`.
 * @type {Object<string, string>}
 */
export const Curve = Object.freeze({
  LINEAR: "linear",
  EASE_IN: "ease-in",
  EASE_OUT: "ease-out",
  EASE_IN_OUT: "ease-in-out",
  EASE: "ease",
  BOUNCE: "bounce",
  ELASTIC: "elastic",
});

/**
 * Build a transition (a `Style.transition` value). Mirrors
 * `tempest_core.style.Transition`.
 *
 * @param {{duration_ms: number, curve?: string, delay_ms?: number}} args
 * @returns {{duration_ms: number, curve: string, delay_ms: number}}
 */
export function Transition({ duration_ms, curve = Curve.EASE_IN_OUT, delay_ms = 0 } = {}) {
  return { duration_ms, curve, delay_ms };
}
