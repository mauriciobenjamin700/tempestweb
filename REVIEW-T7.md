# REVIEW-T7 — Conformance harness

**Reviewer:** skeptical QA (run-it-don't-trust-it)
**Branch:** `feat/conformance`
**Worktree:** `/home/mauriciobenjamin700/projects/my/tempestweb-T7`
**HEAD at review:** `48d5982 wip(T7): uncommitted work from interrupted prior run`

## VERDICT: PASS

The track's DONE WHEN is met by passing, falsifiable automated tests. I tried to
disprove it (tampered the golden, audited for vacuous asserts, verified the real
core actually emits the pinned shapes) and could not. One scope-boundary note is
recorded below as a low-priority finding, not a blocker.

---

## Gate output (from clean `make setup`)

```
make setup                                   # OK (uv venv + deps + npm install)

.venv/bin/pytest tests/conformance -q
20 passed in 0.26s                           # PRIMARY GATE — PASS

.venv/bin/pytest -q                          # whole repo
24 passed in 0.17s                           # PASS (no collateral breakage)

.venv/bin/ruff check tests/conformance tests/fixtures
All checks passed!

.venv/bin/ruff format --check tests/conformance
7 files already formatted

.venv/bin/mypy tempestweb
Success: no issues found in 9 source files

.venv/bin/mypy tests/conformance             # extra scrutiny (not in gate)
Success: no issues found in 7 source files
```

`node --test` not applicable — T7 added no client JS.

---

## DONE-WHEN checklist (each clause -> proof)

| Clause | Proof | Status |
| --- | --- | --- |
| Generate patches from the **real core** | `_scenarios.scenario_to_fixture` calls `tempestweb._core.build`/`diff`; nothing hand-typed. Verified the live core emits the same shapes (replace = `node` w/o `index`; insert = `node`+`index`). | PASS |
| Lock the wire-format shape (**regenerable goldens**) | `_generate.render_fixture_text()` rebuilds the golden; `test_conformance_fixture_matches_core` asserts on-disk == fresh render. I confirmed MATCH (6600 == 6600 bytes) and that `python -m tests.conformance._generate` is the documented regen path. | PASS |
| Pin the **contract shape** | `test_node_ir_shape` (4 top-level keys), `test_text_props_carry_content`, `test_button_props_carry_label_and_handler_ref`, `test_all_five_patch_kinds_are_emitted_and_classified`, `test_patch_paths_are_index_lists`. All five patch kinds verified present across goldens: counter=[update,update], list=[insert,reorder,remove], replace=[replace]. | PASS |
| Assert **transport-independence** of rendered DOM (A-vs-B) | `test_two_transports_render_identical_dom` feeds MockTransportA (in-process) and MockTransportB (JSON round-trip) the same stream; asserts `final_a == final_b` AND both `== fixture["final"]` (guards against "two identical bugs agreeing"). | PASS |
| New fixtures under `tests/fixtures/` | `conformance_scenarios.json` committed (313 lines), derived from core. | PASS |

---

## Anti-cheat audit (what I hunted for)

- **Vacuous/assert-nothing tests:** none. Every test has real `assert`s. No
  `pytest.skip`, `xfail`, or empty bodies in `tests/conformance/`.
- **Golden is a real lock, not decoration:** tampered `counter.final.key` ->
  `TAMPERED`; suite went RED (2 failures: `test_conformance_fixture_matches_core`,
  `test_scenario_ticks_match_golden[counter]`). Restored byte-exact -> 20 passed,
  `git status` clean. The lock is falsifiable.
- **Real core, not invented shapes:** independently ran `diff` on the live core
  and confirmed insert/replace/reorder/remove/update shapes match what `patch_kind`
  classifies and what the goldens contain.
- **Protocol conformance is genuine:** `tempestweb.transports.base.PatchTransport`
  is `@runtime_checkable` (line 29), so `isinstance(MockTransport*, PatchTransport)`
  in `test_transports_satisfy_the_patch_transport_protocol` is valid.
- **No `tempestweb/_core` edits:** `git log 2e3a9bf..HEAD -- tempestweb/_core` empty.
- **No out-of-track files:** diff touches only `tests/conformance/*` and
  `tests/fixtures/conformance_scenarios.json`.
- **Python style:** double quotes, full type hints, Google docstrings throughout
  (tests are D/ANN-exempt per pyproject, but the harness is fully typed and
  documented anyway — mypy clean confirms types).
- **No TypeScript / no build step:** T7 added no client code at all.

---

## Findings (prioritized)

### Low — F1: `native_call`/`native_result` and Style/Color/Edge object shapes are not re-locked by the new harness
`docs/contract.md` defines a `native_call`/`native_result` protocol (lines
141-159) and the `Style`/`Color`/`Edge` wire objects (lines 68-99). The new
conformance harness pins **node IR + the five patch kinds + the `{type,key,payload}`
event shape**, but does not add a golden for `native_call`/`native_result`, nor a
regenerable golden for the Style/Color/Edge serialization. The pre-existing
`tests/fixtures/style_sample.json` exists but is not asserted against the live core
by this track (only `patches_all_kinds.json` is, via
`test_legacy_patches_all_kinds_fixture_still_matches_core`).

Impact: the contract surface most relevant to T2/T3 (native bridge) and to the
style renderer is not yet drift-protected by a regenerable golden. This is a
reasonable scope boundary (native framing is owned by T2/T3), and the stated
DONE WHEN ("pins the contract shape" for patches + transport independence) is met
— so this is a *follow-up*, not a gate failure.

Suggested follow-up (not required for this track): add a `style_sample` and a
`native_call`/`native_result` golden into the same regenerable `_generate` flow
once the core/transport expose them.

### Low — F2: MockTransportA and MockTransportB share the same `apply_batch`
The two doubles differ only by a JSON `dumps`/`loads` round-trip before applying
the identical applicator. This genuinely tests wire-serialization independence
(number coercion, key ordering, tuple->list) — the most likely real divergence —
but it does **not** test two *independent applicator implementations*. The true
A-vs-B risk in production is the JS DOM patcher (`client/dom.js`) diverging from
the Python path; that can only be closed by the JS-side jsdom tests (track for the
client), which are out of T7's scope. The Python reference applicator is correctly
framed as "the contract's executable specification," and the test asserting both
transports also equal `fixture["final"]` (the core's own output) mitigates the
"shared bug" risk. Acceptable for this track; noted so the human doesn't overread
the guarantee.

---

## Bottom line
Clean-room gate is green, the goldens are real and regenerable, the A-vs-B test is
non-vacuous and tied back to the core's own output, and nothing outside the track
was touched. **PASS.** The two low findings are scope-boundary follow-ups, not
defects in what T7 shipped.
