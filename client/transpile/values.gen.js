// values.gen.js — GENERATED from tempest_core by tempestweb transpile (Mode C).
// The core's enums, non-widget value objects and design tokens, in the wire shape.
// Regenerate: python -m tests.conformance._transpile_values. Do not edit.

/** `ACCENT` — a core design token. */
export const ACCENT = Object.freeze({"r": 37, "g": 99, "b": 235, "a": 1.0});

/** `AlertVariant` — the core enum's members, by wire value. */
export const AlertVariant = Object.freeze({
  SUBTLE: "subtle",
  SOLID: "solid",
  LEFT_ACCENT: "left_accent",
  TOP_ACCENT: "top_accent",
});

/** `AlignItems` — the core enum's members, by wire value. */
export const AlignItems = Object.freeze({
  START: "start",
  END: "end",
  CENTER: "center",
  STRETCH: "stretch",
});

/** `AppState` — the core enum's members, by wire value. */
export const AppState = Object.freeze({
  FOREGROUND: "foreground",
  BACKGROUND: "background",
  INACTIVE: "inactive",
});

/**
 * Build a `ArcTo` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ArcTo(partial = {}) {
  return { ...ArcTo_DEFAULTS, ...partial };
}

const ArcTo_DEFAULTS = Object.freeze({
  kind: "arc_to",
});

/** `BACKGROUND` — a core design token. */
export const BACKGROUND = Object.freeze({"r": 11, "g": 15, "b": 20, "a": 1.0});

/** `BADGE_DENSITY` — a core design token. */
export const BADGE_DENSITY = Object.freeze({"xs": [1.0, 6.0, "label_small"], "sm": [2.0, 8.0, "label_small"], "md": [3.0, 10.0, "label_medium"], "lg": [4.0, 12.0, "label_large"]});

/** `BadgeVariant` — the core enum's members, by wire value. */
export const BadgeVariant = Object.freeze({
  SOLID: "solid",
  SUBTLE: "subtle",
  OUTLINE: "outline",
});

/**
 * Build a `Border` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function Border(partial = {}) {
  return { ...Border_DEFAULTS, ...partial };
}

const Border_DEFAULTS = Object.freeze({
  color: null,
  width: 0.0,
});

/**
 * Build a `CameraFrameEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function CameraFrameEvent(partial = {}) {
  return { ...CameraFrameEvent_DEFAULTS, ...partial };
}

const CameraFrameEvent_DEFAULTS = Object.freeze({
  rotation: 0,
});

/** `CardVariant` — the core enum's members, by wire value. */
export const CardVariant = Object.freeze({
  ELEVATED: "elevated",
  FILLED: "filled",
  OUTLINED: "outlined",
});

/**
 * Build a `ChartSeries` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ChartSeries(partial = {}) {
  return { ...ChartSeries_DEFAULTS, ...partial };
}

const ChartSeries_DEFAULTS = Object.freeze({
  color_scheme: null,
  label: "",
  points: [],
});

/** `ClipShape` — the core enum's members, by wire value. */
export const ClipShape = Object.freeze({
  CIRCLE: "circle",
  ROUNDED_RECT: "rounded_rect",
  OVAL: "oval",
});

/**
 * Build a `Close` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function Close(partial = {}) {
  return { ...Close_DEFAULTS, ...partial };
}

const Close_DEFAULTS = Object.freeze({
  kind: "close",
});

/** `ColorRole` — the core enum's members, by wire value. */
export const ColorRole = Object.freeze({
  PRIMARY: "primary",
  ON_PRIMARY: "on_primary",
  PRIMARY_CONTAINER: "primary_container",
  ON_PRIMARY_CONTAINER: "on_primary_container",
  SECONDARY: "secondary",
  ON_SECONDARY: "on_secondary",
  SECONDARY_CONTAINER: "secondary_container",
  ON_SECONDARY_CONTAINER: "on_secondary_container",
  TERTIARY: "tertiary",
  ON_TERTIARY: "on_tertiary",
  TERTIARY_CONTAINER: "tertiary_container",
  ON_TERTIARY_CONTAINER: "on_tertiary_container",
  ERROR: "error",
  ON_ERROR: "on_error",
  ERROR_CONTAINER: "error_container",
  ON_ERROR_CONTAINER: "on_error_container",
  SUCCESS: "success",
  ON_SUCCESS: "on_success",
  SUCCESS_CONTAINER: "success_container",
  ON_SUCCESS_CONTAINER: "on_success_container",
  WARNING: "warning",
  ON_WARNING: "on_warning",
  WARNING_CONTAINER: "warning_container",
  ON_WARNING_CONTAINER: "on_warning_container",
  INFO: "info",
  ON_INFO: "on_info",
  INFO_CONTAINER: "info_container",
  ON_INFO_CONTAINER: "on_info_container",
  BACKGROUND: "background",
  ON_BACKGROUND: "on_background",
  SURFACE: "surface",
  ON_SURFACE: "on_surface",
  SURFACE_VARIANT: "surface_variant",
  ON_SURFACE_VARIANT: "on_surface_variant",
  OUTLINE: "outline",
  OUTLINE_VARIANT: "outline_variant",
  INVERSE_SURFACE: "inverse_surface",
  INVERSE_ON_SURFACE: "inverse_on_surface",
  INVERSE_PRIMARY: "inverse_primary",
});

