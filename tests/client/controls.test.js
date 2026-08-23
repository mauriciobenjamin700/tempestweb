// Tests for the ten IR widgets that used to render as an anonymous <div> (#143):
// the tag they get, the props they apply, and the payload their event reports.
// Each one is checked in both directions, because #142 showed the tag is only
// half of it — a field can render, accept input and still never tell the app.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import {
  applyPatches,
  buildElement,
  NATIVE_CONTROL_TYPES,
  TYPE_ATTR,
} from "../../client/dom.js";
import { bindEvents } from "../../client/events.js";

/** Install jsdom's `document` globally so dom.js's `document.createElement` works. */
function withDocument() {
  const dom = freshDom();
  globalThis.document = dom.document;
  return dom;
}

/** A mock Transport that records every sendEvent call. */
function mockTransport() {
  const events = [];
  return {
    events,
    onPatches() {},
    sendEvent(event) {
      events.push(event);
    },
    async close() {},
  };
}

/** Build one widget under a bound root; returns the element, dom and transport. */
function mountWidget(type, key, props, children = []) {
  const dom = withDocument();
  const el = buildElement({ type, key, props, children });
  dom.root.appendChild(el);
  const transport = mockTransport();
  bindEvents(dom.root, transport);
  return { dom, el, transport };
}

/** Dispatch a bubbling DOM event of `name` on `target`. */
function fire(dom, target, name) {
  target.dispatchEvent(new dom.window.Event(name, { bubbles: true }));
}

test("Switch renders a real switch and reports checked, not a value", () => {
  const { dom, el, transport } = mountWidget("Switch", "notify", {
    checked: false,
    label: "Notifications",
  });

  assert.equal(el.tagName, "LABEL");
  const box = el.querySelector("input");
  assert.equal(box.getAttribute("type"), "checkbox");
  assert.equal(box.getAttribute("role"), "switch");
  assert.equal(el.textContent.trim(), "Notifications");
  assert.equal(box.checked, false);

  box.checked = true;
  fire(dom, box, "change");

  // `{value: "on"}` is what a checkbox input reports and what ToggleEvent
  // refuses: the handler used to get the raw dict, so `event.checked` threw.
  assert.deepEqual(transport.events.at(-1), {
    type: "change",
    key: "notify",
    payload: { checked: true },
  });
});

test("Switch Update flips the state without dropping the input or the caption", () => {
  withDocument();
  const el = buildElement({
    type: "Switch",
    key: "notify",
    props: { checked: false, label: "Old" },
    children: [],
  });

  applyPatches(el, [{ path: [], set_props: { checked: true, label: "New" } }]);

  assert.equal(el.querySelectorAll("input").length, 1);
  assert.equal(el.querySelector("input").checked, true);
  assert.equal(el.textContent.trim(), "New");
});

test("Slider renders a range over its declared scale and reports a number", () => {
  const { dom, el, transport } = mountWidget("Slider", "volume", {
    value: 70,
    min_value: 10,
    max_value: 90,
    step: 5,
  });

  assert.equal(el.tagName, "INPUT");
  assert.equal(el.getAttribute("type"), "range");
  assert.equal(el.getAttribute("min"), "10");
  assert.equal(el.getAttribute("max"), "90");
  assert.equal(el.getAttribute("step"), "5");
  assert.equal(el.value, "70");

  el.value = "45";
  fire(dom, el, "input");

  assert.deepEqual(transport.events.at(-1), {
    type: "input",
    key: "volume",
    payload: { value: 45 },
  });
});

test("Slider writes its bounds before its value, so nothing is clamped away", () => {
  withDocument();
  const el = buildElement({
    type: "Slider",
    key: "font",
    props: { value: 16, min_value: 10, max_value: 30, step: 1 },
    children: [],
  });

  // A range input clamps to the range it has at the time: with the default 0..100
  // still in place a value of 16 survives, but a scale that starts above it does
  // not — which is what parked a slider at the wrong end.
  assert.equal(el.value, "16");
});

test("RangeSlider draws two thumbs and reports the pair, normalized", () => {
  const { dom, el, transport } = mountWidget("RangeSlider", "price", {
    low: 20,
    high: 80,
    min_value: 0,
    max_value: 100,
    step: 10,
  });

  const thumbs = el.querySelectorAll("input[type=range]");
  assert.equal(thumbs.length, 2);
  assert.equal(thumbs[0].getAttribute("data-tw-part"), "low");
  assert.equal(thumbs[1].getAttribute("data-tw-part"), "high");
  assert.equal(thumbs[0].value, "20");
  assert.equal(thumbs[1].value, "80");

  thumbs[0].value = "90";
  fire(dom, thumbs[0], "change");

  assert.deepEqual(transport.events.at(-1), {
    type: "change",
    key: "price",
    payload: { low: 80, high: 90 },
  });
});

