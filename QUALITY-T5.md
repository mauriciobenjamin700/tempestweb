# QUALITY — Track T5 (CLI + dev loop)

Code-quality pass on `feat/cli-devloop`. Applied quality-only fixes (no behavior
or public-signature changes beyond docstring/string content). Branch stays green.

## Baseline (before the pass)

All gates were already green on the branch:

    ruff check tempestweb tests        # All checks passed (full set: E,W,F,I,N,UP,B,C4,SIM,Q,ANN,D)
    ruff format --check tempestweb tests  # 31 files already formatted
    mypy tempestweb                    # Success: no issues found in 19 source files
    pytest -q                          # 68 passed
    pytest tests/unit/test_cli*.py -q  # 66 passed (track gate)

The T5 author had already met the lint/typing/docstring bar mechanically. This
pass focused on hand-quality issues the linters cannot catch: leftover template
syntax leaking into generated output and a docstring naming a symbol that does
not exist.

## Fixes applied

1. **`tempestweb/cli/scaffold.py` — leftover template placeholder in generated
   `app.py`.** `_app_py()` builds the scaffolded module with a plain `'''...'''`
   literal (not an f-string, not a template engine), so the module-docstring
   header `"""{{ app entrypoint }} — runs unchanged in both modes."""` was
   written **verbatim** into every generated user project — the Jinja-style
   `{{ }}` was never wired to any substitution. Replaced with a real sentence:
   `"""Application entrypoint — runs unchanged in both modes."""`. Pure string
   content; the file list, `make_state`/`view` contract, and `verify` render are
   unchanged (confirmed by re-running `create_project(..., verify=True)` and
   asserting no `{{` remains).

2. **`tempestweb/cli/commands/run.py` — module docstring referenced a
   nonexistent `serve_artifact`.** The docstring claimed `:func:`serve_artifact``
   was "the seam that a real server fills in", but no such function exists in the
   module (the module exports only `RunError`, `RunPlan`, `prepare_run`).
   Rewrote the sentence to describe the real seam: `prepare_run` produces the
   `RunPlan`, and a real server (T2/T3) plugs into that plan. Doc-only.

Both edits are string/docstring content. No function signature, return type,
control flow, or `__all__` changed.

## Not changed (deliberately)

- **`tempestweb/_core/**`** — vendored mechanical copy, out of bounds.
- **`client/*.js`** — owned by other tracks; T5 only *copies* these assets in
  `build.py`. The `{{ mount }}` / `{{` occurrences in `build.py`'s `_bootstrap_js`
  / `_server_py` are correct: they live inside f-strings, where `{{` escapes to a
  literal `{`. Not a defect.
- **Module-level `__all__` ordering** in `main.py`/`build.py`/`dev.py` etc. uses a
  logical (not strictly alphabetical) order. `RUF022` (sorted `__all__`) is not in
  the configured ruff select set, the package `__init__.py` exports are already
  sorted, and re-sorting the per-module lists would be churn with no gate benefit.
  Left as-is.
- **`# noqa: BLE001` blanket-except sites** (`loader.py`, `new.py`, `dev.py`,
  `build.py`, `run.py`) are intentional and documented inline: each normalizes an
  arbitrary import/render failure into the command's typed error. Correct idiom.
- **Stubbed seams** (`bootstrap.js` placeholder, `server.py` `run()` raising
  `NotImplementedError`, `StubTransport`, `prepare_run` stopping at the bind plan)
  are owned by Tracks T3/T2/T9 and clearly marked. Not defects.

## Deferred (needs a behavior change — NOT done here)

Nothing. Every issue found was fixable as a quality-only edit. No behavior-change
items were identified for T5's scope.

## Verification (after the pass — all green)

    ruff check tempestweb tests        # All checks passed
    ruff format --check tempestweb tests  # 31 files already formatted
    mypy tempestweb                    # Success: no issues found in 19 source files
    pytest tests/unit/test_cli*.py -q  # 66 passed (track gate)
    pytest -q                          # 68 passed

Plus a manual re-render check: `create_project("demoapp", verify=True)` renders
the scaffold and the generated `app.py` no longer contains `{{`.