/**
 * Build a `ColorScheme` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ColorScheme(partial = {}) {
  return { ...ColorScheme_DEFAULTS, ...partial };
}

const ColorScheme_DEFAULTS = Object.freeze({
  info: null,
  info_container: null,
  on_info: null,
  on_info_container: null,
  on_success: null,
  on_success_container: null,
  on_warning: null,
  on_warning_container: null,
  success: null,
  success_container: null,
  warning: null,
  warning_container: null,
});

/**
 * Build a `ColorSchemes` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ColorSchemes(partial = {}) {
  return { ...ColorSchemes_DEFAULTS, ...partial };
}

const ColorSchemes_DEFAULTS = Object.freeze({});

/** `ComponentState` — the core enum's members, by wire value. */
export const ComponentState = Object.freeze({
  DEFAULT: "default",
  HOVER: "hover",
  PRESSED: "pressed",
  DISABLED: "disabled",
  FOCUS: "focus",
});

/**
 * Build a `ConnectivityEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ConnectivityEvent(partial = {}) {
  return { ...ConnectivityEvent_DEFAULTS, ...partial };
}

const ConnectivityEvent_DEFAULTS = Object.freeze({});

/** `ConnectivityState` — the core enum's members, by wire value. */
export const ConnectivityState = Object.freeze({
  CONNECTED: "connected",
  DISCONNECTED: "disconnected",
  WIFI: "wifi",
  MOBILE: "mobile",
});

/**
 * Build a `Corners` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function Corners(partial = {}) {
  return { ...Corners_DEFAULTS, ...partial };
}

const Corners_DEFAULTS = Object.freeze({
  bottom_left: 0.0,
  bottom_right: 0.0,
  top_left: 0.0,
  top_right: 0.0,
});

/** `DEFAULT_WINDOW_SIZE` — a core design token. */
export const DEFAULT_WINDOW_SIZE = 20;

/** `DISABLED_CONTAINER_OPACITY` — a core design token. */
export const DISABLED_CONTAINER_OPACITY = 0.12;

/** `DISABLED_CONTENT_OPACITY` — a core design token. */
export const DISABLED_CONTENT_OPACITY = 0.38;

/**
 * Build a `DateChangeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function DateChangeEvent(partial = {}) {
  return { ...DateChangeEvent_DEFAULTS, ...partial };
}

const DateChangeEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `DeepLinkEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function DeepLinkEvent(partial = {}) {
  return { ...DeepLinkEvent_DEFAULTS, ...partial };
}

const DeepLinkEvent_DEFAULTS = Object.freeze({
  params: {},
});

/**
 * Build a `DetectionBox` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function DetectionBox(partial = {}) {
  return { ...DetectionBox_DEFAULTS, ...partial };
}

const DetectionBox_DEFAULTS = Object.freeze({
  conf: 1.0,
  name: "",
});

/** `Device` — the core enum's members, by wire value. */
export const Device = Object.freeze({
  PIXEL_4: "Google Pixel 4",
  PIXEL_5: "Google Pixel 5",
  PIXEL_6: "Google Pixel 6",
  PIXEL_6_PRO: "Google Pixel 6 Pro",
  PIXEL_7: "Google Pixel 7",
  PIXEL_7_PRO: "Google Pixel 7 Pro",
  PIXEL_8: "Google Pixel 8",
  PIXEL_8_PRO: "Google Pixel 8 Pro",
  GALAXY_S8: "Samsung Galaxy S8",
  GALAXY_S9: "Samsung Galaxy S9",
  GALAXY_S10: "Samsung Galaxy S10",
  GALAXY_S20: "Samsung Galaxy S20",
  GALAXY_S21: "Samsung Galaxy S21",
  GALAXY_S22: "Samsung Galaxy S22",
  GALAXY_S23: "Samsung Galaxy S23",
  GALAXY_S24: "Samsung Galaxy S24",
  GALAXY_S24_ULTRA: "Samsung Galaxy S24 Ultra",
  GALAXY_A51: "Samsung Galaxy A51",
  GALAXY_A52: "Samsung Galaxy A52",
  GALAXY_A54: "Samsung Galaxy A54",
  REDMI_NOTE_10: "Xiaomi Redmi Note 10",
  REDMI_NOTE_11: "Xiaomi Redmi Note 11",
  REDMI_NOTE_12: "Xiaomi Redmi Note 12",
  REDMI_NOTE_13: "Xiaomi Redmi Note 13",
  REDMI_11: "Xiaomi Redmi 11",
  REDMI_12: "Xiaomi Redmi 12",
  POCO_X5: "Xiaomi Poco X5",
  XIAOMI_13: "Xiaomi 13",
  XIAOMI_14: "Xiaomi 14",
  MOTO_G_POWER: "Motorola Moto G Power",
  MOTO_G52: "Motorola Moto G52",
  ONEPLUS_9: "OnePlus 9",
  ONEPLUS_11: "OnePlus 11",
});

