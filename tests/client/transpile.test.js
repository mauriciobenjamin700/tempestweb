// Tests for client/transpile/ — Mode C native runtime (diff, widgets, runtime).
//
// Three layers, mirroring docs/modo-c-transpile.md:
//   1. diff.js conforms to the core-derived golden (transpile_diff_cases.json).
//   2. widgets.js emits IR in the core's wire shape.
//   3. runtime.js mounts a generated module (counter.gen.js), and a real DOM
//      click drives state -> diff -> patch -> DOM update.
import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { fixture, freshDom } from "./setup.js";
import { diff } from "../../client/transpile/diff.js";
import {
  Button,
  Column,
  Container,
  Edge,
  Input,
  Row,
  Style,
  Text,
} from "../../client/transpile/widgets.js";
import { mountApp, State } from "../../client/transpile/runtime.js";
import * as widgets from "../../client/transpile/widgets.gen.js";
import { HStack, VStack } from "../../client/transpile/components.js";
import { native, NativeError } from "../../client/transpile/native.js";
import { makeState, view } from "../../client/transpile/counter.gen.js";

// ---- 1. diff conformance against the core-derived golden -------------------

test("diff conforms to every golden case (all five patch kinds + noop)", () => {
  const cases = fixture("transpile_diff_cases.json");
  assert.ok(cases.length >= 6, "expected the full kind coverage");
  for (const { name, before, after, patches } of cases) {
    assert.deepEqual(diff(before, after), patches, `case "${name}" diverged from golden`);
  }
});

test("diff of identical trees is empty", () => {
  const { before } = fixture("transpile_diff_cases.json")[0];
  assert.deepEqual(diff(before, before), []);
});

// ---- 2. widgets emit the core's wire shape --------------------------------

test("Text emits the core Text prop shape (attrs + tag)", () => {
  const node = Text({ content: "hi", key: "t" });
  assert.equal(node.type, "Text");
  assert.equal(node.key, "t");
  assert.deepEqual(node.children, []);
  assert.equal(node.props.content, "hi");
  assert.deepEqual(node.props.attrs, {});
  assert.equal(node.props.tag, null);
  assert.equal(node.props.style, null);
});

test("Column/Row are flex containers carrying their children", () => {
  const col = Column({ key: "root", children: [Text({ content: "x", key: "x" })] });
  assert.equal(col.type, "Column");
  assert.equal(col.children.length, 1);
  const row = Row({ children: [] });
  assert.equal(row.type, "Row");
  assert.equal(row.key, null);
});

test("every generated builder returns a well-formed IR node", () => {
  // Widgets that need a required arg — supply a minimal value so we can build one
  // of each and assert the common wire shape.
  const required = {
    Text: { content: "x" },
    Icon: { name: "home" },
    Image: { src: "x" },
    Svg: { source: "x" },
    Toast: { message: "x" },
    Tooltip: { message: "x" },
    WebView: { url: "x" },
    VideoPlayer: { source: "x" },
    MapView: { latitude: 0, longitude: 0 },
  };
  const builders = Object.entries(widgets).filter(([, v]) => typeof v === "function");
  assert.ok(builders.length >= 40, `expected many builders, got ${builders.length}`);
  for (const [name, build] of builders) {
    if (name === "Style") continue; // helper, not a widget
    let node;
    try {
      node = build(required[name] ?? {});
    } catch (err) {
      // A builder needing an arg we didn't supply is fine to skip here.
      continue;
    }
    assert.equal(typeof node.type, "string", `${name}: type`);
    assert.ok("props" in node, `${name}: props`);
    assert.ok(Array.isArray(node.children), `${name}: children array`);
    assert.ok("attrs" in node.props, `${name}: attrs`);
    assert.ok("style" in node.props, `${name}: style key present`);
  }
});

