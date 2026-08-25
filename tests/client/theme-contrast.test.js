// theme-contrast.test.js — the base palette's declared pairs meet WCAG AA.
//
// The a11y gate disables axe's `color-contrast` rule because jsdom has no layout
// to sample colours from, and the Lighthouse job that would catch it in a real
// browser runs with `|| echo soft-fail`. So when the sheet gained a whole dark
// palette (#148) nothing in CI could tell a legible one from an illegible one.
//
// This is the half that does not need layout: the sheet declares its foregrounds
// and backgrounds as *pairs of roles* — `--tw-on-surface` is by definition what
// goes on `--tw-surface` — so the contrast of every pair the design promises can
// be computed from the tokens themselves. What still needs a browser is whether a
// given widget actually used the pair it was supposed to; that stays with
// Lighthouse.
import { test } from "node:test";
import assert from "node:assert/strict";
import { BASE_THEME_CSS } from "../../client/theme.js";

/** WCAG AA for normal text. */
const AA_TEXT = 4.5;

/** WCAG AA for a non-text UI boundary (an outline, a control's edge). */
const AA_NON_TEXT = 3.0;

/**
 * The pairs the palette promises, as `[foreground, background, minimum]`.
 *
 * A role named `on-<x>` is by definition drawn on `<x>`; the status families and
 * `primary` are drawn as text or icons on the page surface; `outline` is a
 * boundary, so it answers to the non-text threshold.
 */
const PAIRS = [
  ["on-surface", "surface", AA_TEXT],
  ["on-surface-variant", "surface", AA_TEXT],
  ["on-primary", "primary", AA_TEXT],
  ["on-primary-container", "primary-container", AA_TEXT],
  ["on-secondary-container", "secondary-container", AA_TEXT],
  ["primary", "surface", AA_TEXT],
  ["error", "surface", AA_TEXT],
  ["success", "surface", AA_TEXT],
  ["warning", "surface", AA_TEXT],
  ["info", "surface", AA_TEXT],
  ["neutral", "surface", AA_TEXT],
  ["outline", "surface", AA_NON_TEXT],
];

/**
 * The sheet with its comments removed.
 *
 * The palette's own comment shows an override as `:root { --tw-primary: ... }`, so
 * a block scan that stops at the first `}` stops inside the comment and reads an
 * empty palette — which looks like "the tokens are gone" instead of "the parser is
 * wrong". Measured: every pair reported `--tw-on-surface is not declared`.
 */
const CSS = BASE_THEME_CSS.replace(/\/\*[\s\S]*?\*\//g, "");

/**
 * Read the `--tw-*` hex tokens declared inside one selector's block.
 *
 * @param {string} selector  The selector that opens the block, verbatim.
 * @returns {Object<string, string>}  Role name (without the `--tw-` prefix) -> hex.
 */
function tokensUnder(selector) {
  const start = CSS.indexOf(`${selector} {`);
  assert.notEqual(start, -1, `no block for ${selector}`);
  const block = CSS.slice(start, CSS.indexOf("}", start));
  /** @type {Object<string, string>} */
  const tokens = {};
  for (const [, role, hex] of block.matchAll(/--tw-([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    tokens[role] = hex;
  }
  return tokens;
}

/**
 * Relative luminance of a `#rrggbb` colour, per WCAG 2.
 *
 * @param {string} hex  The colour.
 * @returns {number}  Its relative luminance.
 */
function luminance(hex) {
  const channels = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255);
  const linear = channels.map((c) =>
    c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

/**
 * Contrast ratio between two colours, per WCAG 2.
 *
 * @param {string} foreground  The text or icon colour.
 * @param {string} background  What it sits on.
 * @returns {number}  The ratio, from 1 to 21.
 */
function contrast(foreground, background) {
  const [high, low] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (high + 0.05) / (low + 0.05);
}

/**
 * Assert every promised pair in one palette.
 *
 * @param {string} mode  The mode's name, for the failure message.
 * @param {Object<string, string>} tokens  Role -> hex for that mode.
 * @returns {void}
 */
function assertPalette(mode, tokens) {
  for (const [foreground, background, minimum] of PAIRS) {
    const fg = tokens[foreground];
    const bg = tokens[background];
    assert.ok(fg, `${mode}: --tw-${foreground} is not declared`);
    assert.ok(bg, `${mode}: --tw-${background} is not declared`);
    const ratio = contrast(fg, bg);
    assert.ok(
      ratio >= minimum,
      `${mode}: --tw-${foreground} on --tw-${background} is ${ratio.toFixed(2)}:1, ` +
        `below the ${minimum}:1 this pair promises (${fg} on ${bg})`,
    );
  }
}

test("the light palette's promised pairs meet WCAG AA", () => {
  assertPalette("light", tokensUnder(":root"));
});

// The dark block redefines only some tokens, so the palette a reader actually
// gets is the light one with the dark block layered over it — which is also where
// a half-finished dark palette would show up: a foreground darkened without its
// background is exactly the illegible case.
test("the dark palette's promised pairs meet WCAG AA", () => {
  const merged = {
    ...tokensUnder(":root"),
    ...tokensUnder(':root[data-tw-theme="dark"]'),
  };
  assertPalette("dark", merged);
});

// A gate nobody has seen fail is a gate nobody knows works.
test("the check fails a foreground darkened without its background", () => {
  const broken = { ...tokensUnder(":root"), "on-surface": "#f0eef4" };

  assert.throws(() => assertPalette("probe", broken), /on --tw-surface is 1\.\d+:1/);
});