/**
 * Build a `DismissEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function DismissEvent(partial = {}) {
  return { ...DismissEvent_DEFAULTS, ...partial };
}

const DismissEvent_DEFAULTS = Object.freeze({
  overlay_id: null,
});

/**
 * Build a `DragEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function DragEvent(partial = {}) {
  return { ...DragEvent_DEFAULTS, ...partial };
}

const DragEvent_DEFAULTS = Object.freeze({
  data: "",
  x: null,
  y: null,
});

/**
 * Build a `DrawOval` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function DrawOval(partial = {}) {
  return { ...DrawOval_DEFAULTS, ...partial };
}

const DrawOval_DEFAULTS = Object.freeze({
  kind: "draw_oval",
});

/**
 * Build a `DrawRect` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function DrawRect(partial = {}) {
  return { ...DrawRect_DEFAULTS, ...partial };
}

const DrawRect_DEFAULTS = Object.freeze({
  kind: "draw_rect",
});

/**
 * Build a `DrawText` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function DrawText(partial = {}) {
  return { ...DrawText_DEFAULTS, ...partial };
}

const DrawText_DEFAULTS = Object.freeze({
  color: [0.0, 0.0, 0.0, 1.0],
  kind: "draw_text",
  size: 14.0,
});

/** `ELEVATION_SHADOW_COLOR` — a core design token. */
export const ELEVATION_SHADOW_COLOR = Object.freeze({"r": 0, "g": 0, "b": 0, "a": 0.3});

/**
 * Build a `ElevationScale` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ElevationScale(partial = {}) {
  return { ...ElevationScale_DEFAULTS, ...partial };
}

const ElevationScale_DEFAULTS = Object.freeze({
  level0: 0.0,
  level1: 1.0,
  level2: 3.0,
  level3: 6.0,
  level4: 8.0,
  level5: 12.0,
});

/** `FOCUS_OPACITY` — a core design token. */
export const FOCUS_OPACITY = 0.12;

/** `FieldVariant` — the core enum's members, by wire value. */
export const FieldVariant = Object.freeze({
  OUTLINE: "outline",
  FILLED: "filled",
  FLUSHED: "flushed",
});

/**
 * Build a `FileSelectEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function FileSelectEvent(partial = {}) {
  return { ...FileSelectEvent_DEFAULTS, ...partial };
}

const FileSelectEvent_DEFAULTS = Object.freeze({
  name: null,
});

/**
 * Build a `FillCmd` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function FillCmd(partial = {}) {
  return { ...FillCmd_DEFAULTS, ...partial };
}

const FillCmd_DEFAULTS = Object.freeze({
  kind: "fill",
});

/** `FlexDirection` — the core enum's members, by wire value. */
export const FlexDirection = Object.freeze({
  ROW: "row",
  COLUMN: "column",
});

/** `FlexWrap` — the core enum's members, by wire value. */
export const FlexWrap = Object.freeze({
  NOWRAP: "nowrap",
  WRAP: "wrap",
  WRAP_REVERSE: "wrap-reverse",
});

/** `FontStyle` — the core enum's members, by wire value. */
export const FontStyle = Object.freeze({
  NORMAL: "normal",
  ITALIC: "italic",
});

/** `FontWeight` — the core enum's members, by wire value. */
export const FontWeight = Object.freeze({
  THIN: 100,
  LIGHT: 300,
  NORMAL: 400,
  MEDIUM: 500,
  SEMIBOLD: 600,
  BOLD: 700,
  BLACK: 900,
});

/**
 * Build a `FormState` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function FormState(partial = {}) {
  return { ...FormState_DEFAULTS, ...partial };
}

const FormState_DEFAULTS = Object.freeze({
  errors: {},
  valid: true,
});

/**
 * Build a `Gradient` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function Gradient(partial = {}) {
  return { ...Gradient_DEFAULTS, ...partial };
}

const Gradient_DEFAULTS = Object.freeze({
  direction: "top-bottom",
});

/** `GradientDirection` — the core enum's members, by wire value. */
export const GradientDirection = Object.freeze({
  TOP_BOTTOM: "top-bottom",
  BOTTOM_TOP: "bottom-top",
  LEFT_RIGHT: "left-right",
  RIGHT_LEFT: "right-left",
});

/**
 * Build a `GradientStop` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function GradientStop(partial = {}) {
  return { ...GradientStop_DEFAULTS, ...partial };
}

const GradientStop_DEFAULTS = Object.freeze({});

/** `HOVER_OPACITY` — a core design token. */
export const HOVER_OPACITY = 0.08;

