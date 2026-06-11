# NOTES — Track T3 (Mode A / WASM, Pyodide)

Branch: `feat/mode-wasm`. Scope: A0 (de-risk Pyodide+pydantic), A1 (WASM
transport), A3 (static bootstrap). Pure-Python logic is pytest-covered; the live
in-browser Pyodide path is documented here for manual verification.

---

## A0 — Current state of pydantic-core in Pyodide (researched 2026-06-10)

The critical de-risk for Mode A is whether `pydantic-core` (Rust → WASM) loads in
Pyodide, because the vendored core (`tempestweb/_core`) is built on Pydantic v2 and
every IR/patch model is a `pydantic.BaseModel`.

### Findings

- **Pyodide moved to a CalVer-ish scheme.** The latest stable release is
  **`314.0.0`** (published **2026-06-09**), succeeding `0.29.4` (2026-05-07). The
  jump is a versioning change, not 314 major versions. CDN paths use the tag
  verbatim: `https://cdn.jsdelivr.net/pyodide/v314.0.0/full/`.
- **Pyodide 314.0.0 bundles CPython 3.14.2** (`Makefile.envs`: `PYVERSION ?=
  3.14.2`). The vendored core uses `from __future__ import annotations` and modern
  `X | None` typing, so it imports cleanly on 3.14.
- **Package recipes moved out of the main repo** into
  [`pyodide/pyodide-recipes`](https://github.com/pyodide/pyodide-recipes). The
  `pyodide/pyodide` `packages/` dir now only holds core/test packages; the broad
  index (numpy, pydantic, …) lives in `pyodide-recipes`.
- **`pydantic` and `pydantic_core` are both built recipes** in
  `pyodide-recipes` as **emscripten wheels** (Pyodide's CI compiles the Rust
  `pydantic_core` to WASM):
  - `pydantic` → **2.12.5**
  - `pydantic_core` → **2.41.5** (source tarball compiled to an emscripten wheel by
    Pyodide; sha pinned in the recipe).
- The historical pain (pydantic/pydantic-core#1506: "Can't find a pure Python 3
  wheel for pydantic-core") is about **installing from PyPI via `micropip`** — PyPI
  ships no emscripten wheel. The fix is to **not** install from PyPI: use Pyodide's
  own package index, which carries the prebuilt emscripten wheel. The
  `pydantic-core` repo itself was archived 2026-04-11; the WASM build now lives in
  Pyodide-land, not upstream.

### Decision for the bootstrap

Load pydantic via Pyodide's package machinery, **not** plain PyPI micropip:

```js
const pyodide = await loadPyodide({
  indexURL: "https://cdn.jsdelivr.net/pyodide/v314.0.0/full/",
});
// Pulls the prebuilt emscripten pydantic_core wheel + pydantic from Pyodide's
// index (NOT from PyPI), so the Rust→WASM concern is already solved upstream.
await pyodide.loadPackage(["pydantic"]); // pydantic_core comes along as a dep
```

`micropip.install("pydantic")` also works in recent Pyodide because micropip falls
back to the Pyodide package index for packages with no pure-Python PyPI wheel — but
`loadPackage` is the explicit, dependency-free path and is what the bootstrap uses.

### Version skew note (local vs Pyodide)

| | Local dev (`.venv`, CPython 3.x) | Pyodide 314.0.0 (browser, CPython 3.14.2) |
|---|---|---|
| pydantic | 2.13.4 | 2.12.5 |
| pydantic_core | 2.46.4 | 2.41.5 |

Both are Pydantic **v2** with the API surface the vendored core uses
(`BaseModel`, `model_dump(mode="json")`, `model_copy`, `ConfigDict`,
`WithJsonSchema`, `Field`). No v1/v2 split risk. If a future core feature needs a
pydantic ≥ 2.13 API, the Pyodide recipe must be bumped first — flag it at integration.

### Residual risks (carry to A2/integration)

- **Cold start / bundle size.** Pyodide + pydantic_core WASM is several MB; first
  load is heavy. Mitigation belongs to Trilho P (service-worker precache) — out of
  T3 scope, noted for the merge.
- **CPU-bound work blocks the tab.** The reconciler is light, but a heavy `view()`
  freezes the UI thread; keep handlers async (A2).
- **Emscripten wheel ↔ Pyodide version coupling.** The pydantic_core WASM wheel is
  built against a specific Pyodide ABI; **pin the Pyodide version in the bootstrap**
  (done — `v314.0.0`) and bump the recipe version together.

Sources:

- <https://pyodide.org/en/stable/usage/packages-in-pyodide.html>
- <https://github.com/pyodide/pyodide/releases> (tag `314.0.0`, 2026-06-09)
- <https://github.com/pyodide/pyodide-recipes> (`packages/pydantic`,
  `packages/pydantic_core` meta.yaml)
- <https://github.com/pydantic/pydantic-core/issues/1506>
- <https://blog.pyodide.org/posts/314-release/>

---

## Manual verification (live Pyodide — requires a real browser)

The pure-Python glue (runtime + transport) is unit-tested headless. The live
in-browser path (A0/A1 "feito quando") needs a browser with WASM and cannot run in
CI here. Steps to verify by hand:

1. From the repo root, serve the project over HTTP (Pyodide needs same-origin
   fetch; `file://` will not work):

   ```bash
   python -m http.server 8000
   ```

2. Open <http://127.0.0.1:8000/public/index.html> in a modern browser.

3. Expected on load:
   - The splash shows "Loading Pyodide…", then "Loading pydantic…", then the
     counter mounts.
   - The DOM shows `Count: 0` with `-` and `+` buttons.
   - The browser console logs the initial patch batch produced **in the browser**
     by the vendored reconciler (proves A0: core + pydantic_core ran in WASM).

4. Click `+` / `-`:
   - `Count:` updates with **zero network** (proves A1: in-process `pyodide.ffi`
     transport round-trips an event → Python handler → patch → DOM).

5. Confirm in the Network tab that after the Pyodide/pydantic assets load, clicking
   the buttons issues **no further requests**.

> Until T1's real `client/dom.js`/`client/tempestweb.js` land, `public/index.html`
> uses them by ES-module import; if T1 is not yet merged, the bootstrap still loads
> Pyodide and logs the patch batch to the console (step 3's last bullet), which is
> enough to confirm A0. Full visual counter (step 4) needs T1 merged.
