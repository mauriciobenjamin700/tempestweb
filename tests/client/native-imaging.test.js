// native-imaging.test.js — the quality search, and the budget it cannot meet.
//
// jsdom has no canvas, so one is injected through `deps.createCanvas` /
// `deps.decodeImage`. The fake encoder models the one property that makes the
// search necessary: encoded size falls with quality, non-linearly. A fixed
// ladder ("try 0.8, then 0.6, then 0.4") either overshoots the budget or throws
// away quality that would have fit; the binary search does neither, and these
// tests are what says so.
//
// The case that matters most is `test an impossible budget answers instead of
// hanging`. A budget no quality can meet must terminate in a bounded number of
// encodes and report `within_budget: false` with the smallest it managed — a
// too-large image the app can decide about beats a spinner that never stops.

import assert from "node:assert/strict";
import test from "node:test";
import "./setup.js";

import {
  DEFAULT_COMPRESS_STEPS,
  imagingCompress,
  imagingInfo,
  imagingRead,
  imagingRelease,
  imagingThumbnails,
  imagingTransform,
} from "../../client/native/imaging.js";
import { clearBlobs, countBlobs, getBlob, putBlob } from "../../client/native/blobs.js";

const SOURCE_WIDTH = 4000;
const SOURCE_HEIGHT = 3000;

/** Encoded size in bytes: area-driven, and non-linear in quality. */
function modelSize(width, height, quality, floorBytes = 0) {
  const area = width * height;
  return Math.round(floorBytes + area * 0.5 * quality ** 2.2);
}

/**
 * A canvas whose encoder models real behaviour: smaller and lower quality means
 * fewer bytes, but never fewer than `floorBytes`.
 */
function fakeDeps({ floorBytes = 0, encodes = [], webp = true } = {}) {
  const createCanvas = (w, h) => ({
    width: w,
    height: h,
    getContext: () => ({
      drawImage() {},
      save() {},
      restore() {},
      translate() {},
      rotate() {},
      scale() {},
    }),
    toBlob(callback, type, quality) {
      if (type === "image/webp" && !webp) return callback(null);
      encodes.push({ type, quality, width: w, height: h });
      const size = modelSize(w, h, quality, floorBytes);
      callback(new Blob([new Uint8Array(size)], { type }));
    },
  });
  const decodeImage = async () => ({
    source: {},
    width: SOURCE_WIDTH,
    height: SOURCE_HEIGHT,
  });
  return { deps: { createCanvas, decodeImage }, encodes };
}

/** A source blob standing in for a captured photo. */
function source() {
  return putBlob(new Blob([new Uint8Array(4_000_000)], { type: "image/jpeg" }));
}

test("compress meets a reachable budget and says where it landed", async (t) => {
  t.after(() => clearBlobs());
  const { deps, encodes } = fakeDeps();

  const result = await imagingCompress(
    { source: source(), max_kb: 200, max_width: 1600 },
    deps,
  );

  assert.equal(result.within_budget, true);
  assert.ok(result.size_kb <= 200, `${result.size_kb} KB should fit 200 KB`);
  assert.ok(result.attempts >= 1 && result.attempts <= DEFAULT_COMPRESS_STEPS);
  assert.equal(encodes.length >= result.attempts, true);
  assert.ok(result.ref.startsWith("blob:tw:"));
  assert.ok(result.quality >= 0.4 && result.quality <= 0.92);
});

test("the width cap is honoured and the aspect ratio is kept", async (t) => {
  t.after(() => clearBlobs());
  const { deps } = fakeDeps();

  const result = await imagingCompress({ source: source(), max_width: 1600 }, deps);

  assert.equal(result.width, 1600);
  assert.equal(result.height, Math.round(1600 * (SOURCE_HEIGHT / SOURCE_WIDTH)));
});

test("a smaller image is never upscaled", async (t) => {
  t.after(() => clearBlobs());
  const { deps } = fakeDeps();

  const result = await imagingCompress({ source: source(), max_width: 99_999 }, deps);

  assert.equal(result.width, SOURCE_WIDTH);
});

test("an impossible budget answers instead of hanging", async (t) => {
  t.after(() => clearBlobs());
  // a floor of 400 KB against a 200 KB budget: no quality can reach it
  const { deps, encodes } = fakeDeps({ floorBytes: 400 * 1024 });

  const result = await imagingCompress(
    { source: source(), max_kb: 200, max_width: 800 },
    deps,
  );

  assert.equal(result.within_budget, false);
  assert.ok(result.size_kb >= 400, "it should report the smallest it managed");
  assert.ok(
    encodes.length <= DEFAULT_COMPRESS_STEPS,
    `spent ${encodes.length} encodes, cap is ${DEFAULT_COMPRESS_STEPS}`,
  );
});

test("the search is bounded by steps, and fewer steps means fewer encodes", async (t) => {
  t.after(() => clearBlobs());
  const { deps: wide, encodes: manyEncodes } = fakeDeps();
  const { deps: narrow, encodes: fewEncodes } = fakeDeps();

  await imagingCompress({ source: source(), max_kb: 200, steps: 6 }, wide);
  await imagingCompress({ source: source(), max_kb: 200, steps: 2 }, narrow);

  assert.ok(manyEncodes.length > fewEncodes.length);
  assert.ok(fewEncodes.length <= 3, `${fewEncodes.length} encodes for 2 steps`);
});