/** `ICON_PATHS` — a core design token. */
export const ICON_PATHS = Object.freeze({"eye": "M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0 M15 12 a3 3 0 1 1-6 0 3 3 0 0 1 6 0 Z", "eye-off": "M10.733 5.076 a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49 M14.084 14.158 a3 3 0 0 1-4.242-4.242 M17.479 17.499 a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143 M2 2 l20 20", "lock": "M5 11 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v8 a2 2 0 0 1-2 2 H7 a2 2 0 0 1-2-2 Z M7 11 V7 a5 5 0 0 1 10 0 v4", "unlock": "M5 11 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v8 a2 2 0 0 1-2 2 H7 a2 2 0 0 1-2-2 Z M7 11 V7 a5 5 0 0 1 9.9-1", "search": "M21 21 l-4.34-4.34 M11 19 a8 8 0 1 0 0-16 8 8 0 0 0 0 16 Z", "x": "M18 6 6 18 M6 6 l12 12", "check": "M20 6 9 17 l-5-5", "chevron-down": "M6 9 l6 6 6-6", "chevron-up": "M18 15 l-6-6-6 6", "chevron-left": "M15 18 l-6-6 6-6", "chevron-right": "M9 18 l6-6-6-6", "arrow-left": "M19 12 H5 M12 19 l-7-7 7-7", "arrow-right": "M5 12 h14 M12 5 l7 7-7 7", "plus": "M5 12 h14 M12 5 v14", "minus": "M5 12 h14", "user": "M19 21 v-2 a4 4 0 0 0-4-4 H9 a4 4 0 0 0-4 4 v2 M12 11 a4 4 0 1 0 0-8 4 4 0 0 0 0 8 Z", "mail": "M22 7 l-8.991 5.727 a2 2 0 0 1-2.018 0 L2 7 M4 4 h16 c1.1 0 2 .9 2 2 v12 c0 1.1-.9 2-2 2 H4 c-1.1 0-2-.9-2-2 V6 c0-1.1.9-2 2-2 Z", "phone": "M13.832 16.568 a1 1 0 0 0 1.213-.303 l.355-.465 A2 2 0 0 1 17 15 h3 a2 2 0 0 1 2 2 v3 a2 2 0 0 1-2 2 A18 18 0 0 1 2 4 a2 2 0 0 1 2-2 h3 a2 2 0 0 1 2 2 v3 a2 2 0 0 1-.8 1.6 l-.468.351 a1 1 0 0 0-.292 1.233 a14 14 0 0 0 6.06 6.0 Z", "calendar": "M8 2 v4 M16 2 v4 M3 10 h18 M5 4 h14 a2 2 0 0 1 2 2 v14 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 V6 a2 2 0 0 1 2-2 Z", "clock": "M12 6 v6 l4 2 M12 2 a10 10 0 1 0 0 20 10 10 0 0 0 0-20 Z", "trash": "M3 6 h18 M19 6 v14 c0 1-1 2-2 2 H7 c-1 0-2-1-2-2 V6 M8 6 V4 c0-1 1-2 2-2 h4 c1 0 2 1 2 2 v2 M10 11 v6 M14 11 v6", "menu": "M4 12 h16 M4 6 h16 M4 18 h16", "home": "M3 9 l9-7 9 7 v11 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 z M9 22 V12 h6 v10", "settings": "M12.22 2 h-.44 a2 2 0 0 0-2 2 v.18 a2 2 0 0 1-1 1.73 l-.43.25 a2 2 0 0 1-2 0 l-.15-.08 a2 2 0 0 0-2.73.73 l-.22.38 a2 2 0 0 0 .73 2.73 l.15.1 a2 2 0 0 1 1 1.72 v.51 a2 2 0 0 1-1 1.74 l-.15.09 a2 2 0 0 0-.73 2.73 l.22.38 a2 2 0 0 0 2.73.73 l.15-.08 a2 2 0 0 1 2 0 l.43.25 a2 2 0 0 1 1 1.73 V20 a2 2 0 0 0 2 2 h.44 a2 2 0 0 0 2-2 v-.18 a2 2 0 0 1 1-1.73 l.43-.25 a2 2 0 0 1 2 0 l.15.08 a2 2 0 0 0 2.73-.73 l.22-.39 a2 2 0 0 0-.73-2.73 l-.15-.08 a2 2 0 0 1-1-1.74 v-.5 a2 2 0 0 1 1-1.74 l.15-.09 a2 2 0 0 0 .73-2.73 l-.22-.38 a2 2 0 0 0-2.73-.73 l-.15.08 a2 2 0 0 1-2 0 l-.43-.25 a2 2 0 0 1-1-1.73 V4 a2 2 0 0 0-2-2 Z M15 12 a3 3 0 1 1-6 0 3 3 0 0 1 6 0 Z", "star": "M11.525 2.295 a.53.53 0 0 1 .95 0 l2.31 4.679 a2.123 2.123 0 0 0 1.595 1.16 l5.166.756 a.53.53 0 0 1 .294.904 l-3.736 3.638 a2.123 2.123 0 0 0-.611 1.878 l.882 5.14 a.53.53 0 0 1-.771.56 l-4.618-2.428 a2.122 2.122 0 0 0-1.973 0 L6.396 21.01 a.53.53 0 0 1-.77-.56 l.881-5.139 a2.122 2.122 0 0 0-.611-1.879 L2.16 9.795 a.53.53 0 0 1 .294-.906 l5.165-.755 a2.122 2.122 0 0 0 1.597-1.16 Z", "heart": "M2 9.5 a5.5 5.5 0 0 1 9.591-3.676 .56.56 0 0 0 .818 0 A5.49 5.49 0 0 1 22 9.5 c0 2.29-1.5 4-3 5.5 l-5.492 5.313 a2 2 0 0 1-3.016 0 L5 14.5 c-1.5-1.5-3-3.2-3-5 Z", "bell": "M10.268 21 a2 2 0 0 0 3.464 0 M3.262 15.326 A1 1 0 0 0 4 17 h16 a1 1 0 0 0 .74-1.673 C19.41 13.956 18 12.499 18 8 A6 6 0 0 0 6 8 c0 4.499-1.411 5.956-2.738 7.326 Z", "info": "M12 16 v-4 M12 8 h.01 M12 2 a10 10 0 1 0 0 20 10 10 0 0 0 0-20 Z"});