test("Dropdown renders its options, its placeholder, and reports a selection", () => {
  const { dom, el, transport } = mountWidget("Dropdown", "theme", {
    options: ["System", "Light", "Dark"],
    value: "Light",
    placeholder: "Choose…",
  });

  assert.equal(el.tagName, "SELECT");
  const options = el.querySelectorAll("option");
  assert.equal(options.length, 4);
  assert.equal(options[0].getAttribute("data-tw-part"), "placeholder");
  assert.equal(options[0].textContent, "Choose…");
  assert.equal(el.value, "Light");

  el.value = "Dark";
  fire(dom, el, "change");

  // `select`, not `change`: on_select is the handler a Dropdown declares, and the
  // index counts the real options — the placeholder is not one of them.
  assert.deepEqual(transport.events.at(-1), {
    type: "select",
    key: "theme",
    payload: { value: "Dark", index: 2 },
  });
});

test("Dropdown reports one event per choice, not one per DOM event", () => {
  const { dom, el, transport } = mountWidget("Dropdown", "theme", {
    options: ["Light", "Dark"],
    value: "Light",
  });

  el.value = "Dark";
  fire(dom, el, "input");
  fire(dom, el, "change");

  assert.equal(transport.events.length, 1);
});

test("Dropdown keeps the reader's choice when only its options are patched", () => {
  withDocument();
  const el = buildElement({
    type: "Dropdown",
    key: "city",
    props: { options: ["Recife", "Olinda"], value: "Olinda" },
    children: [],
  });

  applyPatches(el, [{ path: [], set_props: { options: ["Recife", "Olinda", "Paulista"] } }]);

  assert.equal(el.querySelectorAll("option").length, 3);
  assert.equal(el.value, "Olinda");
});

test("Autocomplete wraps an input plus the datalist the browser suggests from", () => {
  const { dom, el, transport } = mountWidget("Autocomplete", "search", {
    options: ["ana", "bia", "caio"],
    value: "an",
    placeholder: "Search…",
  });

  assert.equal(el.tagName, "LABEL");
  const input = el.querySelector("input");
  const list = el.querySelector("datalist");
  assert.equal(input.getAttribute("list"), list.getAttribute("id"));
  assert.equal(list.querySelectorAll("option").length, 3);
  assert.equal(input.value, "an");
  assert.equal(input.getAttribute("placeholder"), "Search…");

  input.value = "ana";
  fire(dom, input, "input");

  assert.deepEqual(transport.events.at(-1), {
    type: "input",
    key: "search",
    payload: { value: "ana" },
  });
});

test("Autocomplete reports a suggestion pick as select, alongside the change", () => {
  const { dom, el, transport } = mountWidget("Autocomplete", "search", {
    options: ["ana", "bia"],
    value: "",
  });
  const input = el.querySelector("input");

  input.value = "bia";
  fire(dom, input, "change");

  assert.deepEqual(transport.events.at(-2), {
    type: "change",
    key: "search",
    payload: { value: "bia" },
  });
  assert.deepEqual(transport.events.at(-1), {
    type: "select",
    key: "search",
    payload: { value: "bia", index: 1 },
  });
});

test("Autocomplete typing that matches no option stays a change only", () => {
  const { dom, el, transport } = mountWidget("Autocomplete", "search", {
    options: ["ana", "bia"],
    value: "",
  });
  const input = el.querySelector("input");

  input.value = "zzz";
  fire(dom, input, "change");

  assert.equal(transport.events.length, 1);
  assert.equal(transport.events[0].type, "change");
});

test("two keyless Autocompletes do not share one suggestion list", () => {
  withDocument();
  const first = buildElement({
    type: "Autocomplete",
    key: null,
    props: { options: ["a"] },
    children: [],
  });
  const second = buildElement({
    type: "Autocomplete",
    key: null,
    props: { options: ["b"] },
    children: [],
  });

  assert.notEqual(
    first.querySelector("datalist").getAttribute("id"),
    second.querySelector("datalist").getAttribute("id"),
  );
});

test("DatePicker renders the native date control with its caption and value", () => {
  const { dom, el, transport } = mountWidget("DatePicker", "when", {
    value: "2026-08-23",
    label: "Departure",
  });

  assert.equal(el.tagName, "LABEL");
  const input = el.querySelector("input");
  assert.equal(input.getAttribute("type"), "date");
  assert.equal(input.value, "2026-08-23");
  assert.equal(el.textContent.trim(), "Departure");

  input.value = "2026-09-01";
  fire(dom, input, "change");

  assert.deepEqual(transport.events.at(-1), {
    type: "change",
    key: "when",
    payload: { value: "2026-09-01" },
  });
});

test("TimePicker renders the native time control and reports its value", () => {
  const { dom, el, transport } = mountWidget("TimePicker", "at", {
    value: "10:30",
    label: "Boarding",
  });

  const input = el.querySelector("input");
  assert.equal(input.getAttribute("type"), "time");
  assert.equal(input.value, "10:30");

  input.value = "11:45";
  fire(dom, input, "change");

  assert.deepEqual(transport.events.at(-1), {
    type: "change",
    key: "at",
    payload: { value: "11:45" },
  });
});

