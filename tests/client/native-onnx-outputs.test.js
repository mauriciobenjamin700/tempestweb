// native-onnx-outputs.test.js — the output shape a sklearn export actually has.
//
// This test exists because a real measurement produced a real failure. A sklearn
// classifier exported with skl2onnx's DEFAULT settings emits `probabilities` as
// a seq(map(int64,float)) — the ZipMap node — and onnxruntime answers:
//
//   Can't access output tensor data on index 1.
//   ERROR_MESSAGE: Reading data from non-tensor typed value is not supported.
//
// That message does not say what to do. The handler now translates it into one
// that names the fix, and this pins that translation.

import assert from "node:assert/strict";
import test from "node:test";
import "./setup.js";

import { onnxLoad, onnxRun } from "../../client/native/onnx.js";

/** An ort double that answers whatever outputs a test asks for. */
function fakeOrt(outputs, outputNames) {
  return {
    Tensor: class {
      constructor(type, data, dims) {
        this.type = type;
        this.data = data;
        this.dims = dims;
      }
    },
    InferenceSession: {
      create: async () => ({
        inputNames: ["X"],
        outputNames,
        run: async () => outputs,
      }),
    },
  };
}

const FEEDS = {
  X: { data_base64: "AAAAAA==", dims: [1, 1], dtype: "float32" },
};

test("a tensor output is read", async () => {
  const ort = fakeOrt(
    { label: { type: "int64", data: new BigInt64Array([1n]), dims: [1] } },
    ["label"],
  );
  const model = await onnxLoad({ model_url: "m.onnx" }, { ort, caches: null });
  const { outputs } = await onnxRun(
    { session_id: model.session_id, feeds: FEEDS },
    { ort },
  );

  assert.equal(outputs.label.dtype, "int64");
  assert.equal(outputs.label.dims[0], 1);
});

test("a ZipMap output names the fix instead of the symptom", async () => {
  const ort = fakeOrt(
    {
      label: { type: "int64", data: new BigInt64Array([1n]), dims: [1] },
      // what skl2onnx's default emits: a sequence of maps, no `data`, no `type`
      probabilities: [new Map([[0, 0.2], [1, 0.8]])],
    },
    ["label", "probabilities"],
  );
  const model = await onnxLoad({ model_url: "m.onnx" }, { ort, caches: null });

  await assert.rejects(
    () => onnxRun({ session_id: model.session_id, feeds: FEEDS }, { ort }),
    (err) => {
      assert.equal(err.code, "unsupported_output");
      assert.match(err.message, /probabilities/);
      assert.match(err.message, /zipmap/i);
      return true;
    },
  );
});

test("loading falls back to the URL when there is no cache storage", async () => {
  const ort = fakeOrt({ label: { type: "int64", data: new BigInt64Array([0n]), dims: [1] } }, [
    "label",
  ]);
  const model = await onnxLoad({ model_url: "m.onnx" }, { ort, caches: null });

  assert.ok(model.session_id);
  assert.deepEqual(model.input_names, ["X"]);
});
