// patch-diagnostics.test.js — what the client says when a patch will not apply.
//
// A path failure used to be reported as a bare `at index N`: it named neither
// the node the client had nor how far short it fell, so diagnosing one meant
// hand-patching dom.js inside a built artifact (tempestweb#160). These pin the
// two things that replaced it — a message carrying the tree's actual shape, and
// an opt-in patch-stream log that can be switched on from the console of a page
// that is already misbehaving.
import { test } from "node:test";
import assert from "node:assert/strict";

import { fixture, freshDom } from "./setup.js";
import { mount } from "../../client/tempestweb.js";

/**
 * A mock Transport that pushes patch batches and counts resync requests.
 */
function mockTransport() {
  /** @type {?(patches: any[]) => void} */
  let handler = null;
  let resyncs = 0;
  return {
    push(patches) {
      if (handler) handler(patches);
    },
    onPatches(fn) {
      handler = fn;
    },
    sendEvent() {},
    requestResync() {
      resyncs += 1;
    },
    resyncs: () => resyncs,
    async close() {},
  };
}

/**
 * Run `fn` with console.error/console.log captured, restoring them afterwards.
 *
 * @param {() => void} fn  The body to run.
 * @returns {{errors: string[], logs: string[]}}  Everything each channel received.
 */
function captureConsole(fn) {
  const errors = [];
  const logs = [];
  const realError = console.error;
  const realLog = console.log;
  console.error = (...args) => errors.push(args.map(String).join(" "));
  console.log = (...args) => logs.push(args.map(String).join(" "));
  try {
    fn();
  } finally {
    console.error = realError;
    console.log = realLog;
  }
  return { errors, logs };
}

test("a failed path names the node, the whole path, and the shortfall", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, fixture("node_initial.json"));

  const { errors } = captureConsole(() => {
    transport.push([{ path: [1, 99], set_props: { content: "nope" } }]);
  });

  const message = errors.join("\n");
  assert.match(message, /path \[1, 99\]/, "the full path is in the message");
  assert.match(message, /step 1/, "the failing step is named");
  assert.match(message, /has \d+ children/, "the shortfall is measurable");
  assert.match(message, /data-tw-key/, "the parent is identified by widget key");
});

test("the patch stream is silent unless debugging is switched on", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, fixture("node_initial.json"));
  delete globalThis.__tempestweb_debug;

  const { logs } = captureConsole(() => {
    transport.push([{ path: [0], set_props: { content: "quiet" } }]);
  });

  assert.deepEqual(logs, []);
});

test("with debugging on, every batch is logged and a failure dumps the tree", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, fixture("node_initial.json"));
  globalThis.__tempestweb_debug = true;

  const { errors, logs } = captureConsole(() => {
    transport.push([{ path: [0], set_props: { content: "loud" } }]);
    transport.push([{ path: [99], set_props: { content: "nope" } }]);
  });
  delete globalThis.__tempestweb_debug;

  assert.equal(logs.length, 2, "one line per batch, failing or not");
  assert.match(logs[0], /patch batch #1/);
  assert.match(logs[1], /patch batch #2/);
  assert.match(errors.join("\n"), /client tree at failure/);
});

test("a transport that cannot resync says so instead of failing quietly", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  delete transport.requestResync;
  mount(dom.root, transport, fixture("node_initial.json"));

  const { errors } = captureConsole(() => {
    transport.push([{ path: [99], set_props: { content: "nope" } }]);
  });

  assert.match(errors.join("\n"), /cannot request a resync/);
});
