// events.js — capture DOM events and route them through a transport.  PHASE W3.
//
// Implement bindEvents(root, transport) so that a click on a Button element
// (carrying its widget key) calls transport.sendEvent({type:"click", key, payload}).
// Use event delegation on `root`. Map DOM events (click/input/change/submit) to the
// TWEvent shape in transport.js. Read the widget key from a data attribute set by
// dom.js (agree on `data-tw-key`).
//
// Verify in tests/client/ with a mock transport (jsdom dispatchEvent).

/**
 * Bind delegated DOM event listeners on `root` that forward to the transport.
 * @param {HTMLElement} root
 * @param {import("./transport.js").Transport} transport
 * @returns {() => void}  An unbind function.
 */
export function bindEvents(root, transport) {
  throw new Error("W3: bindEvents not implemented");
}
