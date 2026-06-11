# QUALITY-T10 — code-quality pass on `feat/observability`

Track T10 (Trilho O — observability providers) was reviewed against the
tempest-fastapi-sdk / tempestroid bar (Google docstrings, full typing under ruff
`ANN`+`D` and mypy `--strict`, double quotes, module-level re-exports + `__all__`,
fail-safe collections, async-first).

## Applied (quality only, no behavior change)

- **`auth.py` `__all__` consistency.** `__init__.py` re-exported `AuthListener`
  and `RefreshFn`, but `auth.__all__` did not declare them public — inconsistent
  with the project rule that `__init__` aggregates each submodule's *declared*
  public surface (the parallel `ChangeListener` in `feature_flags.__all__` and
  `AuthState`/`RefreshQueue` were already listed). Added both names to
  `auth.__all__`. Pure re-export bookkeeping; no runtime behavior change. Verified
  by an AST cross-check that every `__init__` re-export now appears in its
  submodule's `__all__` (all 5 modules: NONE missing).

## Verification

Tools run from the project's pyenv 3.11.13 interpreter:

- `ruff check tempestweb/observability tests/unit/test_observability*.py` → All checks passed.
- `ruff format --check tempestweb/observability` → 6 files already formatted.
- `pytest tests/unit/test_observability*.py -q` → **54 passed**.
- Import smoke: `from tempestweb.observability import AuthListener, RefreshFn` resolves; both in `__all__`.

**mypy was NOT run:** `mypy` is not installed in this environment (only `ruff` and
`pytest` are present under `~/.pyenv/versions/3.11.13/bin`). The ruff `ANN` family
(part of the gate) passed clean, and every public surface is fully annotated by
inspection, but a `mypy --strict tempestweb/observability` run still needs to be
executed once mypy is available. This is a tooling gap, not a code defect.

## Deferred (would require a behavior / signature change — NOT applied)

These are observations left untouched because fixing them changes behavior beyond
"adding types". They are flagged for the author to decide.

1. **`telemetry.TelemetryProvider._should_sample` — deterministic-sampling math
   looks off for fractional rates.** The intent (docstring) is "with
   `sample_rate` 0.5 every other event is forwarded." The current expression
   `(self._counter * self._sample_rate) % 1.0 < self._sample_rate` does yield the
   advertised ~50% for 0.5, but for other rates (e.g. 0.3) the spread is uneven
   and the *first* event at low rates can be dropped/kept counter-intuitively.
   A more standard deterministic decimator is "forward when
   `floor(counter * rate) != floor((counter-1) * rate)`". Changing it alters which
   events are forwarded → behavior change, deferred. Tests currently assert the
   existing behavior, so this must be co-decided with the test update.

2. **`auth.RefreshQueue.refresh` uses `asyncio.ensure_future`.** For a coroutine,
   `asyncio.create_task(...)` is the modern, more explicit idiom (3.11+) and is
   semantically equivalent here (the argument is always a coroutine from
   `self._run()`). Left as-is to avoid any scheduling-semantics surprise without a
   dedicated test; a one-line swap to `create_task` is a safe follow-up if desired.

3. **`__all__` ordering is logical, not alphabetical (RUF022).** RUF022 is *not*
   in the project gate (`select = E,W,F,I,N,UP,B,C4,SIM,Q,ANN,D`). The current
   grouping (Adapter Protocol → Provider → concrete adapters) is intentionally
   semantic and more readable than isort order. Not changed — enforcing RUF022
   would be a stylistic regression and is outside the configured standard.
