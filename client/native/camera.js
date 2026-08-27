// native/camera.js — MediaDevices/getUserMedia glue for the N4 camera capability.
//
// Captures a single frame: open a stream, draw the first video frame to a canvas,
// encode it, and return base64 bytes (JSON-safe for the Mode B round-trip). The
// stream tracks are always stopped before returning.

import { CapabilityError } from "./index.js";
import { fromBase64, putBlob } from "./blobs.js";

/**
 * Strip the `data:<mime>;base64,` prefix from a canvas data URL.
 * @param {string} dataUrl
 * @returns {string}
 */
function stripDataUrl(dataUrl) {
  const comma = dataUrl.indexOf(",");
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

/**
 * Capture a single photo from the device camera.
 *
 * Playing the video element is best-effort: a rejected play() is swallowed since
 * some environments resolve frames without an explicit play().
 *
 * @param {{facing:string,quality:number,mime_type:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{mime_type:string,width:number,height:number,data_base64:string}>}
 * @throws {CapabilityError} permission_denied / unavailable / insecure_context.
 */
export async function cameraCapture(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  if (!nav || !nav.mediaDevices || typeof nav.mediaDevices.getUserMedia !== "function") {
    throw new CapabilityError("unavailable", "camera is not available");
  }

  let stream;
  try {
    stream = await nav.mediaDevices.getUserMedia({
      video: { facingMode: args.facing || "environment" },
    });
  } catch (err) {
    const code = err && err.name === "NotAllowedError" ? "permission_denied" : "unavailable";
    throw new CapabilityError(code, err && err.message);
  }

  try {
    const video = doc.createElement("video");
    video.srcObject = stream;
    if (typeof video.play === "function") {
      try {
        await video.play();
      } catch {
      }
    }
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    const canvas = doc.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (ctx) ctx.drawImage(video, 0, 0, width, height);
    const mime = args.mime_type || "image/jpeg";
    const dataUrl = canvas.toDataURL(mime, typeof args.quality === "number" ? args.quality : 0.85);
    const base64 = stripDataUrl(dataUrl);
    // The blob is registered either way: `imaging.*` addresses the photo by
    // handle, so the pixels never cross the bridge again. `include_bytes: false`
    // additionally keeps them from crossing the FIRST time, which is what an app
    // that only compresses and uploads wants.
    const blob = fromBase64(base64, mime);
    return {
      mime_type: mime,
      width,
      height,
      ref: blob ? putBlob(blob) : "",
      data_base64: args.include_bytes === false ? "" : base64,
    };
  } finally {
    for (const track of stream.getTracks ? stream.getTracks() : []) {
      if (typeof track.stop === "function") track.stop();
    }
  }
}
