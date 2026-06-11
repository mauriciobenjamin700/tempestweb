# REVIEW-T10 — adversarial QA of Track T10 (Trilho O — observability)

**Branch:** `feat/observability` · **Base:** `2e3a9bf` · **Reviewer stance:** skeptical QA, run-don't-trust.

## VERDICT: PASS-WITH-GAPS

The four done-when clauses are each backed by a real, passing automated test. The
full project gate is green from a clean checkout. The implementation does not edit
`tempestweb/_core/`, touches only the track's own dirs, and the agent's manual-check
notes are honest. The single substantive gap is that `server_decode_jwt` — public
exported surface — has **zero test coverage** on both its branches; it is, however,
out of the strict T10 (client-side) done-when scope, so it does not sink the track.

---

## Gate output (run from clean state)

```
$ uv run ruff check .
All checks passed!                                   EXIT 0

$ uv run ruff format --check .
26 files already formatted                           EXIT 0

$ uv run mypy tempestweb
Success: no issues found in 15 source files          EXIT 0

$ uv run pytest -q
58 passed in 0.18s                                   EXIT 0

$ uv run pytest tests/unit/test_observability*.py -q
54 passed in 0.19s
  test_observability_auth.py            19 passed
  test_observability_error_boundary.py   7 passed
  test_observability_feature_flags.py   10 passed
  test_observability_logger.py           8 passed
  test_observability_telemetry.py       10 passed
```

The scope-target command from the MANIFEST (`pytest tests/unit/test_observability*.py`)
is **green**.

---

## Done-when checklist (each clause vs. an actual passing test)

| Clause | Status | Proof |
|--------|--------|-------|
| Each provider exposes a minimal interface + ≥1 working adapter | PASS | O0 `TelemetryAdapter` Protocol + Console/Sentry/PostHog; O1 `LoggerSink` + `console_sink`; O2 `ErrorBoundary` + `default_fallback`; O3 `FeatureFlagsAdapter` Protocol + InMemory/GrowthBook/LaunchDarkly; O4 `AuthStore`/`RefreshQueue`. All 38 `__all__` names resolve (verified by import). |
| Swapping adapters changes no call sites | PASS | `test_swapping_adapter_changes_no_call_sites` exists in **both** telemetry (line 91) and feature_flags (line 63): one `emit(provider)` / `read(provider)` fn drives two different backends unchanged. |
| Per-provider unit tests pass with third-party instances mocked | PASS | Sentry/PostHog via `MagicMock` with `assert_called_once_with` on real method names; GrowthBook/LaunchDarkly via `MagicMock`; console via injected sink. 54 tests, every one asserts (AST-checked; the 3 "no-assert" hits are `pytest.raises` context managers — real assertions). |
| Refresh queue serializes concurrent refresh into a single renewal | PASS | `test_concurrent_refreshes_collapse_into_single_renewal`: 5 real `asyncio.create_task` callers, an `Event` holds the renewal open so waiters pile up, asserts `refresh_calls == 1` and all 5 get the same token. Reset-after-settle and failure-then-retry also covered. Not faked. |

---

## Convention audit

- **No `tempestweb/_core/` edits** — `git diff --name-only 2e3a9bf HEAD -- tempestweb/_core/` is empty. ✅
- **No files touched outside the track** — diff is confined to `tempestweb/observability/*`, `tests/unit/test_observability*.py`, `QUALITY-T10.md`, `SUMMARY-T10.md`. ✅
- **No single-quote string literals** — all `'` hits are apostrophes in prose/docstrings or doctest output (`'off'`); flake8-quotes (Q) passes. ✅
- **Full typing / docstrings** — mypy `--strict` clean over 15 files; ruff `ANN`+`D` (google) clean. The 3 `Any` params (`sink`, injected vendor clients) carry `# noqa: ANN401` justifications. ✅
- **No skip/xfail/NotImplementedError behind green tests** — the only `...` hits are Protocol method bodies + docstring examples; no stubbed behavior. ✅
- **Empty-collection convention** — N/A (no collection-returning lookups in this track). 
- **Client JS** — N/A (T10 is Python-only; no TS/build introduced). ✅

---

## Findings (prioritized)

### P1 — `server_decode_jwt` is untested public surface (the only real gap)
- Exported in `__all__` (line 110 of `__init__.py`) but **no test references it**.
- Both branches are uncovered: the ImportError branch carries `# pragma: no cover`,
  and the success path requires `tempest_fastapi_sdk`, which is **not installed** in
  this worktree (`ModuleNotFoundError` confirmed).
- The agent flags this honestly in SUMMARY note #2. It is also outside the strict
  T10 done-when (client-side providers); the MANIFEST treats server SDK use as a
  server concern. Hence a gap, not a failure.
- **Close it by:** adding a unit test that monkeypatches/injects a fake `JWTUtils`
  (or `sys.modules["tempest_fastapi_sdk"]`) to exercise the success path and the
  `dict(result)` coercion, plus an explicit test of the `RuntimeError` message on
  the SDK-absent branch (drop the `pragma: no cover` once tested).

### P2 — Vendor adapters assume SDK method shapes, unverified against real versions
- Sentry (`capture_message`/`set_user`), PostHog (`capture`/`identify`), GrowthBook
  (`get_feature_value`), LaunchDarkly (`variation`) are asserted only against mocks.
- Honestly flagged (SUMMARY manual-check #1). Low risk by design — a mismatch is
  local to one adapter and the provider/call sites are unaffected — but it remains a
  contract assumption, not a verified fact. Acceptable for a night build; confirm
  against pinned SDK versions before production.

### P3 — Error boundary's live DOM effect is unverifiable here (expected)
- `ErrorBoundary.render()` Python behavior is fully tested (fallback returned, no
  raise, report hook fires, telemetry wiring). The visual "broken subtree shows
  fallback while the rest keeps rendering" needs the T1 client patcher in a browser.
- Correctly deferred to post-merge manual verification (SUMMARY #3). No overclaim.

---

## Bottom line
Solid, idiomatic, well-tested track. Done-when is genuinely met for all five
client-side providers with non-trivial tests (the concurrent-refresh test in
particular is real, not a rubber stamp). Ship after closing P1 (a small test) and
honoring the P2/P3 manual checks before production.
