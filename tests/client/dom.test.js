// Tests for client/dom.js — buildElement + applyPatches over the golden fixtures.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture, freshDom } from "./setup.js";
import { applyPatches, buildElement, KEY_ATTR, TYPE_ATTR } from "../../client/dom.js";

/** Install jsdom's `document` globally so dom.js's `document.createElement` works. */
function withDocument() {
  const dom = freshDom();
  globalThis.document = dom.document;
  return dom;
}

test("buildElement maps the counter tree to the expected DOM shape", () => {
  withDocument();
  const node = fixture("node_initial.json");
  const el = buildElement(node);

  // Column -> div, two children: a Text span and a Row div.
  assert.equal(el.tagName, "DIV");
  assert.equal(el.children.length, 2);

  const label = el.children[0];
  assert.equal(label.tagName, "SPAN");
  assert.equal(label.getAttribute(KEY_ATTR), "label");
  assert.equal(label.textContent, "Count: 0");

  const row = el.children[1];
  assert.equal(row.tagName, "DIV");
  assert.equal(row.children.length, 2);

  const [dec, inc] = row.children;
  assert.equal(dec.tagName, "BUTTON");
  assert.equal(dec.getAttribute(KEY_ATTR), "dec");
  assert.equal(dec.textContent, "-");
  assert.equal(inc.getAttribute(KEY_ATTR), "inc");
  assert.equal(inc.textContent, "+");
});

test("buildElement styles a Column: flex column from its type, gap, padding", () => {
  withDocument();
  const node = fixture("node_initial.json");
  const el = buildElement(node);
  assert.equal(el.style.display, "flex");
  assert.equal(el.style.flexDirection, "column");
  assert.equal(el.style.gap, "8px");
  assert.equal(el.style.paddingTop, "16px");
  assert.equal(el.style.paddingRight, "16px");
  assert.equal(el.style.paddingBottom, "16px");
  assert.equal(el.style.paddingLeft, "16px");
});

test("buildElement omits data-tw-key when the node has no key", () => {
  withDocument();
  const node = fixture("node_initial.json");
  const el = buildElement(node);
  assert.equal(el.hasAttribute(KEY_ATTR), false); // Column key is null.
});

test("Update patch sets a prop (content) on the node at path", () => {
  withDocument();
  const root = buildElement(fixture("node_initial.json"));
  const patches = fixture("patches_count_0_to_1.json");
  applyPatches(root, patches);
  assert.equal(root.children[0].textContent, "Count: 1");
});

test("all five patch kinds applied in sequence yield the expected DOM", () => {
  withDocument();
  const all = fixture("patches_all_kinds.json");
  const order = ["update", "insert", "remove", "reorder", "replace"];

  // update: Text[0].content -> "y"
  {
    const root = buildElement(fixture("node_initial.json"));
    applyPatches(root, all.update);
    assert.equal(root.children[0].textContent, "y");
  }

  // insert: a Button "b1" at index 1 of the root (between Text and Row).
  {
    const root = buildElement(fixture("node_initial.json"));
    applyPatches(root, all.insert);
    assert.equal(root.children.length, 3);
    const inserted = root.children[1];
    assert.equal(inserted.tagName, "BUTTON");
    assert.equal(inserted.getAttribute(KEY_ATTR), "b1");
    assert.equal(inserted.textContent, "+");
  }

  // remove: drop child at index 1 (the Row) -> only the Text remains.
  {
    const root = buildElement(fixture("node_initial.json"));
    applyPatches(root, all.remove);
    assert.equal(root.children.length, 1);
    assert.equal(root.children[0].getAttribute(KEY_ATTR), "label");
  }

  // reorder: [1, 0] swaps Text and Row.
  {
    const root = buildElement(fixture("node_initial.json"));
    const before = Array.from(root.children).map((c) => c.tagName);
    applyPatches(root, all.reorder);
    const after = Array.from(root.children).map((c) => c.tagName);
    assert.deepEqual(before, ["SPAN", "DIV"]);
    assert.deepEqual(after, ["DIV", "SPAN"]);
  }

  // replace: swap node at path [0] (the Text) for a Button "n".
  {
    const root = buildElement(fixture("node_initial.json"));
    applyPatches(root, all.replace);
    const replaced = root.children[0];
    assert.equal(replaced.tagName, "BUTTON");
    assert.equal(replaced.getAttribute(KEY_ATTR), "n");
    assert.equal(replaced.textContent, "x");
  }

  assert.equal(order.length, 5); // guards against a fixture losing a kind.
});

test("Update with unset_props clears content", () => {
  withDocument();
  const root = buildElement(fixture("node_initial.json"));
  applyPatches(root, [{ path: [0], set_props: {}, unset_props: ["content"] }]);
  assert.equal(root.children[0].textContent, "");
});

test("nested path resolves through grandchildren (Row's button)", () => {
  withDocument();
  const root = buildElement(fixture("node_initial.json"));
  // path [1,0] = first button inside the Row; relabel it.
  applyPatches(root, [{ path: [1, 0], set_props: { label: "DEC" }, unset_props: [] }]);
  assert.equal(root.children[1].children[0].textContent, "DEC");
});

test("applyPatches throws on an unrecognized patch shape", () => {
  withDocument();
  const root = buildElement(fixture("node_initial.json"));
  assert.throws(() => applyPatches(root, [{ path: [] }]), TypeError);
});

