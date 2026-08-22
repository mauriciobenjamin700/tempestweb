// Guard: the base stylesheet lives inside a JS template literal, so a stray
// backtick in a CSS comment is a SyntaxError that takes the whole client down —
// every test file that imports anything from client/ fails to load, and the
// message points at the comment rather than at what broke.
//
// This has happened three times while writing new sections of the sheet, so it
// is pinned here. The check reads the file as text on purpose: importing the
// module would be the very failure it is meant to report.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const THEME = fileURLToPath(new URL("../../client/theme.js", import.meta.url));

test("no unescaped backtick inside the base stylesheet template", () => {
  const source = readFileSync(THEME, "utf8");
  const opener = 'export const BASE_THEME_CSS = `';
  const start = source.indexOf(opener);
  assert.notEqual(start, -1, "the stylesheet template moved; update this guard");
  const body = source.slice(start + opener.length).split("\n`;")[0];

  const offending = body.replace(/\\`/g, "").indexOf("`");
  assert.equal(
    offending,
    -1,
    offending === -1
      ? ""
      : `unescaped backtick near: ${JSON.stringify(body.slice(Math.max(0, offending - 70), offending + 20))}`,
  );
});

test("the stylesheet is still one template literal ending in a backtick", () => {
  const source = readFileSync(THEME, "utf8");
  assert.match(source, /export const BASE_THEME_CSS = `[\s\S]+\n`;/);
});
