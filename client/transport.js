// transport.js — the shared client/Python seam contract.
//
// A transport delivers patches (Python -> client) and events (client -> Python).
// The DOM renderer and Style->CSS translator are identical across both modes;
// only the transport implementation differs:
//   - transport-wasm.js : in-process bridge via pyodide.ffi   (Mode A)
//   - transport-ws.js   : WebSocket                           (Mode B)
//
// See ../docs/contract.md for the wire format and ../tests/fixtures/ for goldens.

/**
 * @typedef {Object} Patch
 * A JSON patch emitted by the reconciler. One of five shapes — distinguish by keys:
 *  - Update : { path:number[], set_props:Object, unset_props:string[] }
 *  - Insert : { path:number[], index:number, node:Node }
 *  - Remove : { path:number[], index:number }
 *  - Reorder: { path:number[], order:number[] }
 *  - Replace: { path:number[], node:Node }
 */

/**
 * @typedef {Object} Node
 * @property {string} type            Widget type ("Column", "Text", "Button", ...).
 * @property {?string} key            Stable reconciliation key.
 * @property {Object} props           Widget props, including `style` (Style|null).
 * @property {Node[]} children        Child nodes.
 */

/**
 * @typedef {Object} TWEvent
 * @property {string} type            "click" | "input" | "change" | "submit" | ...
 * @property {?string} key            Key of the originating widget.
 * @property {Object} payload         Event data, e.g. { value: "text" } for input.
 */

/**
 * @typedef {Object} Transport
 * @property {(handler: (patches: Patch[]) => void) => void} onPatches
 *           Register the callback that receives each tick's patch batch.
 * @property {(event: TWEvent) => void} sendEvent
 *           Send a user event back to the Python side.
 * @property {() => Promise<void>} close
 *           Tear down the transport.
 */

export {};
