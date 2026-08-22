// PinInput and FormField: a code field that exists, and a field that says when
// to validate it.
//
// `PinInput` declares `length` / `value` / `secure` / `on_complete` and rendered
// as an empty div — nothing to type into, so neither handler was reachable.
// `FormField` declares `name`, `error` and `on_validate`: the name never reached
// the DOM (so the client had nothing to report), and the error was a prop nobody
// drew.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { applyPatches, buildElement } from "../../client/dom.js";
import { bindEvents } from "../../client/events.js";
import { BASE_THEME_CSS } from "../../client/theme.js";

/** A mock Transport that records every sendEvent call. */
function mockTransport() {
  /** @type {import("../../client/transport.js").TWEvent[]} */
  const events = [];
  return { events, onPatches() {}, sendEvent: (e) => events.push(e), async close() {} };
}

/** Mount a PinInput of `length` under the dom root. */
function pin(dom, { length = 4, value = "", secure = false } = {}) {
  const el = buildElement({
    type: "PinInput",
    key: "code",
    props: { length, value, secure },
    children: [],
  });
  dom.root.appendChild(el);
  return el;
}

/** Type `value` into a control and dispatch the DOM input event. */
function type(dom, el, value) {
  el.value = value;
  el.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
}

test("a PinInput is a real one-time-code field", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = pin(dom, { length: 6, secure: true });

  assert.equal(el.tagName, "INPUT");
  assert.equal(el.getAttribute("type"), "password");
  assert.equal(el.getAttribute("maxlength"), "6");
  assert.equal(el.getAttribute("inputmode"), "numeric");
  assert.equal(el.getAttribute("autocomplete"), "one-time-code");
  assert.equal(el.getAttribute("data-tw-length"), "6");
});

test("typing the last digit reports complete, alongside the change", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = pin(dom, { length: 4 });
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  type(dom, el, "12");
  assert.deepEqual(
    transport.events.map((e) => e.type),
    ["input"],
    "a partial code is just a change",
  );

  type(dom, el, "1234");
  assert.deepEqual(transport.events.map((e) => e.type), ["input", "input", "complete"]);
  assert.deepEqual(transport.events[2], {
    type: "complete",
    key: "code",
    payload: { values: { value: "1234" } },
  });
});

test("a full field does not report complete again on every keystroke", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = pin(dom, { length: 4 });
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  type(dom, el, "1234");
  type(dom, el, "1234");
  type(dom, el, "12345");
  const completes = transport.events.filter((e) => e.type === "complete");
  assert.equal(completes.length, 1, "only the transition to full counts");
});

test("clearing the field re-arms the next completion", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = pin(dom, { length: 4 });
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  type(dom, el, "1234");
  type(dom, el, "");
  type(dom, el, "9999");
  assert.equal(transport.events.filter((e) => e.type === "complete").length, 2);
});

test("a masked code stays masked while it is typed", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = pin(dom, { length: 4, secure: true });

  // Typing patches `value` alone; re-deriving the type from that bag would
  // unmask the code on the first keystroke (the Input had exactly this bug).
  applyPatches(el, [{ path: [], set_props: { value: "1" }, unset_props: [] }]);
  assert.equal(el.getAttribute("type"), "password");
});

test("a FormField carries its name, and leaving it asks for validation", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const field = buildElement({
    type: "FormField",
    key: "f-email",
    props: { name: "email", label: "E-mail" },
    children: [{ type: "Input", key: "email-in", props: { value: "nope" }, children: [] }],
  });
  dom.root.appendChild(field);
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  assert.equal(field.getAttribute("data-tw-field"), "email");

  const control = field.querySelector("[data-tw-key=\"email-in\"]");
  control.value = "not-an-email";
  control.dispatchEvent(new dom.window.Event("focusout", { bubbles: true }));

  assert.deepEqual(transport.events, [
    {
      type: "validate",
      key: "f-email",
      payload: { field: "email", value: "not-an-email" },
    },
  ]);
});

test("leaving a control outside any field reports nothing", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const loose = buildElement({ type: "Input", key: "loose", props: { value: "x" }, children: [] });
  dom.root.appendChild(loose);
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  loose.dispatchEvent(new dom.window.Event("focusout", { bubbles: true }));
  assert.deepEqual(transport.events, []);
});

test("an unnamed field cannot be validated, so nothing is reported", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const field = buildElement({
    type: "FormField",
    key: "f",
    props: { name: "" },
    children: [{ type: "Input", key: "in", props: { value: "x" }, children: [] }],
  });
  dom.root.appendChild(field);
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  field.querySelector("input").dispatchEvent(new dom.window.Event("focusout", { bubbles: true }));
  assert.deepEqual(transport.events, []);
});

test("a field's error is drawn and announced, and clears again", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const field = buildElement({
    type: "FormField",
    key: "f",
    props: { name: "email", error: "E-mail inválido" },
    children: [{ type: "Input", key: "in", props: { value: "x" }, children: [] }],
  });

  assert.equal(field.getAttribute("data-tw-error"), "E-mail inválido");
  assert.equal(field.getAttribute("aria-invalid"), "true");

  applyPatches(field, [{ path: [], set_props: { error: null }, unset_props: [] }]);
  assert.equal(field.getAttribute("data-tw-error"), null);
  assert.equal(field.getAttribute("aria-invalid"), null, "a fixed field is not invalid");
});

test("the base sheet paints the code box and the field error", () => {
  assert.match(BASE_THEME_CSS, /\[data-tw-type="PinInput"\][\s\S]*letter-spacing/);
  assert.match(BASE_THEME_CSS, /\[data-tw-field\]\[aria-invalid="true"\]::after[\s\S]*attr\(data-tw-error\)/);
});
