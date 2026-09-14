// Mode C honours the app's declared THEME — the Mode C third of the three-mode
// parity the fixture pins (tests/fixtures/transpile_theme_samples.json).
//
// An app declares its palette once, as a module-level THEME. Modes A and B read
// it; Mode C did not, so the same screen was legible on the server and
// unreadable transpiled — a breadcrumb at 1.20:1, a section title at 1.02:1
// (tempestweb#206). Two halves fail independently, so both are asserted here:
//
//   1. the document is marked `data-tw-theme="dark"`, which is what the base
//      stylesheet keys the page background, field surfaces and hover/focus on;
//   2. the colours the widgets resolve come out of the dark leaf of the
//      generated tables — deep-equal to the IR the *real core* builds under the
//      same theme, which is what the Python half of this pair regenerates.
//
// The `no_theme` case is the regression guard: an app that declares no theme has
// to come out exactly as it did before any theme was read at all.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture, freshDom } from "./setup.js";
import {
  Breadcrumb,
  Button,
  Card,
  Column,
  Input,
  ListTile,
  Text,
} from "../../client/transpile/widgets.js";
import { Theme, ThemeMode } from "../../client/transpile/theme.js";
import { mountApp, State } from "../../client/transpile/runtime.js";

const SAMPLES = fixture("transpile_theme_samples.json");

/** The scene's state: empty, mirroring `ThemeState` in the generator. */
class ThemeState extends State {}

/**
 * Build the parity scene, passing `theme` to nothing.
 *
 * The transcription of `view` in tests/conformance/_transpile_theme.py. Not one
 * widget is handed a theme: inheriting the app's palette without being handed it
 * is the behaviour under test.
 *
 * @returns {import("../../client/transport.js").Node}  The scene's root node.
 */
function view() {
  return Column({
    key: "root",
    children: [
      Breadcrumb({ items: ["home", "docs", "ui"], key: "crumbs" }),
      Card({
        key: "card",
        children: [
          Text({ content: "Relatório", key: "title" }),
          Button({ label: "Salvar", key: "save" }),
          Input({ placeholder: "nome", key: "name" }),
        ],
      }),
      ListTile({ title: "Maria", subtitle: "admin", key: "row" }),
    ],
  });
}

/**
 * Strip a Mode C tree down to the four wire fields the core serializes.
 *
 * The builders stash handlers in a non-wire `__handlers` map; everything else is
 * already the core's shape.
 *
 * @param {Object} node  A Mode C IR node.
 * @returns {Object}  The comparable node.
 */
function wire(node) {
  return {
    type: node.type,
    key: node.key ?? null,
    props: node.props,
    children: (node.children ?? []).map(wire),
  };
}

/**
 * Mount the parity scene under a declared theme and report what it produced.
 *
 * @param {?Object} theme  The module's `THEME`, or null for an app that declares
 *        none.
 * @returns {{attribute: ?string, node: Object}}  The document's theme attribute
 *          and the comparable IR tree.
 */
function mounted(theme) {
  const dom = freshDom();
  const saved = globalThis.document;
  globalThis.document = dom.document;
  try {
    const mod = { makeState: () => new ThemeState(), view };
    if (theme !== null) {
      mod.THEME = theme;
    }
    const handle = mountApp(dom.root, mod);
    return {
      attribute: dom.document.documentElement.getAttribute("data-tw-theme"),
      node: wire(handle.node),
    };
  } finally {
    globalThis.document = saved;
  }
}

/**
 * Find a node by key in a serialized tree.
 *
 * @param {Object} node  The root to search.
 * @param {string} key   The key to find.
 * @returns {Object}     The node carrying that key.
 */
function byKey(node, key) {
  if (node.key === key) {
    return node;
  }
  for (const child of node.children ?? []) {
    const hit = byKey(child, key);
    if (hit !== null) {
      return hit;
    }
  }
  return null;
}

test("a declared dark THEME marks the document and darkens every resolved colour", () => {
  const expected = SAMPLES.dark;
  const actual = mounted(new Theme({ mode: ThemeMode.DARK }));
  assert.equal(actual.attribute, expected.attribute);
  assert.deepEqual(actual.node, expected.node);
});

test("a declared light THEME leaves the document unmarked and resolves light", () => {
  const expected = SAMPLES.light;
  const actual = mounted(new Theme({ mode: ThemeMode.LIGHT }));
  assert.equal(actual.attribute, expected.attribute);
  assert.deepEqual(actual.node, expected.node);
});

test("an app that declares no THEME is untouched by the theme being read", () => {
  const expected = SAMPLES.no_theme;
  const actual = mounted(null);
  assert.equal(actual.attribute, expected.attribute);
  assert.deepEqual(actual.node, expected.node);
});

test("the dark case is not vacuous: it differs from the light one", () => {
  assert.notDeepEqual(SAMPLES.dark.node, SAMPLES.light.node);
  assert.deepEqual(SAMPLES.no_theme.node, SAMPLES.light.node);
});

test("set_theme re-resolves the tree and re-marks the document both ways", () => {
  const dom = freshDom();
  const saved = globalThis.document;
  globalThis.document = dom.document;
  try {
    const handle = mountApp(dom.root, { makeState: () => new ThemeState(), view });
    assert.equal(dom.document.documentElement.getAttribute("data-tw-theme"), null);

    handle.app.set_theme(new Theme({ mode: ThemeMode.DARK }));
    assert.equal(dom.document.documentElement.getAttribute("data-tw-theme"), "dark");
    assert.deepEqual(wire(handle.node), SAMPLES.dark.node);

    handle.app.set_theme(new Theme({ mode: ThemeMode.LIGHT }));
    assert.equal(dom.document.documentElement.getAttribute("data-tw-theme"), "light");
    assert.deepEqual(wire(handle.node), SAMPLES.light.node);
  } finally {
    globalThis.document = saved;
  }
});

test("a widget built outside a build still resolves light", () => {
  const outside = wire(Button({ label: "Salvar", key: "save" }));
  assert.deepEqual(outside.props.style, byKey(SAMPLES.light.node, "save").props.style);
  assert.notDeepEqual(
    outside.props.style,
    byKey(SAMPLES.dark.node, "save").props.style,
  );
});
