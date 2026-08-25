// mode-a-resync.test.js — Mode A repairs a broken tree instead of staying truncated.
//
// Drives the real mount() against the real createWasmTransport (with a fake
// pyodide.ffi bridge standing in for Pyodide), so the whole Mode A repair path is
// exercised end to end: a patch the renderer cannot apply raises, the mount asks
// the transport for a resync, the transport pushes the `resync` wire event the
// Python runtime serves, and the root Replace that comes back rebuilds the tree.
//
// Before this, Mode A had no `requestResync` at all: onPatchFailure degenerated
// into a console.error and returned, so every later index-relative patch landed
// on a tree that no longer existed and the screen stayed truncated for the rest
// of the page's life (tempestweb#159).
import { test } from "node:test";
import assert from "node:assert/strict";

import { fixture, freshDom } from "./setup.js";
import { mount } from "../../client/tempestweb.js";
import { createWasmTransport } from "../../client/transport-wasm.js";

/** Build a fake pyodide.ffi bridge that records pushed events and exposes deliver. */
function fakeBridge() {
  /** @type {(patches: any[]) => void} */
  let deliver = () => {};
  const pushed = [];
  return {
    bridge: {
      onDeliver(cb) {
        deliver = cb;
      },
      pushEvent(ev) {
        pushed.push(ev);
      },
      close() {},
    },
    deliver: (patches) => deliver(patches),
    pushed,
  };
}

test("a patch that cannot apply makes Mode A ask Python for a resync", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  mount(dom.root, transport, fixture("node_initial.json"));

  fb.deliver([{ path: [99], set_props: { content: "nope" } }]);

  assert.deepEqual(fb.pushed, [{ type: "resync", key: "", payload: {} }]);
});

test("the resync repaints the whole tree, so the screen is not left truncated", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  const initial = fixture("node_initial.json");
  mount(dom.root, transport, initial);

  const before = dom.root.querySelectorAll("[data-tw-key]").length;
  assert.ok(before > 0, "the fixture mounts keyed nodes");

  fb.deliver([
    { path: [0], set_props: { content: "applied" } },
    { path: [99], set_props: { content: "nope" } },
  ]);
  assert.equal(fb.pushed.length, 1, "the failure asked for a resync");

  fb.deliver([{ path: [], node: initial }]);

  assert.equal(
    dom.root.querySelectorAll("[data-tw-key]").length,
    before,
    "the repaired tree holds every node the initial mount did",
  );
});

test("the repaired tree accepts the patches that follow", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  const initial = fixture("node_initial.json");
  mount(dom.root, transport, initial);

  fb.deliver([{ path: [99], set_props: { content: "nope" } }]);
  fb.deliver([{ path: [], node: initial }]);
  fb.deliver([{ path: [0], set_props: { content: "Count: 7" } }]);

  assert.equal(fb.pushed.length, 1, "no second resync piled up after the repair");
  assert.equal(dom.root.firstChild.children[0].textContent, "Count: 7");
});

test("the resync replaces the overlay layer instead of stacking onto it", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  const initial = fixture("node_initial.json");
  mount(dom.root, transport, initial);

  const dialog = { type: "Dialog", key: "dlg", props: {}, children: [] };
  fb.deliver([{ path: ["overlay"], index: 0, node: dialog }]);
  const host = dom.root.querySelector("[data-tw-overlays]");
  assert.equal(host.children.length, 1, "the dialog is open before the failure");

  fb.deliver([{ path: [99], set_props: { content: "nope" } }]);
  fb.deliver([
    { path: [], node: initial },
    { path: ["overlay"], index: 0, node: dialog },
  ]);

  assert.equal(
    host.children.length,
    1,
    "a resync carries every open overlay as an insert, and an insert adds — " +
      "without clearing the layer first the dialog comes back stacked on itself",
  );
});

test("a plain root Replace leaves the overlay layer alone", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  const initial = fixture("node_initial.json");
  mount(dom.root, transport, initial);

  const dialog = { type: "Dialog", key: "dlg", props: {}, children: [] };
  fb.deliver([{ path: ["overlay"], index: 0, node: dialog }]);
  const host = dom.root.querySelector("[data-tw-overlays]");

  fb.deliver([{ path: [], node: initial }]);

  assert.equal(
    host.children.length,
    1,
    "the diff re-sends a root Replace whenever the root's type changes, and it " +
      "does not re-send overlays it did not touch — clearing here would delete " +
      "a dialog nothing would put back",
  );
});

test("a resync with no overlays empties a layer that had some", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const fb = fakeBridge();
  const transport = createWasmTransport(fb.bridge);
  const initial = fixture("node_initial.json");
  mount(dom.root, transport, initial);

  fb.deliver([
    { path: ["overlay"], index: 0, node: { type: "Dialog", key: "dlg", props: {}, children: [] } },
  ]);
  const host = dom.root.querySelector("[data-tw-overlays]");
  assert.equal(host.children.length, 1);

  fb.deliver([{ path: [99], set_props: { content: "nope" } }]);
  fb.deliver([{ path: [], node: initial }]);

  assert.equal(
    host.children.length,
    0,
    "the scene closed the dialog while the tree was broken; the repaired screen " +
      "must not still show it",
  );
});