test("the search converges rather than walking a fixed ladder", async (t) => {
  t.after(() => clearBlobs());
  const { deps, encodes } = fakeDeps();

  await imagingCompress({ source: source(), max_kb: 200, max_width: 1600 }, deps);

  const qualities = encodes.filter((e) => e.type !== "image/webp" || true).map((e) => e.quality);
  const spans = [];
  for (let i = 1; i < qualities.length; i += 1) {
    spans.push(Math.abs(qualities[i] - qualities[i - 1]));
  }
  // a halving search takes shrinking steps; a fixed ladder takes equal ones
  assert.ok(spans.length >= 2, "expected at least three encodes to compare");
  assert.ok(spans[spans.length - 1] < spans[0], `steps did not shrink: ${spans}`);
});

test("auto picks webp when the browser encodes it, jpeg when it does not", async (t) => {
  t.after(() => clearBlobs());
  const withWebp = await imagingCompress(
    { source: source(), max_width: 400, type: "auto" },
    fakeDeps({ webp: true }).deps,
  );
  const withoutWebp = await imagingCompress(
    { source: source(), max_width: 400, type: "auto" },
    fakeDeps({ webp: false }).deps,
  );

  assert.equal(withWebp.mime_type, "image/webp");
  assert.equal(withoutWebp.mime_type, "image/jpeg");
});

test("an explicit type is not second-guessed", async (t) => {
  t.after(() => clearBlobs());
  const result = await imagingCompress(
    { source: source(), max_width: 400, type: "image/png" },
    fakeDeps().deps,
  );
  assert.equal(result.mime_type, "image/png");
});

test("thumbnails come back one per size, in the order asked", async (t) => {
  t.after(() => clearBlobs());
  const { deps } = fakeDeps();

  const { thumbnails } = await imagingThumbnails(
    { source: source(), sizes: [96, 256, 512] },
    deps,
  );

  assert.equal(thumbnails.length, 3);
  assert.deepEqual(thumbnails.map((t) => t.size), [96, 256, 512]);
  assert.equal(thumbnails[0].width, 96);
  assert.ok(thumbnails.every((t) => t.ref.startsWith("blob:tw:")));
});

test("asking for no thumbnails is valid, not an error", async (t) => {
  t.after(() => clearBlobs());
  const { thumbnails } = await imagingThumbnails({ source: source(), sizes: [] }, fakeDeps().deps);
  assert.deepEqual(thumbnails, []);
});

test("transform rotates, and 90 degrees swaps the output axes", async (t) => {
  t.after(() => clearBlobs());
  const { deps } = fakeDeps();

  const straight = await imagingTransform({ source: source(), width: 800 }, deps);
  const turned = await imagingTransform({ source: source(), width: 800, rotate: 90 }, deps);

  assert.equal(straight.width, 800);
  assert.equal(turned.height, 800);
  assert.equal(turned.width, straight.height);
});

test("info reads the shape without a second encode", async (t) => {
  t.after(() => clearBlobs());
  const { deps, encodes } = fakeDeps();

  const result = await imagingInfo({ source: source() }, deps);

  assert.equal(result.width, SOURCE_WIDTH);
  assert.equal(result.height, SOURCE_HEIGHT);
  assert.equal(result.mime_type, "image/jpeg");
  assert.equal(encodes.length, 0, "info must not encode anything");
});

test("an unknown handle is a named error, not a silent empty result", async () => {
  await assert.rejects(
    () => imagingCompress({ source: "blob:tw:999999" }, fakeDeps().deps),
    (err) => err.code === "not_found",
  );
});

test("base64 still works, for a photo captured before handles existed", async (t) => {
  t.after(() => clearBlobs());
  const { deps } = fakeDeps();

  const result = await imagingCompress(
    { source: { data_base64: "AQID", mime_type: "image/png" }, max_width: 100 },
    deps,
  );

  assert.ok(result.ref.startsWith("blob:tw:"));
});

test("read is the escape hatch and gives the bytes back", async (t) => {
  t.after(() => clearBlobs());
  const ref = putBlob(new Blob([new Uint8Array([1, 2, 3])], { type: "image/png" }));

  const result = await imagingRead({ source: ref }, {});

  assert.equal(result.data_base64, "AQID");
  assert.equal(result.mime_type, "image/png");
});

test("release drops one handle, and dropping it twice is not an error", async (t) => {
  t.after(() => clearBlobs());
  const ref = putBlob(new Blob([new Uint8Array([1])], { type: "image/png" }));

  assert.deepEqual(await imagingRelease({ source: ref }, {}), { released: 1 });
  assert.deepEqual(await imagingRelease({ source: ref }, {}), { released: 0 });
  assert.equal(getBlob(ref), null);
});

test("release all empties the registry", async (t) => {
  t.after(() => clearBlobs());
  putBlob(new Blob([new Uint8Array([1])]));
  putBlob(new Blob([new Uint8Array([2])]));

  const { released } = await imagingRelease({ all: true }, {});

  assert.equal(released, 2);
  assert.equal(countBlobs(), 0);
});

test("the registry is bounded, so a long capture session does not grow forever", async (t) => {
  t.after(() => clearBlobs());
  clearBlobs();
  for (let i = 0; i < 100; i += 1) putBlob(new Blob([new Uint8Array([i])]));

  assert.ok(countBlobs() <= 32, `registry holds ${countBlobs()}`);
});
