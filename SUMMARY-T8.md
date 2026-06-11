# SUMMARY — Track T8 (`feat/examples`)

Additional example apps under `examples/`, each a `view(app) -> Widget` module
mirroring `examples/counter/app.py`, exercising the core widget API (inputs,
lists, forms, async handlers), plus `tests/unit/test_examples.py` covering them.

## What was built

- **`examples/todo/app.py`** — Todo list. Exercises the value-bearing widgets:
  a single-line `Input` for the draft (`TextChangeEvent` handler), a virtualized
  `LazyColumn` (`item_count` + `item_builder`, only the visible window
  materializes into the IR), and a per-row `Checkbox` to toggle completion. Seeds
  two items so the first mount renders a non-empty list. Mode-agnostic view.
- **`examples/form/app.py`** — Sign-up form. Exercises the form layer: a `Form`
  aggregating two `FormField` wrappers (each wrapping an `Input`, password field
  `secure=True`) with typed `Validator` rules that run purely in Python.
  `Form.validate(...)` gates the submit and mirrors per-field errors back onto
  the fields via `set_state`.
- **`examples/fetch/app.py`** — Async fetch view. Exercises an `async` handler
  driving the UI through an idle -> loading -> loaded/error lifecycle (`StrEnum`
  phase). Renders a `Spinner` while in flight and a `LazyColumn` of result rows
  on success. The `fetch` coroutine is injected into state (`Fetcher` type) so
  the example is deterministic under test; a real app would pass
  `native.http.request`. Never blocks the event loop.
- **`examples/counter/app.py`** — pre-existing canonical example (not owned by
  this track; left untouched).

- **`tests/unit/test_examples.py`** — 11 tests:
  - Parametrized `build(view(app))` validity for all four examples (yields a
    `Node` tree with a non-empty type tag and children).
  - Todo: asserts `Input` / `LazyColumn` / `Checkbox` present; the materialized
    window matches the seeded item count; an add-item transition grows the list
    and produces a non-empty `diff`.
  - Form: asserts `Form` / `FormField` / `Input` present (two fields, each
    wrapping one `Input`); empty submit surfaces email + password errors, a valid
    payload passes with no errors.
  - Fetch (async): idle has no `Spinner`; driving the async `load` handler
    transitions to a 3-row `LazyColumn`; the loading phase renders a `Spinner`;
    a failing fetch surfaces the error message in the `error`-keyed node.

## Widgets exercised (scope: inputs, lists, forms)

`Input`, `Checkbox`, `LazyColumn`, `Form`, `FormField`, `Validator`/`FormState`,
`Spinner`, plus the shared `Column`/`Row`/`Text`/`Button`. Async handler path is
exercised end-to-end via `App.set_state` + `await`.

## What is stubbed / simplified

- The fetch example's network call is an injected coroutine returning a fixed
  list (`_default_fetch`), not a real HTTP request — by design, so the test is
  deterministic and transport-free. The docstring notes the real wiring point
  (`native.http.request`).
- Tests build/diff directly with `apply_patches = lambda _: None`; they do not
  go through a real transport (that is T1/T2/T3 territory).

## Verification

All green on `feat/examples`:

```
ruff check .            # All checks passed!
ruff format --check .   # 19 files already formatted
mypy tempestweb         # Success: no issues found
pytest tests/unit/test_examples.py -q   # 11 passed
```

Each example also typechecks individually under `mypy --strict examples/<name>/app.py`
(the gate runs `mypy tempestweb`; the examples are standalone scripts with sibling
`app.py` modules, so they are checked one at a time — checking them together trips
mypy's duplicate-module guard, which is expected for a flat examples/ layout).

## Needs manual verification

- Nothing for this track's automated scope. The examples are pure `view()`
  functions validated by `build`/`diff`; no browser/device is required to prove
  the tree is correct.
- A live end-to-end run (`tempestweb dev --mode wasm|server` rendering these
  views in a real browser) depends on the transport/devserver tracks landing
  first and is out of T8 scope.

## Suggested merge order

Per `docs/agents/MANIFEST.md`: T1 -> T2/T3 -> T4 -> T9 -> **T5/T7/T8/T10** -> T6.
T8 touches only `examples/**` (except counter) and `tests/unit/test_examples.py`,
so it has no source conflicts with other tracks and can merge in that batch.
