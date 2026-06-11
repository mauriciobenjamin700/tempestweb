// manifest.js — emit a valid, installable Web App Manifest.  PHASE P0.
//
// Pure JS (no build step). Produces an object that serializes to a spec-compliant
// `manifest.webmanifest`. The build step (Trilho C) writes the JSON to disk and
// injects <link rel="manifest"> into index.html; this module owns the *shape*.
//
// Installable-shaped means, per the PWA install criteria (Chromium/Lighthouse):
//   - name (or short_name)
//   - start_url
//   - display is one of "standalone" | "fullscreen" | "minimal-ui"
//   - icons[] includes at least a 192x192 and a 512x512 PNG, and at least one
//     icon with purpose containing "any" (maskable alone is not enough).
//
// See ../../docs/plan.md §7 P0 for the contract and tests/unit/test_pwa_manifest_*
// / tests/client/pwa-manifest.test.js for the goldens.

/**
 * @typedef {Object} ManifestIcon
 * @property {string} src       Icon URL, relative to the manifest scope.
 * @property {string} sizes     Space-separated WxH list, e.g. "192x192".
 * @property {string} type      MIME type, e.g. "image/png".
 * @property {string} [purpose] "any", "maskable", or "any maskable".
 */

/**
 * @typedef {Object} ManifestShortcut
 * @property {string} name                  Shortcut label.
 * @property {string} [short_name]          Shorter label for tight surfaces.
 * @property {string} [description]         Accessible description.
 * @property {string} url                   Target URL (within scope).
 * @property {ManifestIcon[]} [icons]       Optional shortcut icons.
 */

/**
 * @typedef {Object} ManifestOptions
 * @property {string} [name]               Full application name.
 * @property {string} [short_name]         Home-screen label (<= ~12 chars ideal).
 * @property {string} [description]        Human description.
 * @property {string} [start_url]          URL opened on launch. Default "/".
 * @property {string} [scope]              Navigation scope. Default "/".
 * @property {string} [display]            "standalone" | "fullscreen" | "minimal-ui" | "browser".
 * @property {string} [orientation]        e.g. "portrait", "any".
 * @property {string} [theme_color]        Toolbar color (CSS color).
 * @property {string} [background_color]   Splash background (CSS color).
 * @property {string} [lang]               BCP-47 language tag, e.g. "pt-BR".
 * @property {string} [dir]                "ltr" | "rtl" | "auto".
 * @property {string} [id]                 Stable app identity.
 * @property {ManifestIcon[]} [icons]      Icon set (defaults to the standard set).
 * @property {ManifestShortcut[]} [shortcuts]  P5 shortcuts (optional).
 * @property {Object} [share_target]       P5 share target (optional, passed through).
 * @property {Object[]} [file_handlers]    P5 file handlers (optional, passed through).
 * @property {string[]} [categories]       App store categories.
 */

/**
 * The default icon set: maskable 192/512 + a plain "any" 512 + apple-touch.
 * These are *references*; the build step is responsible for emitting the files.
 * @type {ManifestIcon[]}
 */
