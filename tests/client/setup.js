// Shared test helpers for the pure-JS client tests (jsdom).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const FIXTURES = fileURLToPath(new URL("../fixtures/", import.meta.url));

/** Load a JSON fixture from tests/fixtures/. */
export function fixture(name) {
  return JSON.parse(readFileSync(new URL(name, `file://${FIXTURES}`), "utf8"));
}

/** Fresh jsdom document; returns { document, root }. */
export function freshDom() {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>");
  return { document: dom.window.document, root: dom.window.document.getElementById("root"), window: dom.window };
}
