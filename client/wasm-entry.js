/**
 * The Mode A (wasm) client surface, as one module.
 *
 * This is the entry the release-time bundler (`scripts/bundle-client.mjs`)
 * starts from. Its output, `client/bundle/tempestweb-wasm.js`, is what a
 * `tempestweb build --mode wasm` artifact loads: the 80-odd modules under
 * `client/` collapse into one request instead of a waterfall of static imports
 * that held Pyodide back until the whole tree had resolved.
 *
 * The bootstrap and the shell's inline script import exactly these names, and
 * nothing else from the client, so a name the shell needs has to be re-exported
 * here or the artifact fails to load.
 *
 * @module wasm-entry
 */

export { mount } from "./tempestweb.js";
export { createWasmTransport } from "./transport-wasm.js";
export { installNativeBridge } from "./native/index.js";
export { applyThemeMode } from "./theme.js";
export { mountConnectivityBanner } from "./pwa/connectivity-banner.js";
