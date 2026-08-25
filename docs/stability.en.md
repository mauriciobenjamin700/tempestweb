# Stability & support

!!! abstract "What you'll find"
    The stability contract on the road to 1.0 (S10) and the **Mode C subset
    contract** (S11): what is public and stable, what may change, which browsers
    are supported, and where the accessibility baseline is.

## Versioning (road to 1.0)

tempestweb is **pre-1.0** (`0.x`). Until then:

- **Public surface** = what you import from `tempestweb` and its documented
  subpackages (`tempestweb.server`, `tempestweb.native`, `tempestweb.transpile`,
  `tempestweb.html`, `tempestweb.pwa`, `tempestweb.cli`) + the **wire contract**
  ([`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md)). Underscored names are private.
- **Compatibility:** a `0.x` minor may carry documented behavior changes (see the
  [CHANGELOG](https://github.com/mauriciobenjamin700/tempestweb/blob/main/CHANGELOG.md)).
  Pin the version in production.
- **Deprecation (from 1.0):** a feature slated for removal gets a warning for at
  least one minor before it goes; removals only in a major.

## Browser matrix

| Browser | Mode A (WASM) | Mode B (server) | Mode C (transpile) |
|---|---|---|---|
| Chrome/Edge ≥ 111 | ✅ | ✅ | ✅ |
| Firefox ≥ 110 | ✅ | ✅ | ✅ |
| Safari ≥ 16.4 | ✅¹ | ✅ | ✅ |

Requirements: ES modules + `fetch` + WebSocket/EventSource. Installable PWA needs
HTTPS; iOS push requires the app to be **installed** (Safari ≥ 16.4). ¹Pyodide
boot (Mode A) is heavier on Safari/mobile — prefer B or C for first-paint/SEO.

## Accessibility

The client emits semantic HTML with roles/aria from `Widget.semantics`
(`aria-label`/`role`/`aria-description`), `tabindex` from `focus_order`, and uses
native controls (`<input>`/`<button>`) wherever possible.

**The baseline is measured, not declared.** The CI `a11y` job runs **axe-core**
over the DOM the real renderer builds, for scenes generated from the apps this
repo ships (`tests/conformance/_a11y_scenes.py` → `scripts/a11y-gate.mjs`), and it
**blocks the merge** on a `serious` or `critical` violation:

| What the gate catches | What it does not |
|---|---|
| a control with no accessible name, an image with no `alt`, an invalid `role`, a nested interactive, a label with no field, a duplicate `id` | colour contrast and installability — they need real layout, and live in the Lighthouse layer (`pwa.yml`) |

The scenes are **generated**, not hand-written: the Mode C component gallery, the
control panel, a list with a text field, a form, a nav shell with a drawer and an
image screen. Auditing hand-written markup would prove the test's snippet is
accessible, not that the renderer is.

One rule may only be loosened in writing: an axe rule that cannot apply to a scene
goes into `KNOWN_EXCEPTIONS` **with its reason** (today: the three whole-document
rules — `landmark-one-main`, `page-has-heading-one`, `region` — plus
`color-contrast`, which belongs to the Lighthouse layer). Silencing without a
written reason is what turned "accessibility baseline" into an empty claim before.

## The wire contract is frozen

The wire contract ([`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md))
is part of the stable surface, so it carries **its own version** — independent of
the package version — in `tempestweb.contract`:

```python
from tempestweb.contract import WIRE_CONTRACT_VERSION, WIRE_SHAPE_DIGEST
```

The golden fixtures already caught accidental drift, but they are **regenerable
from the core**: they cannot tell "I regenerated because the core moved" from "I
changed the contract". `WIRE_SHAPE_DIGEST` can — it hashes the wire's **shape**
(every key and its type, never its value), so:

| Change | Digest | Version | What else |
|---|---|---|---|
| a fixture regenerated with new values | same | same | nothing |
| a new optional key, a new envelope `kind`, a new event `type` | moves | **same** | a CHANGELOG entry |
| a key renamed/removed/retyped, patch semantics changed | moves | **bump** | a migration note |

`tests/unit/test_wire_contract_freeze.py` fails on a shape change and names, in
its message, which of the two choices the author owes. A third-party client pins
`WIRE_CONTRACT_VERSION` and knows what it is talking to.

## Mode C subset contract (S11)

The transpiler accepts a **typed subset** of Python — stable and fail-loud
(`file:line` for anything outside it). See the full list in the
[Mode C guide](advanced/transpile.md#the-supported-subset).

**In (stable):** dataclasses (inheritance/methods/kwargs), `view()` + handler
closures, full arithmetic, chained comparison, comprehensions (list/dict, with
tuple targets), literals, slices, formatted f-strings, common builtins, stdlib
string/list/dict methods, `if/for/while/break/continue/try-except-finally/with/
raise/assert`, unpacking, chained assignment, navigation/i18n/theme/animation/
validators, and all `native/` capabilities.

**Out (by decision):** `global`, `yield`/generators, `del`, the walrus (`:=`),
`raise ... from`, starred unpacking, arbitrary decorators (only `@dataclass`),
and most of `tempest_core.components` (Python composition that expands at
`build()` time — use Modes A/B, or primitives/HStack/VStack in C). Porting the
components (a JS resolver layer) remains on the [roadmap](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md) — S11.

!!! tip "A/B/C portability"
    A `view()` within the subset runs **identically** in all three modes.
    `build --mode transpile` proves it by rendering through the real core — a
    Mode-C-only API would break the build.

## Recap

- Pre-1.0: documented public surface + wire contract; pin the version.
- Modern browsers (recent Chrome/Edge/Firefox/Safari) in all three modes.
- a11y via semantics/roles; an axe gate is a follow-up.
- The Mode C subset is a stable, fail-loud contract; components stay in A/B.
