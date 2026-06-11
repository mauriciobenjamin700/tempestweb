# REVIEW-T5 — adversarial QA of track T5 (`feat/cli-devloop`)

**Verdict: PASS-WITH-GAPS**

The done-when is met by real, asserting automated tests; the gate is green from a
clean sync; the binary works end to end. The only blemishes are (1) an
overclaim in the implement report — the "live `watchfiles` edit through the
production loop" was *not* actually written as a test (the production
`_watchfiles_stream`/`awatch` adapter is never exercised), and (2) the
artifact-layout proof is structural only, since the wasm `bootstrap.js` and
server `server.py` `run()` are deliberate stubs owned by T3/T2. Neither blocks the
T5 done-when, which the manifest scopes to the *stub transport* and *layout*.

## Gate output (clean `uv sync --extra cli --extra server --extra dev`)

```text
ruff check .            -> All checks passed!
ruff format --check .   -> 32 files already formatted
mypy tempestweb         -> Success: no issues found in 19 source files
pytest tests/unit/test_cli*.py -q  -> 66 passed in 0.28s   (track gate)
pytest -q                          -> 68 passed in 0.27s   (full)
```

End-to-end binary run (`uv run tempestweb ...`):

```text
tempestweb new myapp        -> creates app.py/tempestweb.toml/README.md/.gitignore
                               (app.cpython-313.pyc proves app.py was imported by verify)
tempestweb build --mode wasm   -> index.html, bootstrap.js, app.py, client/{tempestweb,dom,style,events,transport,transport-wasm}.js
tempestweb build --mode server -> server.py, app.py, static/{...,transport-ws}.js
load_app + render_initial_tree on the scaffold -> rendered root type: Node (runnable, real)
```

## Done-when checklist

| Clause | Status | Proof |
|---|---|---|
| `tempestweb new X` creates a runnable project tree | PASS | `test_scaffold_project_writes_runnable_tree`, `test_create_project_verifies_runnable`, `test_new_dispatch_creates_project`; runnability is enforced (`load_app`+`render_initial_tree` in `create_project`) and negatively proven by `test_create_project_reports_unrunnable_scaffold` / `test_build_unrunnable_project_raises`. Confirmed live. |
| dev watcher detects a change and emits a reload (stub transport) | PASS (with gap) | `test_dev_session_watcher_change_reaches_transport`, `test_dev_session_run_loop_records_reloads`, `test_watcher_run_consumes_stream`, full `ReloadSignal` suite. All drive an **injected** stream / `handle_batch` — the legitimately automatable path per the manifest. GAP: the **production** `watchfiles.awatch` adapter (`_watchfiles_stream`) is never run by any test, contradicting the report's "live `watchfiles` edit through the production loop" claim. |
| `build --mode` produces the expected artifact layout | PASS | `test_build_wasm_layout`, `test_build_server_layout` assert every file in `WASM_ARTIFACT_FILES`/`SERVER_ARTIFACT_FILES` exists on disk; `test_wasm_*`, `test_server_entrypoint_exposes_run`, out-dir/clean/default-mode/invalid-mode all covered. Confirmed live. |

## Hunt results (no blockers found)

- **No `tempestweb/_core/**` edits.** Diff is confined to `tempestweb/cli/*`,
  `tempestweb/devserver/*`, `tests/unit/test_cli*.py`, `SUMMARY-T5.md`,
  `QUALITY-T5.md`. In scope.
- **`tempestweb/cli/main.py` edit is in scope.** The manifest excludes "`main.py`
  topo" = the repo-root one-liner, which is **untouched** (`git diff main...HEAD --
  main.py` empty). `tempestweb/cli/main.py` already existed on `main` as a skeleton;
  fleshing out its dispatch is continuation, not scope creep.
- **No assert-nothing / skipped / xfail tests.** 66 collected, all real
  assertions. The two `# pragma: no cover` markers are on an empty async generator
  (test helper) and the `watchfiles` import guard — legitimate.
- **`NotImplementedError` behind green tests:** present in the *generated artifact*
  `server.py run()` (Track T2's seam) and the wasm `bootstrap.js` `boot()` throws
  (Track T3's seam). These are deliberately marked stubs in T5-owned scaffolding,
  not T5 runtime code masquerading as done. Acceptable per manifest ("mocka/stuba a
  dependência").
- **No TypeScript / build step introduced.** T5 touches no client `.js`; it only
  *copies* the existing pure-JS assets from `client/`.
- **Convention compliance:** ruff (`ANN`+`D`+`Q` double-quotes) and `mypy --strict`
  both clean. No real single-quote string literals (flagged hits are apostrophes in
  docstrings and `'''`-delimited embedded-file templates, which avoid escaping the
  inner `"""` — ruff accepts them). All public funcs typed + Google docstrings.

## Prioritized findings

1. **(P2 — overclaim) The "live `watchfiles` edit through the production loop"
   reload proof does not exist as a test.** Every reload test injects a stream or
   calls `handle_batch`; `_watchfiles_stream`/`awatch` is uncovered. The done-when
   is still satisfied (stub-transport reload via injected stream is what the
   manifest asks for), but the report's wording overstates coverage. Add an
   integration test that writes a real `.py` file under `tmp_path` and asserts the
   signal fires through `watcher.run(stream_factory=_watchfiles_stream)` (mark as
   timing-sensitive / optional), or correct the SUMMARY wording.
2. **(P3 — expected stubs) wasm `bootstrap.js boot()` and server `server.py run()`
   raise/throw.** Owned by T3/T2; layout is the only T5 deliverable here. Fine, but
   the artifacts are not yet servable — `tempestweb run` correctly stops at "ready
   to serve" and is honest about it.
3. **(P3 — no manual-verify doc) No `NOTES-T5.md`.** None needed: nothing in T5 is
   gated on a real browser/device (the visual wasm boot belongs to T3/T9). Noted for
   completeness.

## Pre-existing, T5-untouched (flagged by implementer, confirmed not T5's problem)

`node --test tests/client/` (directory form) path-resolution failure is in the JS
runner config, not T5 (T5 ships no client JS). Out of scope for this review.