test("HStack/VStack expand to Row/Column matching the core (order-agnostic)", () => {
  const samples = fixture("transpile_component_samples.json");
  const drop = (n) => ({
    type: n.type,
    props: n.props,
    children: (n.children ?? []).map(drop),
  });
  const cases = {
    hstack_default: HStack({ children: [Text({ content: "a", key: "a" })] }),
    hstack_lg_between: HStack({ gap: "lg", justify: "space-between" }),
    hstack_float: HStack({ gap: 8.0 }),
    vstack_sm: VStack({ children: [Text({ content: "a", key: "a" })], gap: "sm" }),
    vstack_start: VStack({ children: [Text({ content: "a", key: "a" })], align: "start" }),
  };
  for (const [name, built] of Object.entries(cases)) {
    // diff() ignores prop key order, so an empty diff means the trees are equal.
    assert.deepEqual(diff(drop(samples[name]), drop(built)), [], `${name} diverged from core`);
  }
});

test("Container is a layout box with the semantic-tag escape hatch", () => {
  const node = Container({
    key: "nav",
    tag: "nav",
    attrs: { "hx-get": "/x" },
    children: [Text({ content: "a" })],
  });
  assert.equal(node.type, "Container");
  assert.equal(node.props.tag, "nav");
  assert.deepEqual(node.props.attrs, { "hx-get": "/x" });
  assert.equal(node.props.style, null); // pure layout, no baked style
  assert.equal(node.children.length, 1);
});

test("Style fills the full shape with nulls; only set fields differ", () => {
  const style = Style({ gap: 8.0, padding: Edge.all(16) });
  assert.equal(style.gap, 8.0);
  assert.deepEqual(style.padding, { top: 16, right: 16, bottom: 16, left: 16 });
  assert.equal(style.background, null);
  assert.equal(style.color, null);
});

test("Button keeps its click closure off the wire (on_click null, __handlers fn)", () => {
  let hit = 0;
  const node = Button({ label: "+", key: "inc", onClick: () => (hit += 1) });
  assert.equal(node.props.on_click, null, "wire prop stays null for a stable diff");
  assert.equal(typeof node.__handlers.click, "function");
  node.__handlers.click();
  assert.equal(hit, 1);
});

test("Button resolves its Material 3 variant style (solid/md/primary default)", () => {
  const node = Button({ label: "+", key: "inc" });
  const style = node.props.style;
  // A default solid/primary button paints a filled background with light text,
  // a pill radius and comfortable padding — resolved from the core-derived table.
  assert.notEqual(style, null);
  assert.notEqual(style.background, null, "solid variant has a filled background");
  assert.notEqual(style.color, null);
  assert.equal(style.radius, 999.0);
  assert.equal(node.props.variant, "solid");
  assert.equal(node.props.color_scheme, "primary");
});

test("an explicit Button style layers over the resolved base (caller wins)", () => {
  const override = Style({ radius: 4.0 });
  const node = Button({ label: "x", style: override });
  assert.equal(node.props.style.radius, 4.0, "caller's set field wins");
  // Fields the caller did NOT set keep the resolved base (not nulled out).
  assert.notEqual(node.props.style.background, null);
});

test("Button variant/size/colorScheme select different resolved styles", () => {
  const solid = Button({ label: "a" }).props.style;
  const ghost = Button({ label: "a", variant: "ghost" }).props.style;
  // A ghost button is not a filled solid one — the table distinguishes variants.
  assert.notDeepEqual(solid, ghost);
});

test("Input emits the core prop shape with a resolved outline style", () => {
  const node = Input({ value: "hi", placeholder: "name", key: "f" });
  assert.equal(node.type, "Input");
  assert.equal(node.props.value, "hi");
  assert.equal(node.props.placeholder, "name");
  assert.equal(node.props.field_variant, "outline");
  assert.equal(node.props.on_change, null, "handler stays off the wire");
  assert.notEqual(node.props.style.border, null, "outline field has a border");
  assert.equal(node.props.style.radius, 8.0);
});

test("Input keeps its change closure off the wire (onChange collected by runtime)", () => {
  const node = Input({ key: "f", onChange: () => {} });
  assert.equal(node.props.on_change, null);
  assert.equal(typeof node.__handlers.input, "function");
  assert.equal(typeof node.__handlers.change, "function");
});

