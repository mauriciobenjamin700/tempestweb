// Tests for the onnx (onnxruntime-web bridge) and file (share/download) native
// capabilities. The `ort` runtime and the browser File/share/anchor surface are
// injected/faked, so these run under node:test with no real browser or WASM.

import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

import { dispatch } from "../../client/native/index.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

/** Base64 of a Float32Array, matching what the Python Tensor would send. */
function f32Base64(values) {
  const arr = new Float32Array(values);
  const bytes = new Uint8Array(arr.buffer);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return Buffer.from(binary, "binary").toString("base64");
}

/** A fake onnxruntime-web that echoes its single input as the output. */
function fakeOrt() {
  class Tensor {
    constructor(type, data, dims) {
      this.type = type;
      this.data = data;
      this.dims = dims;
    }
  }
  const session = {
    inputNames: ["images"],
    outputNames: ["output0"],
    async run(feeds) {
      const input = feeds.images;
      return { output0: new Tensor(input.type, input.data, input.dims) };
    },
  };
  return {
    Tensor,
    InferenceSession: {
      created: [],
      async create(url, opts) {
        this.created.push({ url, opts });
        return session;
      },
    },
  };
}

test("onnx.load: compiles a session and returns its io names", async () => {
  const ort = fakeOrt();
  const res = await dispatch(
    call("onnx.load", { model_url: "./models/detect.onnx", providers: ["wasm"] }),
    { ort },
  );
  assert.equal(res.ok, true);
  assert.match(res.value.session_id, /^onnx-\d+$/);
  assert.deepEqual(res.value.input_names, ["images"]);
  assert.deepEqual(res.value.output_names, ["output0"]);
  assert.deepEqual(ort.InferenceSession.created[0].opts.executionProviders, ["wasm"]);
});

test("onnx.load: unavailable when ort is not loaded", async () => {
  const res = await dispatch(call("onnx.load", { model_url: "x.onnx" }), {});
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("onnx.run: round-trips a float32 tensor through the session", async () => {
  const ort = fakeOrt();
  const loaded = await dispatch(call("onnx.load", { model_url: "m.onnx" }), { ort });
  const sessionId = loaded.value.session_id;

  const res = await dispatch(
    call("onnx.run", {
      session_id: sessionId,
      feeds: { images: { data_base64: f32Base64([1.5, -2.0, 3.25]), dims: [3], dtype: "float32" } },
    }),
    { ort },
  );
  assert.equal(res.ok, true);
  const out = res.value.outputs.output0;
  assert.equal(out.dtype, "float32");
  assert.deepEqual(out.dims, [3]);
  // Decode the echoed bytes and confirm the values survived the round-trip.
  const bytes = Buffer.from(out.data_base64, "base64");
  const decoded = new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4);
  assert.deepEqual(Array.from(decoded), [1.5, -2.0, 3.25]);
});

test("onnx.run: unknown session id is a not_found error", async () => {
  const ort = fakeOrt();
  const res = await dispatch(call("onnx.run", { session_id: "nope", feeds: {} }), { ort });
  assert.equal(res.ok, false);
  assert.equal(res.error, "not_found");
});

test("file.save: falls back to an anchor download when share is unavailable", async () => {
  const dom = new JSDOM("<!doctype html><html><body></body></html>");
  const doc = dom.window.document;
  // Provide URL + Blob + File on the global the handler reads.
  globalThis.Blob = dom.window.Blob;
  globalThis.File = dom.window.File;
  globalThis.URL.createObjectURL = () => "blob:fake";
  globalThis.URL.revokeObjectURL = () => {};

  let clicked = false;
  const realCreate = doc.createElement.bind(doc);
  doc.createElement = (tag) => {
    const el = realCreate(tag);
    if (tag === "a") el.click = () => {
      clicked = true;
    };
    return el;
  };

  const res = await dispatch(
    call("file.save", {
      filename: "famacha.zip",
      data_base64: Buffer.from("hello").toString("base64"),
      mime: "application/zip",
    }),
    { navigator: {}, document: doc },
  );
  assert.equal(res.ok, true);
  assert.equal(res.value.method, "download");
  assert.equal(res.value.shared, false);
  assert.equal(clicked, true);
});

test("file.pick: reads the chosen file back as base64", async () => {
  const dom = new JSDOM("<!doctype html><html><body></body></html>");
  const doc = dom.window.document;
  // Fake FileReader that yields a data URL synchronously on readAsDataURL.
  globalThis.FileReader = class {
    readAsDataURL(_file) {
      this.result = "data:image/png;base64,aGVsbG8=";
      if (this.onload) this.onload();
    }
  };
  const realCreate = doc.createElement.bind(doc);
  doc.createElement = (tag) => {
    const el = realCreate(tag);
    if (tag === "input") {
      Object.defineProperty(el, "files", {
        value: [{ name: "ovino.png", type: "image/png" }],
        configurable: true,
      });
      el.click = () => {
        if (el.onchange) el.onchange();
      };
    }
    return el;
  };
  const res = await dispatch(call("file.pick", { accept: "image/*" }), { document: doc });
  assert.equal(res.ok, true);
  assert.equal(res.value.data_base64, "aGVsbG8=");
  assert.equal(res.value.mime, "image/png");
  assert.equal(res.value.name, "ovino.png");
});

test("file.save: uses the Web Share API when it accepts files", async () => {
  const dom = new JSDOM("<!doctype html><html><body></body></html>");
  globalThis.Blob = dom.window.Blob;
  globalThis.File = dom.window.File;

  const shared = [];
  const navigator = {
    canShare: () => true,
    share: async (payload) => {
      shared.push(payload);
    },
  };
  const res = await dispatch(
    call("file.save", {
      filename: "famacha.zip",
      data_base64: Buffer.from("hi").toString("base64"),
      mime: "application/zip",
    }),
    { navigator, document: dom.window.document },
  );
  assert.equal(res.ok, true);
  assert.equal(res.value.method, "share");
  assert.equal(res.value.shared, true);
  assert.equal(shared.length, 1);
});
