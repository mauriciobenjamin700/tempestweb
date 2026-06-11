# REVIEW-T8 — adversarial QA of track T8 (`feat/examples`)

**Reviewer:** tw-qa (skeptical QA, runs the gate, distrusts prose)
**Branch:** `feat/examples` — worktree `/home/mauriciobenjamin700/projects/my/tempestweb-T8`
**Base:** `2e3a9bf`
**Commits ahead of base:** `4becb75` (wip impl), `e73c71f` (SUMMARY), `e62d521` (code-quality pass)

## VERDICT: PASS-WITH-GAPS

The gate is fully green from a clean state, every done-when clause maps to a real
passing assertion, the examples use the genuine vendored-core widget API (no
fabricated widgets, no `NotImplementedError`, no skipped/xfail tests), and the
track stayed strictly inside its file scope (`examples/{todo,form,fetch}/**`,
`tests/unit/test_examples.py`, `SUMMARY-T8.md`) — `tempestweb/_core/**` and
`examples/counter/**` untouched. The single deduction: three of the user-facing
handler closures (`todo.add_item`, `todo.toggle`, `form.submit`) are **never
invoked by a test** — their state-mutation logic is unverified.

## Gate output (run from clean state)

```text
$ .venv/bin/ruff check .
All checks passed!                       (exit 0)

$ .venv/bin/ruff format --check .
19 files already formatted               (exit 0)

$ .venv/bin/mypy tempestweb
Success: no issues found in 9 source files   (exit 0)

# examples are NOT in `mypy tempestweb` (config targets the package only),
# so verified each individually under --strict:
$ .venv/bin/mypy --strict examples/{todo,form,fetch,counter}/app.py
Success: no issues found in 1 source file   (x4, exit 0)

$ .venv/bin/pytest tests/unit/test_examples.py -q
11 passed in 0.15s                       (exit 0)

$ .venv/bin/pytest -q          # full suite, no regression
15 passed in 0.15s                       (exit 0)
```

ruff lint config confirms `examples/*` is exempt only from `D` (docstrings),
**not** from `ANN` (annotations) or `Q` (double-quotes) — so the examples are
held to the typing/quote gate, and they pass it.

## Done-when checklist (from docs/agents/MANIFEST.md T8)

| Clause | Proof | Status |
|---|---|---|
| Each example imports | `_load_example` + `test_example_imports_and_builds` (parametrized counter/todo/form/fetch) | PASS |
| `build(view())` validates and yields a tree | same test asserts `isinstance(node, Node)`, non-empty `type`, non-empty `children` | PASS |
| input widget exercised | `test_todo_exercises_input_and_list` asserts `Input` in tree; `test_form_exercises_form_widgets` asserts `Input` under each `FormField` | PASS |
| list widget exercised | `test_todo_exercises_input_and_list` asserts `LazyColumn` + `Checkbox`, window len == seeded count; `test_fetch_async_handler_drives_ui` asserts loaded `LazyColumn` has 3 rows | PASS |
| form widget exercised | `test_form_exercises_form_widgets` (Form/FormField/Input structure) + `test_form_validation_surfaces_errors` (real `Form.validate` → errors on empty, clean on valid) | PASS |

Bonus coverage beyond the done-when: async handler lifecycle is genuinely driven
(`test_fetch_async_handler_drives_ui` awaits the real `load` closure;
`test_fetch_error_phase_surfaces_message` injects a raising fetch and asserts the
error message reaches the IR), and `diff(before, after)` is exercised in
`test_todo_add_item_transition`.

## Findings (prioritized)

### P2 — handler closures not exercised (coverage gap, not a failure)
The done-when says widgets are "exercised" and is satisfied at the widget/IR
level. But three real handlers ship untested:

- `examples/todo/app.py::add_item` — contains live logic (`title.strip()`, the
  empty-title guard, append + draft-clear). `test_todo_add_item_transition`
  **reimplements that effect inline** (`app.state.items.append(...)`,
  `app.state.draft = ""`) instead of calling `add_item`, so a regression inside
  `add_item` (e.g. dropping the `.strip()` or the empty guard) would pass the
  suite.
- `examples/todo/app.py::toggle` — the per-row `Checkbox.on_change` closure; never
  invoked. The flip logic (`done = not done`, correct index capture via
  `i=index`) is unverified.
- `examples/form/app.py::submit` — only the pure `Form.validate` is called
  directly; the `submit` closure that wires `validate` → `set_state`
  (`errors`/`submitted` mirroring) is never driven.

Closing it is cheap: drive each closure via the existing `_find_handler` walker
(already used for the fetch `load` handler) and assert the resulting state.

### P3 — `__pycache__` artifacts tracked in the worktree (not committed)
`examples/*/__pycache__/*.pyc` exist on disk. They are gitignored (working tree
is clean, `git status` reports nothing) so this is cosmetic, not a defect.

## Convention scan
- Double quotes: clean (ruff `Q` passes on examples + tests).
- Full typing: `mypy --strict` clean per example; the two `# noqa: ANN401` are on
  legitimately-opaque widget-tree walkers in the test file (and `tests/*` is
  ANN-exempt anyway).
- Docstrings: Google-style English on every module/class/function in the examples
  and the test helpers.
- No TypeScript / no build step introduced (no client files touched).
- No edits to `tempestweb/_core/**`; no files outside track scope.

## Bottom line
Ship-quality for T8's stated done-when. The only thing standing between this and a
clean PASS is that the example handler logic itself is asserted indirectly — worth
a follow-up test, not a blocker.
