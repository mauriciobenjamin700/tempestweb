# REVIEW-T8 — adversarial QA of track T8 (`feat/examples`) — re-QA after fix round 1

**Reviewer:** tw-qa (skeptical QA, runs the gate, distrusts prose)
**Branch:** `feat/examples` — worktree `/home/mauriciobenjamin700/projects/my/tempestweb-T8`
**HEAD:** `8149c30 fix: address QA round-1 gaps on T8`
**Done-when (MANIFEST):** *Each example imports, `build(view())` validates and yields a
tree; input/list/form widgets are exercised.*

## VERDICT: PASS

The single deduction from round 0 (PASS-WITH-GAPS — three user-facing handler closures
never invoked by a test) is **closed**. The fix round added tests that drive the real
`todo.add_item`, the real per-row `toggle` closure, and the real `form.submit` closure,
asserting their state mutations. The gate is green from a clean run, every done-when
clause maps to a non-vacuous passing assertion, no `_core`/out-of-track edits, no
skipped/xfail/assert-nothing tests, no `NotImplementedError`.

## Gate output (run from clean state)

```text
$ ruff check .            -> All checks passed!                     (exit 0)
$ ruff format --check .   -> 19 files already formatted             (exit 0)
$ mypy tempestweb         -> Success: no issues found in 9 files    (exit 0)
$ pytest -q               -> 19 passed, 1 warning                   (exit 0)
$ pytest tests/unit/test_examples.py -> 15 passed                   (exit 0)
$ node --test tests/client/*.test.js -> pass 1, fail 0              (exit 0)
```

Track verification command (`pytest tests/unit/test_examples.py`) is green: 15 tests
(4 examples parametrized for import+build, plus per-widget/per-handler exercises).

### Note: `node --test tests/client/` (directory arg) fails — out of T8 scope

`node --test tests/client/` (directory form) errors with `Cannot find module
.../tests/client` under node v24.15.0 — a node invocation quirk, not a T8 defect. T8 does
not own `client/` or `tests/client/**` (that is T1); the failure reproduces identically
on `main`. The glob form `node --test tests/client/*.test.js` passes. Flagged for the
T1/CI owner.

## Done-when checklist (each clause → passing test)

| Clause | Proof | Status |
|---|---|---|
| Each example **imports** | `test_example_imports_and_builds[counter/todo/form/fetch]` loads `app.py` via importlib, asserts `view`/`make_state` present | PASS |
| `build(view())` **validates + yields a tree** | same test: `node = build(view(app))`, asserts `isinstance(node, Node)`, non-empty `type`, non-empty `children` | PASS |
| **input** exercised | `test_todo_exercises_input_and_list` asserts `Input` in tree; `test_todo_add_item_transition` drives the **real** `edit_draft` (on_change) + `add_item` (on_click) closures incl. `.strip()` + append + draft-clear; `test_todo_add_item_strips_and_guards_blank` proves the blank-guard and whitespace-strip | PASS |
| **list** exercised | todo `LazyColumn`+`Checkbox` window asserted == seed count; `test_todo_toggle_handler_flips_done` calls the **real** `item_builder(i)` factory and per-row `on_change` closure, proving the `i=index` capture and `done = not done` flip; fetch `LazyColumn` materializes 3 rows after async load | PASS |
| **form** exercised | `test_form_exercises_form_widgets` asserts `Form`/`FormField`/`Input` (2 fields, 1 Input each); `test_form_validation_surfaces_errors` runs the real validators; `test_form_submit_handler_mirrors_errors_onto_state` + `test_form_submit_handler_marks_submitted_when_valid` drive the **real** `submit` closure (errors mirrored onto state + fields; valid path clears errors + marks submitted + status Text → "Welcome!") | PASS |

## Round-0 gap → resolution

- **P2 (handlers not invoked) — RESOLVED.** `add_item`, the per-row `toggle`, and
  `form.submit` are now each driven through the actual view closures (located by `key`
  via `_find_handler` / `item_builder`), not reimplemented inline. A regression inside
  any of these closures would now fail the suite. Verified by reading the test bodies
  (lines 134–213, 275–315) and confirming the assertions read back `app.state`.

## Adversarial findings (this round)

- **No asserts-nothing / skip / xfail / NotImplementedError** in the suite.
- **All widgets are genuine core widgets** (verified import of `Input`, `LazyColumn`,
  `Checkbox`, `Form`, `FormField`, `FormState`, `Validator`, `Spinner` from
  `tempestweb._core.widgets` and the events from `tempestweb._core.widgets.events`).
- **Scope clean:** `git diff main...HEAD` = `examples/{todo,form,fetch}/app.py`,
  `tests/unit/test_examples.py`, `REVIEW-T8.md`, `SUMMARY-T8.md`. No `_core` edits, no
  `examples/counter` edits, nothing outside track.
- **Conventions:** examples `D`-exempt but `ANN`/`Q`-enforced (gate passes); mypy strict
  on `tempestweb`. Double quotes in all code (single-quote grep hits are prose inside
  comments). Google docstrings + full type hints present.

## Minor (non-blocking)

1. `DeprecationWarning: There is no current event loop` from
   `tempestweb/_core/core/state.py:665` during `test_todo_add_item_transition`. Origin is
   the **vendored core** (do-not-edit), not T8. Resolves when `tempest-core` replaces the
   vendored copy. No action for T8.
2. Async fetch tests inject a deterministic `Fetcher` rather than a live `native.http`
   round-trip — correct for a unit test, documented in the example docstring; the
   real-transport path is T4's concern.

## Bottom line

T8 meets its done-when with real, passing, non-vacuous tests; the previously flagged
handler-coverage gap is closed; the gate is green; work stays strictly inside track
boundaries. **PASS.**
