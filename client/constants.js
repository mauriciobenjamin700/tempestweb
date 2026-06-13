// constants.js — shared client-side constants (tunables used across modules).
//
// Module-private values stay in their module; this file holds the few constants
// that are shared or are worth naming/tuning in one place: gesture-recognition
// thresholds and the virtualization stylesheet id.

/** Minimum pointer travel (px) for a drag to count as a swipe. */
export const SWIPE_MIN_PX = 30;

/** Hold time (ms, with little travel) for a press to count as a long press. */
export const LONG_PRESS_MS = 500;

/** Widget type tag that opts into gesture events (tap/swipe/long_press). */
export const GESTURE_TYPE = "GestureDetector";

/** Id of the injected stylesheet that carries virtualized-list spacer heights. */
export const VIRT_STYLE_ID = "tw-virt-styles";

/** Id of the injected stylesheet that carries the always-on MD3 base theme. */
export const BASE_THEME_STYLE_ID = "tw-base-theme";
