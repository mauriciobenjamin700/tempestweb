# The Mode A boot payload

In Mode A your Python runs **inside the browser**, on Pyodide. Before the first
paint, the browser downloads `tempestweb-pkg.zip`, unpacks it into Pyodide's
virtual filesystem and runs `import app`. This page shows the two decisions
`tempestweb build --mode wasm` makes about that zip — and how you tune each one
in `tempestweb.toml`.

!!! info "One-line summary"
    By default the zip carries **bytecode precompiled** for Pyodide's exact
    Python and **only the `tempestweb` subpackages your app reaches**. Both fail
    safe: without the right Python on the build host, source ships (with a
    warning); if the import walk cannot see something, you force it with `keep`.

## The problem: compiling everything, on every visit

Pyodide turns on `sys.dont_write_bytecode`. In practice, **every module is
compiled from source on every page load** — the `__pycache__` CPython normally
writes never exists there, and nothing survives a reload.

Measured on the `tempest-webtunnel` dashboard (Pyodide v314.0.0, in Node, same
zip): with the old zip, **159 modules of the app, `tempestweb` and
`tempest_core` went through the compiler** on every boot. With bytecode in the
zip, **zero**.

## 1. Bytecode in the zip — `[wasm] bytecode`

```toml
[wasm]
bytecode = "alongside"   # default
```

| Value | What goes in the zip | When to use |
|---|---|---|
| `"alongside"` (default) | `.py` **and** a `__pycache__/<module>.cpython-314.pyc` beside it | Almost always. Tracebacks keep the source line, and the boot skips compilation. |
| `"sourceless"` | Only the `.pyc`, in place of the `.py` | When download size matters more than tracebacks with source. |
| `"off"` | Only `.py`, as before | To turn the feature (and the warning below) off. |

`app.py` is special: the bootstrap fetches it separately and writes it next to
the zip, so its bytecode travels as `__pycache__/app.cpython-314.pyc` inside the
zip — and Pyodide's importlib finds it there.

### Why it is safe

A `.pyc` is valid for **one** CPython. One from another version is rejected —
or, worse, misread. So the build does not trust "looks like 3.14":

1. The target is pinned in `tempestweb.core.constants`: `WASM_PYODIDE_PYTHON =
   "3.14"` and `WASM_PYODIDE_PYC_MAGIC` (the *magic number* read from the
   Pyodide v314.0.0 runtime itself).
2. The build looks for an interpreter with **exactly that magic**: the one
   running the build, then `uv python find 3.14`, then `python3.14` on `PATH`.
   A 3.14 *alpha* has a different magic and is refused.
3. It compiles in **checked-hash** mode (PEP 552): Pyodide checks the source
   hash before using the `.pyc`. If a new `app.py` arrives with an old zip
   (caching), the module is recompiled instead of running old code.
4. It checks the header of **every** `.pyc` written. Any mismatch discards all
   of the bytecode.

Without a matching interpreter, the build **does not fail**: it emits a
`WasmBytecodeWarning` and packs source only — the app boots the same, just
slower.

!!! tip "Installing Pyodide's Python on the build host"
    If your environment runs another Python (3.11, 3.12, 3.13), make a 3.14
    available for the build to find:

    ```bash
    uv python install 3.14
    tempestweb build --mode wasm
    ```

    `uv python find` only **looks** — the build never downloads a Python on its
    own.

!!! note "`tempestweb dev` does not compile"
    The development loop rebuilds on every save and would rather be fast: it
    packs source only. Bytecode is for `build`, `run` and `deploy`.

## 2. Only what the app reaches — `[wasm] trim`

The zip used to carry **every** browser-side `tempestweb` subpackage
(`tabular`, `vision`, `query`, `export`, `access`, ...), imported or not. Now
the build walks the imports statically and leaves out what nothing reaches.

```toml
[wasm]
trim = true          # default
keep = ["tabular"]   # escape hatch: subpackages that ship with no visible import
```

