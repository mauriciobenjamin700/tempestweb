// native/imaging.js — compress, thumbnail and transform an image before upload.
//   PHASE R6.
//
// Between `camera.capture()` and `http.upload()` there was nothing: an app
// captured a 4 MB photo and uploaded 4 MB, or rewrote canvas compression by hand
// in a framework whose whole proposal is not writing JS.
//
// The part nobody gets right on the first try is `compressToTarget`: a BINARY
// SEARCH of encoder quality against a byte budget. Encoding is not linear in
// quality, so "try 0.8, then 0.6, then 0.4" either overshoots the budget or
// throws away quality that fit. The search converges in a bounded number of
// encodes and reports what it settled on — which quality, how many encodes it
// spent, and whether it met the budget at all.
//
// An impossible budget (200 KB of a photo that will not go below 400 KB at the
// floor quality) must NOT spin forever. The search is bounded by
// DEFAULT_COMPRESS_STEPS and answers `within_budget: false` with the smallest it
// managed, because a too-large image the app can decide about beats a hang.
//
// Everything here works on blob handles (native/blobs.js): the pixels never
// cross the bridge. Canvas is injectable via `deps.createCanvas` so the whole
// module is testable under jsdom, which has no canvas of its own.

import { CapabilityError } from "./index.js";
import {
  clearBlobs,
  describeBlob,
  dropBlob,
  putBlob,
  resolveSource,
  toBase64,
} from "./blobs.js";

/** How many encodes the quality search is allowed to spend. */
export const DEFAULT_COMPRESS_STEPS = 6;

/** The lowest quality the search will accept. Below this, artefacts show. */
export const DEFAULT_MIN_QUALITY = 0.4;

/** The highest quality the search starts from. */
export const DEFAULT_MAX_QUALITY = 0.92;

/** The type an `"auto"` request encodes to when the browser supports it. */
export const PREFERRED_TYPE = "image/webp";

/** The type every browser encodes. */
export const FALLBACK_TYPE = "image/jpeg";

/**
 * Resolve the canvas factory: injected for tests, `document` in a page.
 *
 * @param {import("./index.js").NativeDeps} deps
 * @returns {(w: number, h: number) => *} A factory returning a canvas-like object.
 * @throws {CapabilityError} unavailable — when there is no way to make a canvas.
 */
function canvasFactory(deps) {
  const injected = deps && /** @type {any} */ (deps).createCanvas;
  if (typeof injected === "function") return injected;
  const doc = (deps && deps.document) || /** @type {any} */ (globalThis).document;
  if (doc && typeof doc.createElement === "function") {
    return (w, h) => {
      const canvas = doc.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      return canvas;
    };
  }
  const g = /** @type {any} */ (globalThis);
  if (typeof g.OffscreenCanvas === "function") {
    return (w, h) => new g.OffscreenCanvas(w, h);
  }
  throw new CapabilityError("unavailable", "no canvas is available to decode images");
}

/**
 * Decode a blob into something drawable, with its intrinsic size.
 *
 * @param {Blob} blob  The image bytes.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{source: *, width: number, height: number}>}
 * @throws {CapabilityError} decode_failed — when the bytes are not an image.
 */
async function decode(blob, deps) {
  const injected = deps && /** @type {any} */ (deps).decodeImage;
  if (typeof injected === "function") return injected(blob);
  const g = /** @type {any} */ (globalThis);
  if (typeof g.createImageBitmap === "function") {
    try {
      const bitmap = await g.createImageBitmap(blob);
      return { source: bitmap, width: bitmap.width, height: bitmap.height };
    } catch (err) {
      throw new CapabilityError("decode_failed", err && err.message);
    }
  }
  throw new CapabilityError("decode_failed", "no image decoder is available");
}

/**
 * Encode a canvas at one quality, as a blob.
 *
 * @param {*} canvas   The canvas to read.
 * @param {string} type     The MIME type to encode to.
 * @param {number} quality  The encoder quality, 0 to 1.
 * @returns {Promise<Blob>} The encoded bytes.
 * @throws {CapabilityError} encode_failed — when the browser refuses the type.
 */
async function encode(canvas, type, quality) {
  if (typeof canvas.convertToBlob === "function") {
    return canvas.convertToBlob({ type, quality });
  }
  if (typeof canvas.toBlob === "function") {
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, type, quality));
    if (blob) return blob;
    throw new CapabilityError("encode_failed", `cannot encode to ${type}`);
  }
  throw new CapabilityError("encode_failed", "the canvas cannot be encoded");
}

/**
 * Pick the output type, honouring `"auto"`.
 *
 * `"auto"` is one field rather than the SDK's two capabilities
 * (`bestSupportedType` / `supportsImageType`): the caller wants a small file, not
 * a survey of what the browser encodes.
 *
 * @param {string} requested  `"auto"`, or an explicit MIME type.
 * @param {*} canvas          A canvas to probe with.
 * @returns {Promise<string>} The type to encode to.
 */
