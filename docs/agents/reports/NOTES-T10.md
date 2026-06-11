# NOTES-T10 — manual verification deferred from QA round 1

This file records the QA round-1 gaps on Track T10 (`feat/observability`) that
**cannot be verified automatically in this worktree** and must be checked by hand
before production. P1 was closed in code (a real test); P2 and P3 are honest
deferrals captured here with concrete, reproducible steps.

## Status summary

| Gap | Kind | Status |
| --- | --- | --- |
| P1 — `server_decode_jwt` untested | code | **Closed.** Two unit tests added (success path via injected fake `JWTUtils` + `dict()` coercion; SDK-absent `RuntimeError`). `# pragma: no cover` dropped. |
| P2 — vendor adapter method shapes vs real SDKs | manual | **Deferred.** Asserted against mocks only; verify against pinned versions before production. Steps below. |
| P3 — error boundary live DOM effect | manual | **Deferred.** Python render side fully tested; visual effect needs the T1 client patcher in a browser post-merge. Steps below. |

---

## P2 — confirm vendor adapter method shapes against pinned real SDK versions

The adapters call third-party SDKs through `Any`-typed injected clients, so a
method-name/signature mismatch only surfaces at runtime. Each is asserted against
a mock in `tests/unit/test_observability_*.py`, which proves the **adapter**
forwards correctly but not that the **real SDK** exposes that exact shape. Risk is
low and local: a mismatch is contained to a single adapter and never touches the
provider Protocol or call sites. Confirm the following before shipping to prod.

### Sentry (telemetry `SentryTelemetry`)
- Call sites: `tempestweb/observability/telemetry.py`
  - `self._client.capture_message(event, level="info", extras=props)`
  - `self._client.set_user({"id": user_id, **traits})`
- Verify against the pinned `sentry-sdk` version. Note: the module-level
  `sentry_sdk.capture_message(message, level=...)` accepts `level` but historically
  **not** `extras`; richer context goes through `sentry_sdk.set_context` /
  `push_scope`. Confirm the injected client object actually exposes
  `capture_message(... , extras=...)` and `set_user(dict)`, or adapt the adapter to
  the real surface.

### PostHog (telemetry `PostHogTelemetry`)
- Call sites: `tempestweb/observability/telemetry.py`
  - `self._client.capture(distinct_id=..., event=..., properties=...)`
  - `self._client.identify(distinct_id=..., properties=...)`
- Verify against the pinned `posthog` version. Recent `posthog` releases changed
  capture/identify signatures (e.g. `distinct_id` positional vs keyword, `properties`
  naming). Confirm the keyword form used here matches the pinned client.

### GrowthBook (feature flags `GrowthBookFlags`)
- Call site: `tempestweb/observability/feature_flags.py`
  - `self._client.get_feature_value(key, default)`
- Verify against the pinned `growthbook` SDK. Confirm `get_feature_value(key, default)`
  exists and returns the resolved value (some versions expose `is_on` / `eval_feature`
  with a result object instead).

### LaunchDarkly (feature flags `LaunchDarklyFlags`)
- Call site: `tempestweb/observability/feature_flags.py`
  - `self._client.variation(key, self._context, default)`
- Verify against the pinned `launchdarkly-server-sdk` version. Confirm
  `variation(key, context, default)` and the **context object shape** match the
  pinned SDK (the SDK migrated from `Users` to `Context` objects; the positional
  arg here must be the type that version expects).

### How to verify (suggested)
1. In a scratch environment, `pip install` the exact pinned versions the deploy
   uses.
2. For each SDK, `inspect.signature` the method (or read the release's API docs)
   and diff against the call site above.
3. If a signature differs, adjust the adapter and update its mock-based test so the
   mock mirrors the real surface (keeps the test honest).

---

## P3 — error boundary live DOM effect (post-merge, browser)

`ErrorBoundary.render()` Python behavior is fully covered by
`tests/unit/test_observability_error_boundary.py`: when the wrapped subtree raises,
the boundary returns the fallback node instead of propagating, the report hook
fires, and telemetry wiring is exercised. What is **not** verifiable in a
Python-only worktree is the live DOM effect — that a broken subtree shows its
fallback while the rest of the tree keeps rendering. That depends on the **T1
client patcher** applying the IR/patches in a real browser, which does not exist in
this track.

### How to verify post-merge (once T1 client patcher is available)
1. Build a tiny app whose `view()` mounts an `ErrorBoundary` around a child that
   throws on render, sibling-by-sibling with healthy nodes.
2. Run it in a browser (Mode A/Pyodide or Mode B/WebSocket).
3. Confirm visually + via DOM snapshot that:
   - the boundary's fallback node renders in place of the broken subtree;
   - sibling/parent nodes outside the boundary render normally;
   - the report hook fired (assert on the captured telemetry event).
4. Follow the global CLAUDE.md visual-verification rule (Playwright/chrome-devtools
   MCP, mobile + desktop breakpoints, console check) before claiming the visual
   effect works.