test("Input builds a real <input> carrying value/placeholder (E.6)", () => {
  withDocument();
  const el = buildElement({
    type: "Input",
    key: "email",
    props: { value: "a@b.com", placeholder: "Email", secure: false },
    children: [],
  });
  assert.equal(el.tagName, "INPUT");
  assert.equal(el.getAttribute("type"), "text");
  assert.equal(el.value, "a@b.com");
  assert.equal(el.getAttribute("placeholder"), "Email");
});

test("a secure Input renders type=password", () => {
  withDocument();
  const el = buildElement({ type: "Input", key: "pw", props: { secure: true }, children: [] });
  assert.equal(el.getAttribute("type"), "password");
});

test("Checkbox builds a <label> wrapping a checkbox input plus visible caption", () => {
  withDocument();
  const el = buildElement({
    type: "Checkbox",
    key: "c",
    props: { checked: true, label: "Agree" },
    children: [],
  });
  // The keyed, path-addressed element is the <label>; the real input is nested.
  assert.equal(el.tagName, "LABEL");
  assert.equal(el.getAttribute(TYPE_ATTR), "Checkbox");
  const input = el.querySelector("input");
  assert.equal(input.getAttribute("type"), "checkbox");
  assert.equal(input.checked, true);
  // The caption is visible text (the <label> gives the input its name natively).
  assert.equal(el.textContent.trim(), "Agree");
});

test("Checkbox Update toggles checked and relabels without dropping the input", () => {
  withDocument();
  const el = buildElement({
    type: "Checkbox",
    key: "c",
    props: { checked: false, label: "Old" },
    children: [],
  });
  applyPatches(el, [{ path: [], set_props: { checked: true, label: "New" } }]);
  const input = el.querySelector("input");
  assert.equal(el.querySelectorAll("input").length, 1, "exactly one nested input");
  assert.equal(input.checked, true);
  assert.equal(el.textContent.trim(), "New");
});

test("Image builds an <img> with src/alt", () => {
  withDocument();
  const el = buildElement({
    type: "Image",
    key: "pic",
    props: { src: "/cat.png", alt: "a cat" },
    children: [],
  });
  assert.equal(el.tagName, "IMG");
  assert.equal(el.getAttribute("src"), "/cat.png");
  assert.equal(el.getAttribute("alt"), "a cat");
});

test("semantics + focus map to ARIA/tabindex (E.7)", () => {
  withDocument();
  const el = buildElement({
    type: "Button",
    key: "b",
    props: {
      label: "ok",
      semantics: { label: "Confirm", role: "button", hint: "submits the form" },
      focusable: true,
    },
    children: [],
  });
  assert.equal(el.getAttribute("aria-label"), "Confirm");
  assert.equal(el.getAttribute("role"), "button");
  assert.equal(el.getAttribute("aria-description"), "submits the form");
  assert.equal(el.getAttribute("tabindex"), "0");
});

test("focus_order sets an explicit tabindex; focusable=false excludes", () => {
  withDocument();
  const ordered = buildElement({ type: "Container", key: "x", props: { focus_order: 3 }, children: [] });
  assert.equal(ordered.getAttribute("tabindex"), "3");
  const excluded = buildElement({ type: "Container", key: "y", props: { focusable: false }, children: [] });
  assert.equal(excluded.getAttribute("tabindex"), "-1");
});

// --- the `attrs` escape hatch (parity with the SSR renderer) ---------------
//
// Every core widget carries an `attrs` dict and the SSR renderer has always
// emitted it; the DOM renderer dropped it, so the same tree gained attributes
// server-rendered and lost them in Modes A/B/C. The layout presets tag their
// subtrees through it (`data-tw-layout`), so client/layouts.js can style them.

test("attrs are applied to the element (id/class/data-*)", () => {
  withDocument();
  const el = buildElement({
    type: "Container",
    key: "c",
    props: { attrs: { id: "main", class: "wide", "data-tw-layout": "shell" } },
    children: [],
  });
  assert.equal(el.getAttribute("id"), "main");
  assert.equal(el.getAttribute("class"), "wide");
  assert.equal(el.getAttribute("data-tw-layout"), "shell");
});

test("attrs never overwrite the renderer's own attributes", () => {
  withDocument();
  const el = buildElement({
    type: "Container",
    key: "c",
    props: { attrs: { "data-tw-type": "Evil", "data-tw-key": "evil", style: "color:red" } },
    children: [],
  });
  assert.equal(el.getAttribute(TYPE_ATTR), "Container");
  assert.equal(el.getAttribute(KEY_ATTR), "c");
  assert.equal(el.getAttribute("style"), null);
});

test("an invalid attribute name is skipped, not thrown", () => {
  withDocument();
  const warnings = [];
  const realWarn = console.warn;
  console.warn = (...args) => warnings.push(args);
  try {
    const el = buildElement({
      type: "Container",
      key: "c",
      props: { attrs: { "a>b": "x", "onload x": "y", id: "kept" } },
      children: [],
    });
    assert.equal(el.getAttribute("id"), "kept");
    assert.equal(el.hasAttribute("a>b"), false);
  } finally {
    console.warn = realWarn;
  }
  assert.equal(warnings.length, 2);
});

test("an Update that drops an attrs key removes it from the element", () => {
  withDocument();
  const el = buildElement({
    type: "Container",
    key: "c",
    props: { attrs: { "data-tw-layout": "shell", "data-tw-open": "true" } },
    children: [],
  });
  applyPatches(el, [
    { op: "update", path: [], set_props: { attrs: { "data-tw-layout": "shell" } } },
  ]);
  assert.equal(el.getAttribute("data-tw-layout"), "shell");
  assert.equal(el.hasAttribute("data-tw-open"), false);
});