The walk starts in three places — `app.py`, your `[wasm] modules` and
`tempestweb.runtime` (which the bootstrap imports) — and follows each reached
subpackage. On purpose, it counts **more** than Python executes:

- `import` and `from ... import` **anywhere** in the file — inside functions
  and under `TYPE_CHECKING` too;
- relative imports (`from ..tabular import x`);
- `tempestweb.html` as an attribute;
- dotted strings, as in `importlib.import_module("tempestweb.transports.sse")`.

Docstrings do not count: mentioning `tempestweb.tabular` in documentation is not
importing it.

!!! warning "What the walk cannot see"
    A module name **built at runtime** — `import_module(f"tempestweb.{name}")` —
    appears nowhere in the source. If your app does that, tell the build:
    `keep = ["tabular"]`, or switch it off entirely with `trim = false`. A wrong
    name in `keep` fails the build with the list of valid ones instead of being
    ignored.

`tempest_core` always ships whole: its `__init__` imports nearly everything up
front, so dropping files there would break the boot.

## How much it changes — measured

The `tempest-webtunnel` dashboard (`app.py` + the `api/` client generated by
`gen api`), `tempestweb build --mode wasm`:

| Zip | Size | Entries | `.py` | `.pyc` |
|---|---:|---:|---:|---:|
| Before (everything, source only) | 487 KB | 198 | 197 | 0 |
| `bytecode = "off"`, `trim = true` | 416 KB | 168 | 167 | 0 |
| **Default** (`alongside` + trim) | 1.16 MB | 336 | 167 | 168 |
| `sourceless` + trim | 739 KB | 169 | 0 | 168 |

The trim removed `access`, `components`, `export`, `query`, `tabular` and
`vision` from this app. Bytecode costs download — `.pyc` compresses worse than
source — and in exchange the boot stops compiling.

And the `import app` time (the Python side of the boot, after the zip is
downloaded), on the same Pyodide v314.0.0 running in Node on a desktop, **10
interleaved rounds per variant** on a loaded machine — median (minimum):

| Zip | `import app` |
|---|---:|
| Before | 1454 ms (1267) |
| `off` + trim | 1436 ms (1168) |
| **Default** (`alongside` + trim) | 1247 ms (1068) |
| `sourceless` + trim | 1176 ms (1016) |

That is **~15–20% of the Python side**. The rest is not compilation: profiled,
about two thirds of `import app` is `pydantic` building the ~260 models of
`tempest_core` and the app — work no bytecode avoids.

??? info "What about Pyodide's memory snapshot?"
    Pyodide has a **private** memory-snapshot API
    (`loadPyodide({ _makeSnapshot: true })` → `makeMemorySnapshot()` →
    `loadPyodide({ _loadSnapshot })`) that would skip the interpreter boot and
    the imports in one go. We tried it on v314.0.0 and **it cannot be used
    here**:

    - any `loadPackage` — including `pydantic`, which the core requires — leaves
      JS-side state and `makeMemorySnapshot()` refuses
      (`Unexpected hiwire entry at index 6`);
    - installing the wheels by hand to work around that, the snapshot is made
      (36 MB) but the restore fails (`RangeError: offset is out of bounds`): the
      native `pydantic_core` extension is a dynamic library loaded outside the
      memory the snapshot captures;
    - only an interpreter **without** native extensions restores (≈30 MB, in
      ~80 ms) — and `pydantic` is exactly what makes the boot expensive.

    Without `pydantic` in the snapshot there is no gain that pays for a 30 MB
    download, so the feature was left out.

## Recap

- Pyodide **does not keep** bytecode: with no `.pyc` in the zip, every module
  compiles on every visit.
- `[wasm] bytecode` = `"alongside"` (default) · `"sourceless"` · `"off"`. The
  `.pyc` only comes from an interpreter with the pinned Pyodide's **exact
  magic**; without one, source + `WasmBytecodeWarning`.
- `[wasm] trim = true` (default) leaves out the subpackages the import walk does
  not reach; `keep = [...]` forces, `trim = false` switches it off.
- `tempestweb dev` packs source only, so the loop stays fast.
