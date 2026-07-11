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
  ([`docs/contract.md`](contract.md)). Underscored names are private.
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
native controls (`<input>`/`<button>`) where possible. An **axe-core CI gate** is
a Track-S follow-up (S10).

## Mode C subset contract (S11)

The transpiler accepts a **typed subset** of Python — stable and fail-loud
(`file:line` for anything outside it). See the full list in the
[Mode C guide](transpile.md#the-supported-subset).

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
components (a JS resolver layer) remains on the [roadmap](roadmap.md) — S11.

!!! tip "A/B/C portability"
    A `view()` within the subset runs **identically** in all three modes.
    `build --mode transpile` proves it by rendering through the real core — a
    Mode-C-only API would break the build.

## Recap

- Pre-1.0: documented public surface + wire contract; pin the version.
- Modern browsers (recent Chrome/Edge/Firefox/Safari) in all three modes.
- a11y via semantics/roles; an axe gate is a follow-up.
- The Mode C subset is a stable, fail-loud contract; components stay in A/B.
