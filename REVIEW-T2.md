# REVIEW-T2 — adversarial QA of track T2 (`feat/mode-server`)

**VERDICT: PASS-WITH-GAPS**

Reviewed by the QA stage from a clean install. The done-when is substantially met:
WS connects → initial patches → click → Update patch, two connections stay
independent, and the SSE transport carries the identical patch stream with `id:`
framing, `ping` heartbeats, and `Last-Event-ID` replay. The full gate is green.
The one real gap: the literal done-when says SSE delivers "via EventSource +
**POST**", but the SSE pytest suite drives the transport object directly and
injects clicks with `feed_inbound(...)`; the FastAPI SSE HTTP plumbing
(`GET /sse` stream, the `204` success POST path, `_drop_sse`/`body()` wiring) has
**no end-to-end test** — only the `404` POST path is exercised through the real app.

## Gate output (run from clean `uv pip install -e ".[dev,server,cli]"` + `npm install`)

```
ruff check .            -> All checks passed!                       (exit 0)
ruff format --check .   -> 23 files already formatted               (exit 0)
mypy tempestweb         -> Success: no issues found in 14 source files (exit 0)
pytest -q               -> 13 passed, 1 warning in 0.40s            (exit 0)
pytest tests/unit/test_server*.py -q -> 9 passed                   (exit 0)
node --test tests/client/**/*.test.js -> tests 10 / pass 10 / fail 0 (exit 0)
```

The 1 pytest warning is a Starlette `TestClient` httpx-deprecation notice, not a
failure.

## Done-when checklist (each clause vs. an actual passing test)

| Clause | Proof | Status |
|---|---|---|
| Test client connects over WS, receives initial patches for the counter | `test_server_ws.py::test_ws_initial_patches_and_click_update` — real `TestClient(create_app(...))`, asserts initial `kind=="patches"`, root `path==[]`, label `Count: 0` | PASS |
| ...sends a click, receives the resulting Update patch | same test — sends `{kind:event, data:{click, inc}}`, asserts Update `set_props=={"content":"Count: 1"}`, `path==[0]` | PASS |
| SSE transport delivers the same patch stream via EventSource... | `test_server_sse.py::test_sse_initial_mount_click_update_and_ping` — `id:` framing, `Count: 1`, named `ping`; `test_sse_last_event_id_replay_on_reconnect` — replay of missed ticks | PASS (transport level) |
| ...+ POST | **Only the 404 path** (`test_sse_post_to_unknown_session_returns_404`) hits the real `POST /sse/{id}`. The happy path (`204`, `feed_inbound` routing into a live session) and `GET /sse` streaming are NOT tested through the app — clicks are injected via `transport.feed_inbound()` | **GAP** |
| Two connections keep independent state | WS: `test_ws_two_connections_keep_independent_state`; SSE: `test_sse_two_transports_keep_independent_state` — both assert one click yields `Count: 1`, never leaks | PASS |

## Findings (prioritized)

### P1 — SSE HTTP endpoints (POST 204 + GET stream) have no passing test
`server/app.py::_handle_sse_post` (the `204` success branch + `feed_inbound`
routing) and `_open_sse`/`body()` (the `GET /sse` streaming response and
`_drop_sse` cleanup) are exercised by **zero** tests. The SSE suite asserts the
transport in isolation and uses `feed_inbound`, so the actual wire path a browser
uses ("EventSource + POST", named in the done-when) is unproven end-to-end. A
TestClient-level test that opens `GET /sse?session=...`, reads the first frame,
`POST`s a click to `/sse/{id}`, and reads the resulting Update would close it.
Note: Starlette's `TestClient` streaming/SSE consumption is awkward, which likely
explains the shortcut — but it leaves the literal done-when clause untested.

### P2 — Live-browser verification recorded in SUMMARY-T2.md, no `NOTES-T2.md`
Real `WebSocket`/`EventSource`/`Last-Event-ID` auto-reconnect can only be faked in
jsdom; the manual steps are listed in the agent's report and `SUMMARY-T2.md` but
not in a `NOTES-T2.md`. Acceptable per CLAUDE.md (recorded on the branch), flagged
for the morning merge: real-browser counter mount + increment over `/ws` and
`/sse` still needs a human pass after W1's renderer lands.

## Convention / overclaim audit (all clean)

- `tempestweb/_core/**` **untouched** (`git diff` empty). Good.
- No files edited outside the T2 manifest scope. `pyproject.toml`/`uv.lock` add
  only `httpx` as a dev dep for the FastAPI test client — in-track and justified.
- No `NotImplementedError`/TODO/`xfail`/`skip` in T2 code or tests (the lone
  `NotImplementedError` is in vendored `_core/widgets/base.py`).
- No assert-nothing tests: every test asserts concrete envelope shapes and content
  values against real fixtures; the WS/SSE pytest suites drive the **real**
  reconciler through `create_app`/`AppSession`. The reported `patch_to_wire`
  serialization fix is real and documented.
- Python: double quotes, full typing (mypy `--strict` clean incl. justified
  `ANN401` `# noqa` on `native_call`/`_json_safe`), Google docstrings throughout.
- Client: pure JS, ES modules, JSDoc, double quotes, no TypeScript, no build step.
  jsdom doubles (`WebSocketImpl`/`EventSourceImpl`/`fetchImpl`) are injected, which
  is the sanctioned way to test transports without a real browser.

## Bottom line

Strong, honest track. The runtime, transports, and serialization are real and
well-tested; isolation and SSE replay are genuinely proven. It is **not** a clean
PASS only because the "via ... POST" half of the SSE done-when is verified at the
transport object, not through the FastAPI POST/stream endpoints. Close the P1
end-to-end SSE-over-HTTP test and this is a full PASS.
