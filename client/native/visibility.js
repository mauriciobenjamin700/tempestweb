// native/visibility.js — Page Visibility API glue.
//
// Reports whether the page is currently visible, hidden, or prerendering. Always
// readable (no permission, no gesture); degrades to a safe default if the document
// exposes no visibility state.

/**
 * Report the current page visibility state.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{state:string, hidden:boolean}>}
 */
export async function visibilityState(_args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  return {
    state: (doc && doc.visibilityState) || "visible",
    hidden: !!(doc && doc.hidden),
  };
}
