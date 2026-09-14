// theme.js — Mode C theme + responsiveness primitives (port of tempest_core.theme).
//
// ThemeMode / Theme / MediaQueryData / Breakpoints mirror the core so a transpiled
// app resolves dark/light and reads the viewport the same way as Modes A/B:
// `app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)` and
// `app.media.width`. The runtime keeps `app.media` in sync with the browser via
// client/media.js (matchMedia + resize).
//
// This is the Mode C module (client/transpile/theme.js) — distinct from the shared
// base-stylesheet injector at client/theme.js.

/**
 * The theme mode. Mirrors `tempest_core.theme.ThemeMode` (string values).
 * @type {{LIGHT: string, DARK: string, SYSTEM: string}}
 */
export const ThemeMode = Object.freeze({
  LIGHT: "light",
  DARK: "dark",
  SYSTEM: "system",
});

/**
 * The active theme — its `mode` resolves to dark/light. Mirrors
 * `tempest_core.theme.Theme` (mode only; colour tokens are resolved by the
 * widget styles, so Mode C does not re-carry them).
 */
export class Theme {
  /**
   * @param {{mode?: string}} [args]
   */
  constructor({ mode = ThemeMode.SYSTEM } = {}) {
    this.mode = mode;
  }

  /**
   * Resolve whether the theme renders dark, given the platform setting.
   *
   * `DARK`/`LIGHT` are absolute; `SYSTEM` defers to `platform_dark_mode`.
   *
   * @param {{platform_dark_mode?: boolean}} [opts]  The OS dark-mode flag
   *        (typically `app.media.platform_dark_mode`).
   * @returns {boolean}
   */
  is_dark({ platform_dark_mode = false } = {}) {
    if (this.mode === ThemeMode.DARK) {
      return true;
    }
    if (this.mode === ThemeMode.LIGHT) {
      return false;
    }
    return platform_dark_mode;
  }
}

/**
 * A viewport snapshot. Mirrors `tempest_core.theme.MediaQueryData`.
 */
export class MediaQueryData {
  /**
   * @param {{width?: number, height?: number, device_pixel_ratio?: number,
   *          text_scale_factor?: number, platform_dark_mode?: boolean,
   *          orientation?: string}} [args]
   */
  constructor({
    width = 0.0,
    height = 0.0,
    device_pixel_ratio = 1.0,
    text_scale_factor = 1.0,
    platform_dark_mode = false,
    orientation = "portrait",
  } = {}) {
    this.width = width;
    this.height = height;
    this.device_pixel_ratio = device_pixel_ratio;
    this.text_scale_factor = text_scale_factor;
    this.platform_dark_mode = platform_dark_mode;
    this.orientation = orientation;
  }
}

/**
 * The responsive breakpoints (logical px). Mirrors `tempest_core.theme.Breakpoints`.
 */
export class Breakpoints {
  /**
   * @param {{sm?: number, md?: number, lg?: number, xl?: number}} [args]
   */
  constructor({ sm = 360.0, md = 600.0, lg = 905.0, xl = 1240.0 } = {}) {
    this.sm = sm;
    this.md = md;
    this.lg = lg;
    this.xl = xl;
  }
}

/**
 * The theme installed for the duration of the current build, or `null`.
 *
 * The port of `tempest_core.theme._current`: the core declares every widget's
 * `theme` field with `default_factory=current_theme`, so a widget built inside
 * `view()` inherits the app's palette without the app passing it anywhere. Mode C
 * has no context variable, and the build is single-threaded and synchronous, so a
 * module-level slot set around the build is the exact equivalent.
 *
 * @type {?Object}
 */
let ambientTheme = null;

/**
 * The theme a widget defaults to when the caller passes none.
 *
 * Mirrors `tempest_core.theme.current_theme()`. Outside a build it answers
 * `null`, which resolves light — the same answer the core gives a widget built
 * with no theme installed.
 *
 * @returns {?Object}  The active theme, or `null`.
 */
export function currentTheme() {
  return ambientTheme;
}

/**
 * Install the theme every widget built from now on defaults to.
 *
 * Mirrors entering `tempest_core.theme.use_theme(theme)`. The runtime calls this
 * around each `view(app)` call (and clears it right after), so a build that threw
 * cannot leave a stale palette visible to the next one.
 *
 * @param {?Object} theme  The theme to install, or `null` to clear.
 * @returns {void}
 */
export function setCurrentTheme(theme) {
  ambientTheme = theme ?? null;
}
