// native/share.js — Web Share API glue for the N2 share capability.
//
// `navigator.share` requires a user gesture and a secure context. When the API
// is missing, share() returns `{ outcome: "unsupported" }` rather than throwing,
// so callers fall back gracefully (e.g. to the clipboard). A user dismissal
// resolves `{ outcome: "cancelled" }`.

/**
 * Report whether the Web Share API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function shareIsSupported(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  return { supported: Boolean(nav && typeof nav.share === "function") };
}

/**
 * Open the OS share sheet, degrading gracefully when unsupported.
 * @param {{title:string,text:string,url:string,files:Array<Object>}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{outcome:"shared"|"cancelled"|"unsupported"}>}
 */
export async function shareShare(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || typeof nav.share !== "function") {
    return { outcome: "unsupported" };
  }
  /** @type {ShareData} */
  const data = {};
  if (args.title) data.title = args.title;
  if (args.text) data.text = args.text;
  if (args.url) data.url = args.url;
  // File sharing has uneven support; only forward when the browser accepts it.
  if (Array.isArray(args.files) && args.files.length > 0 && nav.canShare) {
    const files = args.files;
    if (nav.canShare({ files })) data.files = /** @type {any} */ (files);
  }
  try {
    await nav.share(data);
    return { outcome: "shared" };
  } catch (err) {
    // AbortError means the user dismissed the sheet — a normal outcome.
    if (err && err.name === "AbortError") return { outcome: "cancelled" };
    return { outcome: "cancelled" };
  }
}