/** `Icons` — the core enum's members, by wire value. */
export const Icons = Object.freeze({
  EYE: "eye",
  EYE_OFF: "eye-off",
  LOCK: "lock",
  UNLOCK: "unlock",
  SEARCH: "search",
  X: "x",
  CHECK: "check",
  CHEVRON_DOWN: "chevron-down",
  CHEVRON_UP: "chevron-up",
  CHEVRON_LEFT: "chevron-left",
  CHEVRON_RIGHT: "chevron-right",
  ARROW_LEFT: "arrow-left",
  ARROW_RIGHT: "arrow-right",
  PLUS: "plus",
  MINUS: "minus",
  USER: "user",
  MAIL: "mail",
  PHONE: "phone",
  CALENDAR: "calendar",
  CLOCK: "clock",
  TRASH: "trash",
  MENU: "menu",
  HOME: "home",
  SETTINGS: "settings",
  STAR: "star",
  HEART: "heart",
  BELL: "bell",
  INFO: "info",
});

/** `ImageFit` — the core enum's members, by wire value. */
export const ImageFit = Object.freeze({
  CONTAIN: "contain",
  COVER: "cover",
  FILL: "fill",
  NONE: "none",
});

/** `JustifyContent` — the core enum's members, by wire value. */
export const JustifyContent = Object.freeze({
  START: "start",
  END: "end",
  CENTER: "center",
  SPACE_BETWEEN: "space-between",
  SPACE_AROUND: "space-around",
  SPACE_EVENLY: "space-evenly",
});

/** `KeyboardType` — the core enum's members, by wire value. */
export const KeyboardType = Object.freeze({
  TEXT: "text",
  NUMBER: "number",
  EMAIL: "email",
  PHONE: "phone",
  URL: "url",
  PASSWORD: "password",
});

/**
 * Build a `LifecycleEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function LifecycleEvent(partial = {}) {
  return { ...LifecycleEvent_DEFAULTS, ...partial };
}

const LifecycleEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `LineTo` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function LineTo(partial = {}) {
  return { ...LineTo_DEFAULTS, ...partial };
}

const LineTo_DEFAULTS = Object.freeze({
  kind: "line_to",
});

/**
 * Build a `LocaleChangeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function LocaleChangeEvent(partial = {}) {
  return { ...LocaleChangeEvent_DEFAULTS, ...partial };
}

const LocaleChangeEvent_DEFAULTS = Object.freeze({
  region: null,
  rtl: false,
});

/**
 * Build a `LongPressEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function LongPressEvent(partial = {}) {
  return { ...LongPressEvent_DEFAULTS, ...partial };
}

const LongPressEvent_DEFAULTS = Object.freeze({
  x: null,
  y: null,
});

/** `MATERIAL_ALIASES` — a core design token. */
export const MATERIAL_ALIASES = Object.freeze({"photo_camera": "eye", "camera": "eye", "camera_alt": "eye", "visibility": "eye", "visibility_off": "eye-off", "history": "clock", "schedule": "clock", "access_time": "clock", "person": "user", "account_circle": "user", "email": "mail", "email_outlined": "mail", "lock_outline": "lock", "lock_open": "unlock", "edit": "settings", "create": "settings", "tune": "settings", "content_copy": "check", "done": "check", "close": "x", "cancel": "x", "add": "plus", "remove": "minus", "delete": "trash", "delete_outline": "trash", "favorite": "heart", "favorite_border": "heart", "notifications": "bell", "notifications_none": "bell", "expand_more": "chevron-down", "expand_less": "chevron-up", "navigate_before": "chevron-left", "navigate_next": "chevron-right", "arrow_back": "arrow-left", "arrow_forward": "arrow-right", "call": "phone", "phone_in_talk": "phone", "event": "calendar", "date_range": "calendar", "grade": "star", "info_outline": "info"});

/** `MIN_TOUCH_TARGET` — a core design token. */
export const MIN_TOUCH_TARGET = 48.0;

/** `MUTED` — a core design token. */
export const MUTED = Object.freeze({"r": 55, "g": 65, "b": 81, "a": 1.0});

/**
 * Build a `MenuItem` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function MenuItem(partial = {}) {
  return { ...MenuItem_DEFAULTS, ...partial };
}

const MenuItem_DEFAULTS = Object.freeze({
  icon: null,
});

/**
 * Build a `MenuSelectEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function MenuSelectEvent(partial = {}) {
  return { ...MenuSelectEvent_DEFAULTS, ...partial };
}

const MenuSelectEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `MotionScale` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function MotionScale(partial = {}) {
  return { ...MotionScale_DEFAULTS, ...partial };
}

const MotionScale_DEFAULTS = Object.freeze({
  duration_long: 500,
  duration_medium: 300,
  duration_short: 150,
  easing_emphasized: "ease-out",
  easing_standard: "ease-in-out",
});

/**
 * Build a `MoveTo` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function MoveTo(partial = {}) {
  return { ...MoveTo_DEFAULTS, ...partial };
}

const MoveTo_DEFAULTS = Object.freeze({
  kind: "move_to",
});

/** `ON_MUTED` — a core design token. */
export const ON_MUTED = Object.freeze({"r": 156, "g": 163, "b": 175, "a": 1.0});

