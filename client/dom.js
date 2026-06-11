// dom.js — apply a batch of patches to a live DOM tree.  PHASE W1.
//
// Implement applyPatches(root, patches) so that, given the DOM built from
// node_initial.json, applying patches_all_kinds.json yields the expected DOM.
// Distinguish patch kinds by key presence (see transport.js typedefs).
// Build DOM nodes from the Node IR via buildElement(node) using style.js for css.
//
// Verify against ../tests/fixtures/ in tests/client/ (jsdom). Do NOT use a framework.

/**
 * Build a DOM element from an IR node.
 * @param {import("./transport.js").Node} node
 * @returns {HTMLElement}
 */
export function buildElement(node) {
  throw new Error("W1: buildElement not implemented");
}

/**
 * Apply a coalesced batch of patches to the DOM tree rooted at `root`.
 * @param {HTMLElement} root
 * @param {import("./transport.js").Patch[]} patches
 * @returns {void}
 */
export function applyPatches(root, patches) {
  throw new Error("W1: applyPatches not implemented");
}
