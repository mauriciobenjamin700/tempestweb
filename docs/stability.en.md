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

There are **two** jobs, because the rules split by what they need:

| Job | Where it runs | What it measures |
|---|---|---|
| `a11y` | jsdom | structure: a control with no accessible name, an image with no `alt`, an invalid `role`, a nested interactive, a label with no field, a duplicate `id` |
| `contrast` | real Chromium | `color-contrast` over the **painted** DOM, for scenes in **light and dark** |

Contrast needs a laid-out box to sample colours from, and jsdom produces none —
which is why it is the one rule the `a11y` job disables, and why the `contrast`
job exists. Both audit the **same** generated scenes, so they cannot drift.

The scenes are **generated**, not hand-written: the Mode C component gallery, the
control panel, a list with a text field, a form, a nav shell with a drawer and an
image screen. Auditing hand-written markup would prove the test's snippet is
accessible, not that the renderer is.

Coverage is measured by **widget type and by component**, and the second axis had a
hole: nine scenes and not one used the fields this repo owns
(`TextField`/`EmailField`/`PasswordField` and the two forms). The `login-form`
scene looks like it does and does not — it builds the core's
`EmailInput`/`PasswordInput` inside a `FormField`, which the renderer names. The
result: `PasswordField` shipped an anonymous control (`label`, critical) with a
green gate until 0.113.0. `login_demo` closes that axis.

!!! info "The theme goes into the scene, not onto the DOM"
    The dark scene is **built** under the dark theme
    (`tests/fixtures/a11y_scenes_dark.json`), not obtained by flipping an
    attribute on an already-rendered tree. What the core resolves — a `Text`'s
    colour, a `Card`'s surface — travels as inline style on the IR, so a tree
    built in light under the dark sheet is a mixture that exists in no app.
    Measured that way it reported 9 violations; built per theme, 2 — and those 2
    were real.

One rule may only be loosened in writing: an axe rule that cannot apply to a scene
goes into `KNOWN_EXCEPTIONS` **with its reason** (today: the whole-document rules —
`landmark-one-main`, `page-has-heading-one`, `region`). The contrast gate keeps its
own list, keyed by the **colour pair** rather than by rule, because the pair is
what has to change; today's entries all belong to `tempest-core`, whose palette
this repo pins and does not edit. Both gates report an exception that stopped
firing, so an exception list cannot rot in silence. Silencing without a written
reason is what turned "accessibility baseline" into an empty claim before.

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
- a11y via semantics/roles, measured by two merge-blocking gates: `a11y`
  (structure, jsdom) and `contrast` (painted `color-contrast`, Chromium, light + dark).
- The Mode C subset is a stable, fail-loud contract; components stay in A/B.