export const DEFAULT_ICONS = [
  { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
  { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
  { src: "/icons/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
  { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
];

/** @type {Required<Pick<ManifestOptions, "name"|"short_name"|"description"|"start_url"|"scope"|"display"|"theme_color"|"background_color"|"lang"|"dir">>} */
const DEFAULTS = {
  name: "tempestweb app",
  short_name: "tempestweb",
  description: "A tempestweb application.",
  start_url: "/",
  scope: "/",
  display: "standalone",
  theme_color: "#111111",
  background_color: "#ffffff",
  lang: "pt-BR",
  dir: "auto",
};

/** Installable display modes — what buildManifest will accept without coercion. */
const INSTALLABLE_DISPLAYS = new Set(["standalone", "fullscreen", "minimal-ui"]);
/** All spec display modes (used only by the validator). */
const DISPLAY_VALUES = new Set(["standalone", "fullscreen", "minimal-ui", "browser"]);

/**
 * Build a Web App Manifest object from options, filling installable-shaped
 * defaults. Project config overrides every field; unknown extra keys
 * (shortcuts/share_target/file_handlers/categories/id/orientation) pass through.
 *
 * @param {ManifestOptions} [options] Project overrides.
 * @returns {Object} A manifest object ready to JSON.stringify.
 */
export function buildManifest(options = {}) {
  const opts = options || {};
  const icons = Array.isArray(opts.icons) && opts.icons.length > 0 ? opts.icons : DEFAULT_ICONS;

  /** @type {Object} */
  const manifest = {
    name: opts.name ?? DEFAULTS.name,
    short_name: opts.short_name ?? DEFAULTS.short_name,
    description: opts.description ?? DEFAULTS.description,
    start_url: opts.start_url ?? DEFAULTS.start_url,
    scope: opts.scope ?? DEFAULTS.scope,
    display: INSTALLABLE_DISPLAYS.has(opts.display) ? opts.display : DEFAULTS.display,
    theme_color: opts.theme_color ?? DEFAULTS.theme_color,
    background_color: opts.background_color ?? DEFAULTS.background_color,
    lang: opts.lang ?? DEFAULTS.lang,
    dir: opts.dir ?? DEFAULTS.dir,
    icons: icons.map((icon) => ({ ...icon })),
  };

  // Stable app identity defaults to the scope when not provided.
  manifest.id = opts.id ?? manifest.scope;

  if (opts.orientation) manifest.orientation = opts.orientation;
  if (Array.isArray(opts.categories) && opts.categories.length > 0) {
    manifest.categories = [...opts.categories];
  }

  // P5 extras pass through untouched when present.
  if (Array.isArray(opts.shortcuts) && opts.shortcuts.length > 0) {
    manifest.shortcuts = opts.shortcuts.map((s) => ({ ...s }));
  }
  if (opts.share_target) manifest.share_target = { ...opts.share_target };
  if (Array.isArray(opts.file_handlers) && opts.file_handlers.length > 0) {
    manifest.file_handlers = opts.file_handlers.map((h) => ({ ...h }));
  }

  return manifest;
}

/**
 * Serialize a manifest object to a JSON string for `manifest.webmanifest`.
 * @param {Object} manifest A manifest object (typically from buildManifest).
 * @param {number} [indent] Spaces of indentation (default 2; 0 for minified).
 * @returns {string} JSON text.
 */
export function emitManifest(manifest, indent = 2) {
  return JSON.stringify(manifest, null, indent);
}

/**
 * Validate the P5 manifest extras (shortcuts / share_target / file_handlers).
 *
 * These are progressive enhancements with uneven browser support, so this is a
 * shape check, not an install requirement. Returns the list of problems; empty
 * means the extras that ARE present are well-formed.
 *
 * @param {Object} manifest A manifest object.
 * @returns {string[]} Human-readable problems ([] when the extras are valid).
 */
export function validateExtras(manifest) {
  /** @type {string[]} */
  const errors = [];
  if (!manifest || typeof manifest !== "object") return ["manifest must be an object"];

  if (manifest.shortcuts !== undefined) {
    if (!Array.isArray(manifest.shortcuts)) {
      errors.push("shortcuts must be an array");
    } else {
      manifest.shortcuts.forEach((s, i) => {
        if (!s || typeof s.name !== "string") errors.push(`shortcuts[${i}].name is required`);
        if (!s || typeof s.url !== "string") errors.push(`shortcuts[${i}].url is required`);
      });
    }
  }

  if (manifest.share_target !== undefined) {
    const st = manifest.share_target;
    if (!st || typeof st !== "object") {
      errors.push("share_target must be an object");
    } else {
      if (typeof st.action !== "string") errors.push("share_target.action is required");
      const method = (st.method ?? "GET").toUpperCase();
      if (method === "POST" && typeof st.enctype !== "string") {
        errors.push("share_target with method POST requires an enctype");
      }
    }
  }

  if (manifest.file_handlers !== undefined) {
    if (!Array.isArray(manifest.file_handlers)) {
      errors.push("file_handlers must be an array");
    } else {
      manifest.file_handlers.forEach((h, i) => {
        if (!h || typeof h.action !== "string") errors.push(`file_handlers[${i}].action is required`);
        if (!h || typeof h.accept !== "object") errors.push(`file_handlers[${i}].accept is required`);
      });
    }
  }

  return errors;
}

/**
 * The default P5 extras a freshly-scaffolded app ships: a "Home" shortcut, a
 * POST share target, and a CSV file handler. References only — routes are wired
 * by the host app (share_target pairs with native.share, N2).
 * @type {{shortcuts: ManifestShortcut[], share_target: Object, file_handlers: Object[]}}
 */
export const DEFAULT_EXTRAS = {
  shortcuts: [
    { name: "Home", short_name: "Home", url: "/", description: "Open the app home" },
  ],
  share_target: {
    action: "/share-target",
    method: "POST",
    enctype: "multipart/form-data",
    params: { title: "title", text: "text", url: "url" },
  },
  file_handlers: [
    { action: "/open", accept: { "text/csv": [".csv"] } },
  ],
};

/**
 * Check whether a manifest object meets the baseline install criteria used by
 * Chromium/Lighthouse. Returns the list of problems; empty means installable.
 *
 * @param {Object} manifest A manifest object.
 * @returns {string[]} Human-readable validation errors ([] when installable).
 */
export function validateInstallable(manifest) {
  /** @type {string[]} */
  const errors = [];
  if (!manifest || typeof manifest !== "object") {
    return ["manifest must be an object"];
  }
  if (!manifest.name && !manifest.short_name) {
    errors.push("name or short_name is required");
  }
  if (!manifest.start_url) {
    errors.push("start_url is required");
  }
  if (!DISPLAY_VALUES.has(manifest.display) || manifest.display === "browser") {
    errors.push('display must be "standalone", "fullscreen" or "minimal-ui"');
  }

  const icons = Array.isArray(manifest.icons) ? manifest.icons : [];
  const hasSize = (size) =>
    icons.some((icon) => typeof icon.sizes === "string" && icon.sizes.split(/\s+/).includes(size));
  if (!hasSize("192x192")) errors.push("a 192x192 icon is required");
  if (!hasSize("512x512")) errors.push("a 512x512 icon is required");

  const hasAnyPurpose = icons.some((icon) => {
    const purpose = icon.purpose ?? "any";
    return purpose.split(/\s+/).includes("any");
  });
  if (!hasAnyPurpose) errors.push('at least one icon must have purpose "any"');

  return errors;
}
