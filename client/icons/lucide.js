// icons/lucide.js — vendored Lucide icon paths (the framework's default set).
//
// Each entry is one SVG path `d` string on a 24x24 viewBox, stroke-based (no
// fill), drawn in `currentColor` with stroke width ~2 and round caps/joins.
// Names are kebab-case Lucide names. Geometry mirrors Lucide (ISC-licensed) and
// is kept byte-identical to the core's `tempest_core.icons.ICON_PATHS`, so the
// core's `Icon` widget and input `leading_icon`/`trailing_icon` names render the
// same glyph the Python side resolves. Apps add more via registerIcon().
//
// This is the DEFAULT set: a bare name (no "set:" prefix) resolves here, as does
// the explicit "lucide:" prefix.

/** @type {Readonly<Record<string, string>>} */
export const LUCIDE_PATHS = Object.freeze({
  "eye":
    "M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0 M15 12 a3 3 0 1 1-6 0 3 3 0 0 1 6 0 Z",
  "eye-off":
    "M10.733 5.076 a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49 M14.084 14.158 a3 3 0 0 1-4.242-4.242 M17.479 17.499 a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143 M2 2 l20 20",
  "lock":
    "M5 11 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v8 a2 2 0 0 1-2 2 H7 a2 2 0 0 1-2-2 Z M7 11 V7 a5 5 0 0 1 10 0 v4",
  "unlock":
    "M5 11 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v8 a2 2 0 0 1-2 2 H7 a2 2 0 0 1-2-2 Z M7 11 V7 a5 5 0 0 1 9.9-1",
  "search": "M21 21 l-4.34-4.34 M11 19 a8 8 0 1 0 0-16 8 8 0 0 0 0 16 Z",
  "x": "M18 6 6 18 M6 6 l12 12",
  "check": "M20 6 9 17 l-5-5",
  "chevron-down": "M6 9 l6 6 6-6",
  "chevron-up": "M18 15 l-6-6-6 6",
  "chevron-left": "M15 18 l-6-6 6-6",
  "chevron-right": "M9 18 l6-6-6-6",
  "arrow-left": "M19 12 H5 M12 19 l-7-7 7-7",
  "arrow-right": "M5 12 h14 M12 5 l7 7-7 7",
  "plus": "M5 12 h14 M12 5 v14",
  "minus": "M5 12 h14",
  "user":
    "M19 21 v-2 a4 4 0 0 0-4-4 H9 a4 4 0 0 0-4 4 v2 M12 11 a4 4 0 1 0 0-8 4 4 0 0 0 0 8 Z",
  "mail":
    "M22 7 l-8.991 5.727 a2 2 0 0 1-2.018 0 L2 7 M4 4 h16 c1.1 0 2 .9 2 2 v12 c0 1.1-.9 2-2 2 H4 c-1.1 0-2-.9-2-2 V6 c0-1.1.9-2 2-2 Z",
  "phone":
    "M13.832 16.568 a1 1 0 0 0 1.213-.303 l.355-.465 A2 2 0 0 1 17 15 h3 a2 2 0 0 1 2 2 v3 a2 2 0 0 1-2 2 A18 18 0 0 1 2 4 a2 2 0 0 1 2-2 h3 a2 2 0 0 1 2 2 v3 a2 2 0 0 1-.8 1.6 l-.468.351 a1 1 0 0 0-.292 1.233 a14 14 0 0 0 6.06 6.0 Z",
  "calendar":
    "M8 2 v4 M16 2 v4 M3 10 h18 M5 4 h14 a2 2 0 0 1 2 2 v14 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 V6 a2 2 0 0 1 2-2 Z",
  "clock": "M12 6 v6 l4 2 M12 2 a10 10 0 1 0 0 20 10 10 0 0 0 0-20 Z",
  "trash":
    "M3 6 h18 M19 6 v14 c0 1-1 2-2 2 H7 c-1 0-2-1-2-2 V6 M8 6 V4 c0-1 1-2 2-2 h4 c1 0 2 1 2 2 v2 M10 11 v6 M14 11 v6",
  "menu": "M4 12 h16 M4 6 h16 M4 18 h16",
  "home": "M3 9 l9-7 9 7 v11 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 z M9 22 V12 h6 v10",
  "settings":
    "M12.22 2 h-.44 a2 2 0 0 0-2 2 v.18 a2 2 0 0 1-1 1.73 l-.43.25 a2 2 0 0 1-2 0 l-.15-.08 a2 2 0 0 0-2.73.73 l-.22.38 a2 2 0 0 0 .73 2.73 l.15.1 a2 2 0 0 1 1 1.72 v.51 a2 2 0 0 1-1 1.74 l-.15.09 a2 2 0 0 0-.73 2.73 l.22.38 a2 2 0 0 0 2.73.73 l.15-.08 a2 2 0 0 1 2 0 l.43.25 a2 2 0 0 1 1 1.73 V20 a2 2 0 0 0 2 2 h.44 a2 2 0 0 0 2-2 v-.18 a2 2 0 0 1 1-1.73 l.43-.25 a2 2 0 0 1 2 0 l.15.08 a2 2 0 0 0 2.73-.73 l.22-.39 a2 2 0 0 0-.73-2.73 l-.15-.08 a2 2 0 0 1-1-1.74 v-.5 a2 2 0 0 1 1-1.74 l.15-.09 a2 2 0 0 0 .73-2.73 l-.22-.38 a2 2 0 0 0-2.73-.73 l-.15.08 a2 2 0 0 1-2 0 l-.43-.25 a2 2 0 0 1-1-1.73 V4 a2 2 0 0 0-2-2 Z M15 12 a3 3 0 1 1-6 0 3 3 0 0 1 6 0 Z",
  "star":
    "M11.525 2.295 a.53.53 0 0 1 .95 0 l2.31 4.679 a2.123 2.123 0 0 0 1.595 1.16 l5.166.756 a.53.53 0 0 1 .294.904 l-3.736 3.638 a2.123 2.123 0 0 0-.611 1.878 l.882 5.14 a.53.53 0 0 1-.771.56 l-4.618-2.428 a2.122 2.122 0 0 0-1.973 0 L6.396 21.01 a.53.53 0 0 1-.77-.56 l.881-5.139 a2.122 2.122 0 0 0-.611-1.879 L2.16 9.795 a.53.53 0 0 1 .294-.906 l5.165-.755 a2.122 2.122 0 0 0 1.597-1.16 Z",
  "heart":
    "M2 9.5 a5.5 5.5 0 0 1 9.591-3.676 .56.56 0 0 0 .818 0 A5.49 5.49 0 0 1 22 9.5 c0 2.29-1.5 4-3 5.5 l-5.492 5.313 a2 2 0 0 1-3.016 0 L5 14.5 c-1.5-1.5-3-3.2-3-5 Z",
  "bell":
    "M10.268 21 a2 2 0 0 0 3.464 0 M3.262 15.326 A1 1 0 0 0 4 17 h16 a1 1 0 0 0 .74-1.673 C19.41 13.956 18 12.499 18 8 A6 6 0 0 0 6 8 c0 4.499-1.411 5.956-2.738 7.326 Z",
  "info": "M12 16 v-4 M12 8 h.01 M12 2 a10 10 0 1 0 0 20 10 10 0 0 0 0-20 Z",
});

/** The 24x24 grid every Lucide path above is drawn on. */
export const LUCIDE_VIEWBOX = "0 0 24 24";
