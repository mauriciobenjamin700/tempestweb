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

/** Pull distance (px) from a list's scroll origin that arms a refresh. */
export const PULL_REFRESH_PX = 64;

/** Quiet time (ms) after a carousel's last scroll before its page is reported. */
export const PAGE_SETTLE_MS = 120;

/** Id of the injected stylesheet that carries virtualized-list spacer heights. */
export const VIRT_STYLE_ID = "tw-virt-styles";

/** Id of the injected stylesheet that carries the always-on MD3 base theme. */
export const BASE_THEME_STYLE_ID = "tw-base-theme";

/** Id of the injected stylesheet backing the layout presets (client/layouts.js). */
export const LAYOUT_STYLE_ID = "tw-layout-styles";