async function chooseType(requested, canvas) {
  if (requested && requested !== "auto") return requested;
  try {
    const probe = await encode(canvas, PREFERRED_TYPE, 0.5);
    if (probe && probe.type === PREFERRED_TYPE) return PREFERRED_TYPE;
  } catch {
    // fall through — a browser that cannot encode webp is not an error
  }
  return FALLBACK_TYPE;
}

/**
 * Draw a decoded image onto a canvas at a target size.
 *
 * @param {{source: *, width: number, height: number}} image  The decoded image.
 * @param {number} width   Target width.
 * @param {number} height  Target height.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {*} The canvas holding the drawn image.
 * @throws {CapabilityError} decode_failed — when the canvas has no 2D context.
 */
function draw(image, width, height, deps) {
  const canvas = canvasFactory(deps)(Math.max(1, Math.round(width)), Math.max(1, Math.round(height)));
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new CapabilityError("decode_failed", "no 2D context on the canvas");
  ctx.drawImage(image.source, 0, 0, canvas.width, canvas.height);
  return canvas;
}

/**
 * Scale a size down to fit a maximum edge, keeping the aspect ratio.
 *
 * @param {number} width      Current width.
 * @param {number} height     Current height.
 * @param {?number} maxWidth  The cap, or null for none.
 * @param {?number} maxHeight The cap, or null for none.
 * @returns {{width: number, height: number}} The fitted size, never upscaled.
 */
function fit(width, height, maxWidth, maxHeight) {
  let scale = 1;
  if (maxWidth && width > maxWidth) scale = Math.min(scale, maxWidth / width);
  if (maxHeight && height > maxHeight) scale = Math.min(scale, maxHeight / height);
  return { width: width * scale, height: height * scale };
}

/**
 * Shrink an image to fit a byte budget, by binary search on encoder quality.
 *
 * The search is the whole point. Encoded size is not linear in quality, so a
 * fixed ladder either misses the budget or gives away quality that would have
 * fit. Each step halves the remaining quality range: too big, search lower; fits,
 * keep it and search higher for something better.
 *
 * @param {{source: *, max_kb?: number, max_width?: number, max_height?: number,
 *          type?: string, min_quality?: number, max_quality?: number,
 *          steps?: number}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{ref: string, width: number, height: number, size_kb: number,
 *          quality: number, attempts: number, within_budget: boolean, mime_type: string}>}
 * @throws {CapabilityError} not_found — the handle is unknown or was evicted.
 */
export async function imagingCompress(args, deps) {
  const blob = resolveSource(args.source);
  if (!blob) throw new CapabilityError("not_found", "the image source could not be resolved");

  const image = await decode(blob, deps);
  const target = fit(image.width, image.height, args.max_width, args.max_height);
  const canvas = draw(image, target.width, target.height, deps);
  const type = await chooseType(args.type, canvas);

  const budget = typeof args.max_kb === "number" ? args.max_kb * 1024 : Infinity;
  const steps = args.steps ?? DEFAULT_COMPRESS_STEPS;
  let low = args.min_quality ?? DEFAULT_MIN_QUALITY;
  let high = args.max_quality ?? DEFAULT_MAX_QUALITY;

  let attempts = 0;
  /** @type {?{blob: Blob, quality: number}} */
  let best = null;
  /** @type {?{blob: Blob, quality: number}} */
  let smallest = null;

  for (let step = 0; step < steps && low <= high; step += 1) {
    const quality = (low + high) / 2;
    const encoded = await encode(canvas, type, quality);
    attempts += 1;
    if (!smallest || encoded.size < smallest.blob.size) {
      smallest = { blob: encoded, quality };
    }
    if (encoded.size <= budget) {
      best = { blob: encoded, quality };
      low = quality + 0.01;
    } else {
      high = quality - 0.01;
    }
  }

  const chosen = best ?? smallest;
  if (!chosen) throw new CapabilityError("encode_failed", "no encode attempt succeeded");

  return {
    ref: putBlob(chosen.blob),
    width: Math.round(canvas.width),
    height: Math.round(canvas.height),
    size_kb: Math.round((chosen.blob.size / 1024) * 10) / 10,
    quality: Math.round(chosen.quality * 100) / 100,
    attempts,
    within_budget: chosen.blob.size <= budget,
    mime_type: type,
  };
}

/**
 * Render one image at several sizes, for previews.
 *
 * @param {{source: *, sizes?: number[], type?: string, quality?: number}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{thumbnails: Object[]}>} One entry per requested size, in the
 *          order asked. An empty `sizes` answers an empty list — asking for no
 *          thumbnails is a valid thing to do, not an error.
 * @throws {CapabilityError} not_found — the handle is unknown or was evicted.
 */
export async function imagingThumbnails(args, deps) {
  const blob = resolveSource(args.source);
  if (!blob) throw new CapabilityError("not_found", "the image source could not be resolved");
  const sizes = Array.isArray(args.sizes) ? args.sizes : [];
  if (sizes.length === 0) return { thumbnails: [] };

  const image = await decode(blob, deps);
  const quality = typeof args.quality === "number" ? args.quality : DEFAULT_MAX_QUALITY;
  const thumbnails = [];

  for (const size of sizes) {
    const target = fit(image.width, image.height, size, size);
    const canvas = draw(image, target.width, target.height, deps);
    const type = await chooseType(args.type, canvas);
    const encoded = await encode(canvas, type, quality);
    thumbnails.push({
      ref: putBlob(encoded),
      size,
      width: Math.round(canvas.width),
      height: Math.round(canvas.height),
      size_kb: Math.round((encoded.size / 1024) * 10) / 10,
      mime_type: type,
    });
  }
  return { thumbnails };
}