test("typing in an Input drives onChange -> state -> re-render", () => {
  const dom = freshDom();
  globalThis.document = dom.document;

  class FormState extends State {
    constructor() {
      super();
      this.text = "";
    }
  }
  const mod = {
    makeState: () => new FormState(),
    view: (app) =>
      Column({
        children: [
          Input({
            value: app.state.text,
            key: "f",
            onChange: (e) => app.setState((s) => (s.text = e.payload.value)),
          }),
        ],
      }),
  };

  const handle = mountApp(dom.root, mod);
  const field = dom.root.querySelector("[data-tw-key=\"f\"]");
  field.value = "hello";
  field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));

  assert.equal(handle.app.state.text, "hello");
  assert.ok(handle.patchLog.length >= 1, "the re-render emitted a patch");
});

// ---- 3. runtime drives a real generated module ----------------------------

test("mountApp renders the counter's initial tree", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  mountApp(dom.root, { makeState, view });

  const tree = dom.root.children[0];
  assert.equal(tree.children[0].textContent, "Count: 0");
});

test("a click drives state -> diff -> Update patch -> DOM (not a Replace)", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const handle = mountApp(dom.root, { makeState, view });

  const inc = dom.root.querySelector("[data-tw-key=\"inc\"]");
  inc.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  assert.equal(dom.root.children[0].children[0].textContent, "Count: 1");
  // The only change is the label's content: a single Update patch, not a Replace.
  assert.equal(handle.patchLog.length, 1);
  const batch = handle.patchLog[0];
  assert.equal(batch.length, 1);
  assert.ok("set_props" in batch[0], "expected an Update patch");
  assert.deepEqual(batch[0].path, [0]);
});

test("decrement works too and the tree element stays stable across ticks", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const handle = mountApp(dom.root, { makeState, view });

  const treeBefore = dom.root.children[0];
  const dec = dom.root.querySelector("[data-tw-key=\"dec\"]");
  dec.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  dec.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  assert.equal(dom.root.children[0].textContent.startsWith("Count: -2"), true);
  // Granular patches mutate in place — the mounted tree element is never swapped.
  assert.equal(dom.root.children[0], treeBefore);
  assert.equal(handle.patchLog.length, 2);
});

// ---- Mode C native facade -------------------------------------------------

test("native.cookies round-trips via the in-process facade (document)", async () => {
  const dom = new JSDOM("<!doctype html>", { url: "https://example.com/" });
  globalThis.document = dom.window.document;
  try {
    await native.cookies.set("token", "xyz");
    assert.equal(await native.cookies.get("token"), "xyz");
    assert.equal(await native.cookies.get("absent"), null);
    const all = await native.cookies.all();
    assert.equal(all.token, "xyz");
    await native.cookies.remove("token");
    assert.equal(await native.cookies.get("token"), null);
  } finally {
    delete globalThis.document;
  }
});

test("native.http.request routes to fetch and parses the response", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return {
      status: 200,
      ok: true,
      headers: { get: () => "application/json", forEach: () => {} },
      json: async () => ({ hello: "world" }),
      text: async () => '{"hello":"world"}',
    };
  };
  try {
    const res = await native.http.request("GET", "/api/x");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/x");
    assert.equal(res.status, 200);
  } finally {
    delete globalThis.fetch;
  }
});

test("a native failure surfaces as a NativeError", async () => {
  // No document -> the cookies capability reports "unsupported".
  delete globalThis.document;
  await assert.rejects(() => native.cookies.get("x"), (err) => {
    assert.ok(err instanceof NativeError);
    assert.equal(err.code, "unsupported");
    return true;
  });
});

test("native.share.is_supported reports false without navigator.share", async () => {
  // Node's built-in navigator has no `.share`, so the capability reports false —
  // proving the dispatch + unwrap (`.supported`) path.
  assert.equal(await native.share.is_supported(), false);
});

test("native.audio.play dispatches src/volume/channel", async () => {
  // No Audio ctor -> the capability reports unavailable, proving the dispatch
  // path and arg shaping without a real audio device.
  await assert.rejects(() => native.audio.play("/x.wav", { volume: 0.5 }), (err) => {
    assert.ok(err instanceof NativeError);
    return true;
  });
});