/** `ON_SURFACE` — a core design token. */
export const ON_SURFACE = Object.freeze({"r": 249, "g": 250, "b": 251, "a": 1.0});

/** `PRESSED_OPACITY` — a core design token. */
export const PRESSED_OPACITY = 0.12;

/**
 * Build a `PageChangeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function PageChangeEvent(partial = {}) {
  return { ...PageChangeEvent_DEFAULTS, ...partial };
}

const PageChangeEvent_DEFAULTS = Object.freeze({
  previous: 0,
});

/**
 * Build a `PanEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function PanEvent(partial = {}) {
  return { ...PanEvent_DEFAULTS, ...partial };
}

const PanEvent_DEFAULTS = Object.freeze({
  dx: 0.0,
  dy: 0.0,
  vx: 0.0,
  vy: 0.0,
});

/** `Position` — the core enum's members, by wire value. */
export const Position = Object.freeze({
  STATIC: "static",
  ABSOLUTE: "absolute",
});

/**
 * Build a `QrScanEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function QrScanEvent(partial = {}) {
  return { ...QrScanEvent_DEFAULTS, ...partial };
}

const QrScanEvent_DEFAULTS = Object.freeze({
  format: "QR_CODE",
});

/**
 * Build a `RangeChangeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function RangeChangeEvent(partial = {}) {
  return { ...RangeChangeEvent_DEFAULTS, ...partial };
}

const RangeChangeEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `ReorderEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ReorderEvent(partial = {}) {
  return { ...ReorderEvent_DEFAULTS, ...partial };
}

const ReorderEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `RouteChangeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function RouteChangeEvent(partial = {}) {
  return { ...RouteChangeEvent_DEFAULTS, ...partial };
}

const RouteChangeEvent_DEFAULTS = Object.freeze({
  params: {},
});

/** `SELECTION_SIZE` — a core design token. */
export const SELECTION_SIZE = Object.freeze({"xs": 16.0, "sm": 18.0, "md": 20.0, "lg": 24.0});

/** `SLIDER_SIZE` — a core design token. */
export const SLIDER_SIZE = Object.freeze({"xs": 2.0, "sm": 3.0, "md": 4.0, "lg": 6.0});

/** `SURFACE` — a core design token. */
export const SURFACE = Object.freeze({"r": 31, "g": 41, "b": 55, "a": 1.0});

/** `SafeAreaEdge` — the core enum's members, by wire value. */
export const SafeAreaEdge = Object.freeze({
  TOP: "top",
  RIGHT: "right",
  BOTTOM: "bottom",
  LEFT: "left",
});

/**
 * Build a `ScaleEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ScaleEvent(partial = {}) {
  return { ...ScaleEvent_DEFAULTS, ...partial };
}

const ScaleEvent_DEFAULTS = Object.freeze({
  focus_x: 0.0,
  focus_y: 0.0,
  rotation: 0.0,
  scale: 1.0,
});

/**
 * Build a `ScrollEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ScrollEvent(partial = {}) {
  return { ...ScrollEvent_DEFAULTS, ...partial };
}

const ScrollEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `SectionHeader` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function SectionHeader(partial = {}) {
  return { ...SectionHeader_DEFAULTS, ...partial };
}

const SectionHeader_DEFAULTS = Object.freeze({
  window: null,
  window_size: 20,
});

/**
 * Build a `SelectEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function SelectEvent(partial = {}) {
  return { ...SelectEvent_DEFAULTS, ...partial };
}

const SelectEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `Semantics` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function Semantics(partial = {}) {
  return { ...Semantics_DEFAULTS, ...partial };
}

const Semantics_DEFAULTS = Object.freeze({
  hint: null,
  label: null,
  role: null,
});

/**
 * Build a `SensorEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function SensorEvent(partial = {}) {
  return { ...SensorEvent_DEFAULTS, ...partial };
}

const SensorEvent_DEFAULTS = Object.freeze({
  timestamp_ms: 0,
  values: [],
});

/** `SensorType` — the core enum's members, by wire value. */
export const SensorType = Object.freeze({
  ACCELEROMETER: "accelerometer",
  GYROSCOPE: "gyroscope",
  MAGNETOMETER: "magnetometer",
  PRESSURE: "pressure",
  LIGHT: "light",
  PROXIMITY: "proximity",
  STEP_COUNTER: "step_counter",
});

/**
 * Build a `Shadow` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function Shadow(partial = {}) {
  return { ...Shadow_DEFAULTS, ...partial };
}

const Shadow_DEFAULTS = Object.freeze({
  blur: 0.0,
  color: null,
  offset_x: 0.0,
  offset_y: 0.0,
});

/**
 * Build a `ShapeScale` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ShapeScale(partial = {}) {
  return { ...ShapeScale_DEFAULTS, ...partial };
}

const ShapeScale_DEFAULTS = Object.freeze({
  full: 999.0,
  lg: 16.0,
  md: 12.0,
  none: 0.0,
  sm: 8.0,
  xl: 28.0,
  xs: 4.0,
});

/**
 * Build a `SideBorder` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function SideBorder(partial = {}) {
  return { ...SideBorder_DEFAULTS, ...partial };
}

const SideBorder_DEFAULTS = Object.freeze({
  bottom: null,
  left: null,
  right: null,
  top: null,
});

/** `Size` — the core enum's members, by wire value. */
export const Size = Object.freeze({
  XS: "xs",
  SM: "sm",
  MD: "md",
  LG: "lg",
});