/**
 * Resize, rotate, crop and flip in a single pass.
 *
 * One capability rather than four, because four means four decodes and four
 * encodes of the same image to do what one canvas does in one.
 *
 * @param {{source: *, width?: number, height?: number, rotate?: number,
 *          flip_horizontal?: boolean, flip_vertical?: boolean,
 *          crop?: {x: number, y: number, width: number, height: number},
 *          type?: string, quality?: number}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>} The processed image's handle and shape.
 * @throws {CapabilityError} not_found — the handle is unknown or was evicted.
 */
export async function imagingTransform(args, deps) {
  const blob = resolveSource(args.source);
  if (!blob) throw new CapabilityError("not_found", "the image source could not be resolved");
  const image = await decode(blob, deps);

  const crop = args.crop;
  const cropped = crop
    ? {
        source: image.source,
        width: Math.min(crop.width, image.width - crop.x),
        height: Math.min(crop.height, image.height - crop.y),
        x: crop.x,
        y: crop.y,
      }
    : { source: image.source, width: image.width, height: image.height, x: 0, y: 0 };

  const target = fit(cropped.width, cropped.height, args.width, args.height);
  const rotate = ((args.rotate || 0) % 360 + 360) % 360;
  const swapped = rotate === 90 || rotate === 270;
  const canvasWidth = swapped ? target.height : target.width;
  const canvasHeight = swapped ? target.width : target.height;

  const canvas = canvasFactory(deps)(
    Math.max(1, Math.round(canvasWidth)),
    Math.max(1, Math.round(canvasHeight)),
  );
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new CapabilityError("decode_failed", "no 2D context on the canvas");

  ctx.save();
  ctx.translate(canvas.width / 2, canvas.height / 2);
  if (rotate) ctx.rotate((rotate * Math.PI) / 180);
  ctx.scale(args.flip_horizontal ? -1 : 1, args.flip_vertical ? -1 : 1);
  ctx.drawImage(
    cropped.source,
    cropped.x,
    cropped.y,
    cropped.width,
    cropped.height,
    -target.width / 2,
    -target.height / 2,
    target.width,
    target.height,
  );
  ctx.restore();

  const type = await chooseType(args.type, canvas);
  const quality = typeof args.quality === "number" ? args.quality : DEFAULT_MAX_QUALITY;
  const encoded = await encode(canvas, type, quality);

  return {
    ref: putBlob(encoded),
    width: Math.round(canvas.width),
    height: Math.round(canvas.height),
    size_kb: Math.round((encoded.size / 1024) * 10) / 10,
    mime_type: type,
  };
}

/**
 * Report an image's type, size and dimensions.
 *
 * Cheap by design: the byte count and MIME come from the blob itself, and only
 * the dimensions need a decode. An app deciding whether an image is worth
 * compressing at all asks this first.
 *
 * @param {{source: *}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{mime_type: string, width: number, height: number, size_kb: number}>}
 * @throws {CapabilityError} not_found — the handle is unknown or was evicted.
 */
export async function imagingInfo(args, deps) {
  const blob = resolveSource(args.source);
  if (!blob) throw new CapabilityError("not_found", "the image source could not be resolved");
  const described = typeof args.source === "string" ? describeBlob(args.source) : null;
  const image = await decode(blob, deps);
  return {
    mime_type: (described && described.mime) || blob.type || "application/octet-stream",
    width: image.width,
    height: image.height,
    size_kb: Math.round((blob.size / 1024) * 10) / 10,
  };
}

/**
 * Read an image's bytes back into Python.
 *
 * The escape hatch, not the path. Calling this moves the whole image across the
 * bridge, which is what handles exist to avoid — an app that only needs to upload
 * should hand the handle to `http.upload` instead.
 *
 * @param {{source: *}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{data_base64: string, mime_type: string, size_kb: number}>}
 * @throws {CapabilityError} not_found — the handle is unknown or was evicted.
 */
export async function imagingRead(args, deps) {
  const blob = resolveSource(args.source);
  if (!blob) throw new CapabilityError("not_found", "the image source could not be resolved");
  return {
    data_base64: await toBase64(blob),
    mime_type: blob.type || "application/octet-stream",
    size_kb: Math.round((blob.size / 1024) * 10) / 10,
  };
}

/**
 * Release a handle, or every handle.
 *
 * @param {{source?: *, all?: boolean}} args
 * @param {import("./index.js").NativeDeps} _deps
 * @returns {Promise<{released: number}>} How many handles were released.
 */
export async function imagingRelease(args, _deps) {
  if (args && args.all) return { released: clearBlobs() };
  if (args && typeof args.source === "string") {
    return { released: dropBlob(args.source) ? 1 : 0 };
  }
  return { released: 0 };
}
