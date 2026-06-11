# NOTES — Track T5 (CLI + dev loop)

## Manual verification

**No manual verification is needed for T5.** Nothing in this track is gated on a
real browser or device. The whole developer loop — `new`, `dev` (watcher +
reload signal), `build`, `run` (build + bind plan) — is exercised by automated
pytest tests under `tests/unit/test_cli*.py`, including the dev watcher's
production stream factory:

- `test_watcher_run_reloads_on_real_file_write` drives
  `watcher.run(stream_factory=_watchfiles_stream)` against a real `tmp_path`
  file write (polling backend forced via `functools.partial`, so the loop is
  deterministic on any filesystem — native inotify, WSL, network mounts).

Run the track gate:

```bash
ruff check tempestweb tests
ruff format --check tempestweb tests
mypy tempestweb
pytest tests/unit/test_cli*.py -q
```

## Expected stubs — confirm at merge (do NOT fix in T5)

Two seams are intentional placeholders owned by other tracks. Built artifacts are
therefore **not servable yet**; `tempestweb run` honestly stops at "artifact
built + bind plan ready". These are documented in `SUMMARY-T5.md` ("What is
stubbed") and marked in code:

| Stub | Location | Owner | Behavior today |
| -- | -- | -- | -- |
| wasm `bootstrap.js` `boot()` | `build.py` emitted app-shell | **T3** (Mode A) | `throw new Error("A3: Pyodide bootstrap is provided by Track T3")` |
| generated `server.py` `run()` | `build.py` server artifact | **T2** (Mode B) | `raise NotImplementedError("B0: server host is provided by Track T2")` |

**At merge, confirm T2/T3 replace these without changing T5's pinned layout:**

- The wasm artifact layout (`index.html` + `bootstrap.js` + `app.py` +
  `client/{tempestweb,dom,style,events,transport,transport-wasm}.js`) is final;
  T3/T9 fill `boot()` against it, they do not reshape it.
- The server artifact layout (`server.py` + `app.py` +
  `static/{...,transport-ws}.js`) is final; T2 fills `run()` against it.
- The `dev` reload path plugs the real transport into the same `ReloadSignal`
  seam — T5's `StubTransport` is the only piece that gets swapped, the signal
  contract stays put.