/**
 * Build a `SlideEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function SlideEvent(partial = {}) {
  return { ...SlideEvent_DEFAULTS, ...partial };
}

const SlideEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `SpacingScale` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function SpacingScale(partial = {}) {
  return { ...SpacingScale_DEFAULTS, ...partial };
}

const SpacingScale_DEFAULTS = Object.freeze({
  lg: 24.0,
  md: 16.0,
  none: 0.0,
  sm: 8.0,
  xl: 32.0,
  xs: 4.0,
  xxl: 48.0,
});

/** `StackAlign` — the core enum's members, by wire value. */
export const StackAlign = Object.freeze({
  TOP_START: "top-start",
  TOP_CENTER: "top-center",
  TOP_END: "top-end",
  CENTER_START: "center-start",
  CENTER: "center",
  CENTER_END: "center-end",
  BOTTOM_START: "bottom-start",
  BOTTOM_CENTER: "bottom-center",
  BOTTOM_END: "bottom-end",
});

/**
 * Build a `StrokeCmd` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function StrokeCmd(partial = {}) {
  return { ...StrokeCmd_DEFAULTS, ...partial };
}

const StrokeCmd_DEFAULTS = Object.freeze({
  kind: "stroke",
  width: 1.0,
});

/**
 * Build a `SubmitEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function SubmitEvent(partial = {}) {
  return { ...SubmitEvent_DEFAULTS, ...partial };
}

const SubmitEvent_DEFAULTS = Object.freeze({
  values: {},
});

/** `SwipeDirection` — the core enum's members, by wire value. */
export const SwipeDirection = Object.freeze({
  LEFT: "left",
  RIGHT: "right",
  UP: "up",
  DOWN: "down",
});

/**
 * Build a `SwipeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function SwipeEvent(partial = {}) {
  return { ...SwipeEvent_DEFAULTS, ...partial };
}

const SwipeEvent_DEFAULTS = Object.freeze({
  dx: 0.0,
  dy: 0.0,
});

/**
 * Build a `TableCell` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TableCell(partial = {}) {
  return { ...TableCell_DEFAULTS, ...partial };
}

const TableCell_DEFAULTS = Object.freeze({
  colspan: 1,
  rowspan: 1,
  style: null,
});

/**
 * Build a `TableRow` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TableRow(partial = {}) {
  return { ...TableRow_DEFAULTS, ...partial };
}

const TableRow_DEFAULTS = Object.freeze({
  cells: [],
  style: null,
});

/**
 * Build a `TapEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TapEvent(partial = {}) {
  return { ...TapEvent_DEFAULTS, ...partial };
}

const TapEvent_DEFAULTS = Object.freeze({
  x: null,
  y: null,
});

/** `TextAlign` — the core enum's members, by wire value. */
export const TextAlign = Object.freeze({
  LEFT: "left",
  CENTER: "center",
  RIGHT: "right",
  JUSTIFY: "justify",
});

/**
 * Build a `TextChangeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TextChangeEvent(partial = {}) {
  return { ...TextChangeEvent_DEFAULTS, ...partial };
}

const TextChangeEvent_DEFAULTS = Object.freeze({
  valid: null,
});

/** `TextDecoration` — the core enum's members, by wire value. */
export const TextDecoration = Object.freeze({
  NONE: "none",
  UNDERLINE: "underline",
  LINE_THROUGH: "line-through",
});

/** `TextOverflow` — the core enum's members, by wire value. */
export const TextOverflow = Object.freeze({
  CLIP: "clip",
  ELLIPSIS: "ellipsis",
});

