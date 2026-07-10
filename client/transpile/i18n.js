// i18n.js — Mode C localization (a port of tempest_core.i18n).
//
// `translate` / `t` look a key up in a `{language: {key: template}}` table by the
// locale's language and interpolate `{name}` placeholders — mirroring
// tempest_core.i18n exactly, including the fallbacks: a missing language/key
// degrades to the key itself, and a template whose placeholder has no value
// falls back to the un-interpolated template (never crashes the view).
//
// The transpiler routes `from tempest_core import translate, t, Locale` here. A
// keyword call `t("hi", locale=..., translations=..., name="Ana")` transpiles to
// `t("hi", { locale, translations, name: "Ana" })`, so the facade takes the key
// plus an options object (locale + translations + the interpolation params).
//
// Parity is locked by a core-derived fixture — see tests/fixtures/
// transpile_i18n_cases.json and docs/native-modo-c.md.

/**
 * A locale — its language selects the translation table. Mirrors
 * `tempest_core.i18n.Locale`.
 */
export class Locale {
  /**
   * @param {{language?: string, region?: ?string, rtl?: boolean}} [args]
   */
  constructor({ language = "pt", region = null, rtl = false } = {}) {
    this.language = language;
    this.region = region;
    this.rtl = rtl;
  }
}

/**
 * Interpolate `{name}` placeholders, mirroring Python's `str.format(**kwargs)`.
 *
 * All-or-nothing, like the core: if any referenced placeholder has no value the
 * un-interpolated template is returned (Python raises `KeyError`, which the core
 * catches and falls back on).
 *
 * @param {string} template  The template string.
 * @param {Object<string, *>} params  The interpolation values.
 * @returns {string}
 */
function interpolate(template, params) {
  if (Object.keys(params).length === 0) {
    return template;
  }
  let missing = false;
  const out = template.replace(/\{(\w+)\}/g, (match, name) => {
    if (Object.prototype.hasOwnProperty.call(params, name)) {
      return String(params[name]);
    }
    missing = true;
    return match;
  });
  return missing ? template : out;
}

/**
 * Look up and interpolate a localized string.
 *
 * @param {string} key  The translation key.
 * @param {{locale: Locale, translations: Object<string, Object<string, string>>}}
 *        opts  The active locale, the `{language: {key: template}}` table, and any
 *        extra keys used as interpolation params.
 * @returns {string}  The interpolated, localized string (or the key on a miss).
 */
export function translate(key, { locale, translations, ...params } = {}) {
  const language = locale ? locale.language : "pt";
  const table = (translations && translations[language]) || {};
  const template = Object.prototype.hasOwnProperty.call(table, key)
    ? table[key]
    : key;
  return interpolate(template, params);
}

/** Alias for {@link translate}, mirroring `tempest_core.i18n.t`. */
export const t = translate;