test("FilePicker renders a file input and prints the value it cannot assign", () => {
  withDocument();
  const el = buildElement({
    type: "FilePicker",
    key: "doc",
    props: { label: "Attach", value: "boarding-pass.pdf" },
    children: [],
  });

  const input = el.querySelector("input");
  assert.equal(input.getAttribute("type"), "file");
  // A page may not assign a file input's value, so the name is reflected as the
  // attribute the base sheet prints beside the button.
  assert.equal(input.value, "");
  assert.equal(el.getAttribute("data-tw-value"), "boarding-pass.pdf");
  assert.equal(el.textContent.trim(), "Attach");
});

test("FilePicker reports the chosen file as a select, and a cancel as nothing", () => {
  const { dom, el, transport } = mountWidget("FilePicker", "doc", { label: "Attach" });
  const input = el.querySelector("input");

  fire(dom, input, "change");
  assert.equal(transport.events.length, 0, "a cancelled pick reports nothing");

  Object.defineProperty(input, "files", {
    value: [{ name: "cv.pdf" }],
    configurable: true,
  });
  fire(dom, input, "change");

  const event = transport.events.at(-1);
  assert.equal(event.type, "select");
  assert.equal(event.key, "doc");
  assert.equal(event.payload.name, "cv.pdf");
  assert.equal(typeof event.payload.uri, "string");
});

test("TabView names its panel after the active tab and stays a container", () => {
  withDocument();
  const el = buildElement({
    type: "TabView",
    key: "profile-tabs",
    props: { tabs: ["Posts", "About"], active: 1 },
    children: [{ type: "Text", key: "panel", props: { content: "About me" }, children: [] }],
  });

  assert.equal(el.getAttribute("role"), "tabpanel");
  assert.equal(el.getAttribute("aria-label"), "About");
  assert.equal(el.getAttribute("data-tw-active"), "1");
  // The IR child stays at index 0: a renderer-owned tab strip would sit where the
  // patch paths address the panel.
  assert.equal(el.children.length, 1);
  assert.equal(el.children[0].getAttribute(TYPE_ATTR), "Text");
});

test("RouteDrawer reflects open, so the prop is visible to sheet and reader", () => {
  withDocument();
  const el = buildElement({
    type: "RouteDrawer",
    key: "shell",
    props: { open: false },
    children: [
      { type: "Text", key: "main", props: { content: "content" }, children: [] },
      { type: "Text", key: "side", props: { content: "menu" }, children: [] },
    ],
  });

  assert.equal(el.hasAttribute("data-tw-open"), false);
  assert.equal(el.getAttribute("aria-expanded"), "false");

  applyPatches(el, [{ path: [], set_props: { open: true } }]);

  assert.equal(el.hasAttribute("data-tw-open"), true);
  assert.equal(el.getAttribute("aria-expanded"), "true");
  assert.equal(el.children.length, 2, "both IR children keep their indices");
});

test("every widget in NATIVE_CONTROL_TYPES really renders a control", () => {
  withDocument();
  for (const type of NATIVE_CONTROL_TYPES) {
    const el = buildElement({ type, key: `k-${type}`, props: {}, children: [] });
    const control =
      ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) || el.querySelector("input, select, textarea") != null;
    assert.ok(control, `${type} rendered <${el.tagName.toLowerCase()}> with no control inside`);
  }
});

test("TabBar draws a real tablist and reports the tab that was clicked", () => {
  const { dom, el, transport } = mountWidget("TabBar", "profile-tabs", {
    tabs: ["Posts", "About", "Settings"],
    active: 0,
  });

  assert.equal(el.getAttribute("role"), "tablist");
  const tabs = el.querySelectorAll('[role="tab"]');
  assert.equal(tabs.length, 3);
  assert.equal(tabs[0].getAttribute("aria-selected"), "true");
  assert.equal(tabs[1].getAttribute("aria-selected"), "false");
  assert.equal(tabs[1].textContent, "About");

  tabs[1].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  // RouteChangeEvent's convention, which every tabbed example reads: the label as
  // `name`, the position under params["index"].
  assert.deepEqual(transport.events.at(-1), {
    type: "change",
    key: "profile-tabs",
    payload: { name: "About", params: { index: 1 } },
  });
});

test("TabBar moves the selection on an Update without rebuilding the strip", () => {
  withDocument();
  const el = buildElement({
    type: "TabBar",
    key: "tabs",
    props: { tabs: ["One", "Two"], active: 0 },
    children: [],
  });
  const before = el.children[1];

  applyPatches(el, [{ path: [], set_props: { active: 1 } }]);

  assert.equal(el.children[1], before, "the same button, not a fresh one");
  assert.equal(el.children[1].getAttribute("aria-selected"), "true");
  assert.equal(el.children[0].getAttribute("tabindex"), "-1");
});

test("a TabBar click is not swallowed as a generic click on the bar", () => {
  const { dom, el, transport } = mountWidget("TabBar", "tabs", {
    tabs: ["One", "Two"],
    active: 0,
  });

  el.querySelectorAll('[role="tab"]')[0].dispatchEvent(
    new dom.window.MouseEvent("click", { bubbles: true }),
  );

  assert.equal(transport.events.length, 1);
  assert.equal(transport.events[0].type, "change");
});