/**
 * Build a `ThemeChangeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ThemeChangeEvent(partial = {}) {
  return { ...ThemeChangeEvent_DEFAULTS, ...partial };
}

const ThemeChangeEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `TimeChangeEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TimeChangeEvent(partial = {}) {
  return { ...TimeChangeEvent_DEFAULTS, ...partial };
}

const TimeChangeEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `ToggleEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ToggleEvent(partial = {}) {
  return { ...ToggleEvent_DEFAULTS, ...partial };
}

const ToggleEvent_DEFAULTS = Object.freeze({});

/**
 * Build a `TokenRef` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TokenRef(partial = {}) {
  return { ...TokenRef_DEFAULTS, ...partial };
}

const TokenRef_DEFAULTS = Object.freeze({});

/**
 * Build a `TokenSet` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TokenSet(partial = {}) {
  return { ...TokenSet_DEFAULTS, ...partial };
}

const TokenSet_DEFAULTS = Object.freeze({
  breakpoints: {"sm": 360.0, "md": 600.0, "lg": 905.0, "xl": 1240.0},
  elevation: {"level0": 0.0, "level1": 1.0, "level2": 3.0, "level3": 6.0, "level4": 8.0, "level5": 12.0},
  motion: {"duration_short": 150, "duration_medium": 300, "duration_long": 500, "easing_standard": "ease-in-out", "easing_emphasized": "ease-out"},
  shape: {"none": 0.0, "xs": 4.0, "sm": 8.0, "md": 12.0, "lg": 16.0, "xl": 28.0, "full": 999.0},
  spacing: {"none": 0.0, "xs": 4.0, "sm": 8.0, "md": 16.0, "lg": 24.0, "xl": 32.0, "xxl": 48.0},
  typography: {"display_large": {"font_size": 57.0, "line_height": 64.0, "font_weight": 400, "letter_spacing": 0.0}, "display_medium": {"font_size": 45.0, "line_height": 52.0, "font_weight": 400, "letter_spacing": 0.0}, "display_small": {"font_size": 36.0, "line_height": 44.0, "font_weight": 400, "letter_spacing": 0.0}, "headline_large": {"font_size": 32.0, "line_height": 40.0, "font_weight": 400, "letter_spacing": 0.0}, "headline_medium": {"font_size": 28.0, "line_height": 36.0, "font_weight": 400, "letter_spacing": 0.0}, "headline_small": {"font_size": 24.0, "line_height": 32.0, "font_weight": 400, "letter_spacing": 0.0}, "title_large": {"font_size": 22.0, "line_height": 28.0, "font_weight": 400, "letter_spacing": 0.0}, "title_medium": {"font_size": 16.0, "line_height": 24.0, "font_weight": 500, "letter_spacing": 0.15}, "title_small": {"font_size": 14.0, "line_height": 20.0, "font_weight": 500, "letter_spacing": 0.1}, "body_large": {"font_size": 16.0, "line_height": 24.0, "font_weight": 400, "letter_spacing": 0.5}, "body_medium": {"font_size": 14.0, "line_height": 20.0, "font_weight": 400, "letter_spacing": 0.25}, "body_small": {"font_size": 12.0, "line_height": 16.0, "font_weight": 400, "letter_spacing": 0.4}, "label_large": {"font_size": 14.0, "line_height": 20.0, "font_weight": 500, "letter_spacing": 0.1}, "label_medium": {"font_size": 12.0, "line_height": 16.0, "font_weight": 500, "letter_spacing": 0.5}, "label_small": {"font_size": 11.0, "line_height": 16.0, "font_weight": 500, "letter_spacing": 0.5}},
});

/**
 * Build a `TonalPalette` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TonalPalette(partial = {}) {
  return { ...TonalPalette_DEFAULTS, ...partial };
}

const TonalPalette_DEFAULTS = Object.freeze({});

/**
 * Build a `TypographyScale` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TypographyScale(partial = {}) {
  return { ...TypographyScale_DEFAULTS, ...partial };
}

const TypographyScale_DEFAULTS = Object.freeze({
  body_large: {"font_size": 16.0, "line_height": 24.0, "font_weight": 400, "letter_spacing": 0.5},
  body_medium: {"font_size": 14.0, "line_height": 20.0, "font_weight": 400, "letter_spacing": 0.25},
  body_small: {"font_size": 12.0, "line_height": 16.0, "font_weight": 400, "letter_spacing": 0.4},
  display_large: {"font_size": 57.0, "line_height": 64.0, "font_weight": 400, "letter_spacing": 0.0},
  display_medium: {"font_size": 45.0, "line_height": 52.0, "font_weight": 400, "letter_spacing": 0.0},
  display_small: {"font_size": 36.0, "line_height": 44.0, "font_weight": 400, "letter_spacing": 0.0},
  headline_large: {"font_size": 32.0, "line_height": 40.0, "font_weight": 400, "letter_spacing": 0.0},
  headline_medium: {"font_size": 28.0, "line_height": 36.0, "font_weight": 400, "letter_spacing": 0.0},
  headline_small: {"font_size": 24.0, "line_height": 32.0, "font_weight": 400, "letter_spacing": 0.0},
  label_large: {"font_size": 14.0, "line_height": 20.0, "font_weight": 500, "letter_spacing": 0.1},
  label_medium: {"font_size": 12.0, "line_height": 16.0, "font_weight": 500, "letter_spacing": 0.5},
  label_small: {"font_size": 11.0, "line_height": 16.0, "font_weight": 500, "letter_spacing": 0.5},
  title_large: {"font_size": 22.0, "line_height": 28.0, "font_weight": 400, "letter_spacing": 0.0},
  title_medium: {"font_size": 16.0, "line_height": 24.0, "font_weight": 500, "letter_spacing": 0.15},
  title_small: {"font_size": 14.0, "line_height": 20.0, "font_weight": 500, "letter_spacing": 0.1},
});

/**
 * Build a `TypographyToken` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function TypographyToken(partial = {}) {
  return { ...TypographyToken_DEFAULTS, ...partial };
}

const TypographyToken_DEFAULTS = Object.freeze({
  font_weight: 400,
  letter_spacing: 0.0,
});

/** `VALID_COLOR_SCHEMES` — a core design token. */
export const VALID_COLOR_SCHEMES = ["error", "info", "neutral", "primary", "secondary", "success", "tertiary", "warning"];

/**
 * Build a `ValidationEvent` wire fragment.
 * @param {Object} [partial]  Fields to override, in the wire's snake_case.
 * @returns {Object}
 */
export function ValidationEvent(partial = {}) {
  return { ...ValidationEvent_DEFAULTS, ...partial };
}

const ValidationEvent_DEFAULTS = Object.freeze({
  error: null,
});

/** `Variant` — the core enum's members, by wire value. */
export const Variant = Object.freeze({
  SOLID: "solid",
  OUTLINE: "outline",
  GHOST: "ghost",
  LINK: "link",
});
