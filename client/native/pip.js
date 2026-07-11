// native/pip.js — Picture-in-Picture glue for the Tier-3 seam.
//
// `video.requestPictureInPicture()` pops a <video> into a floating window;
// `document.exitPictureInPicture()` restores it. The target video is located via
// a CSS selector (defaulting to the first <video>).

import { CapabilityError } from "./index.js";

/**
 * Enter Picture-in-Picture for the video matching `selector`.
 * @param {{selector?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{active:boolean}>}
 * @throws {CapabilityError} unavailable / not_found / failed.
 */
export async function pipRequest(args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  if (!doc || typeof doc.querySelector !== "function") {
    throw new CapabilityError("unavailable", "the document is not available");
  }
  const video = doc.querySelector(args.selector || "video");
  if (!video) {
    throw new CapabilityError("not_found", "no video element matched the selector");
  }
  if (typeof video.requestPictureInPicture !== "function") {
    throw new CapabilityError("unavailable", "the Picture-in-Picture API is not available");
  }
  try {
    await video.requestPictureInPicture();
    return { active: true };
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
}

/**
 * Exit Picture-in-Picture.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{active:boolean}>}
 * @throws {CapabilityError} unavailable / failed.
 */
export async function pipExit(_args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  if (!doc || typeof doc.exitPictureInPicture !== "function") {
    throw new CapabilityError("unavailable", "the Picture-in-Picture API is not available");
  }
  try {
    await doc.exitPictureInPicture();
    return { active: false };
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
}
