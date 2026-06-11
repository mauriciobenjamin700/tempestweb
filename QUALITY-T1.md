# QUALITY — Track T1 (`feat/client-render`) code-quality pass

Branch raised to the tempest bar (plain JS only, double quotes everywhere,
complete/accurate JSDoc, no dead code / leftover `console.log`). No behavior
change and no public signature change beyond JSDoc type precision.

## Applied (this pass — `ref: code-quality pass on T1`)

- **Double-quote rule in tests.** Five `querySelector('[data-tw-key="..."]')`
  calls used single-quoted JS string literals — the only real quote-style
  violations on the branch. Converted to double-quoted literals with escaped
  inner attribute quotes (`querySelector("[data-tw-key=\"inc\"]")`) in
  `tests/client/events.test.js` (3) and `tests/client/mount.test.js` (2).
- **JSDoc accuracy — `client/dom.js` `applyUpdate`.** `set_props`/`unset_props`
  are both optional at runtime (`patch.set_props` is guarded; `patch.unset_props
  ?? []`), but the param JSDoc typed them as required. Marked optional
  (`set_props?:Object, unset_props?:string[]`) to match the contract's Update
  shape and the actual code.
- **JSDoc accuracy — `client/events.js` `payloadFor`.** Tightened the return
  type from the bare `{Object}` to `{{value?: string}}` and noted the two cases
  (`{ value }` for `input`/`change`, `{}` otherwise), matching what the function
  returns.

## Verification

```
node --test "tests/client/**/*.test.js"   # 36 pass / 0 fail (unchanged)
node --check <each T1 .js file>            # all parse OK
```

No single-quoted JS string literals, `console.*`, `debugger`, `var`, or
`TODO/FIXME` remain in the T1 surface (`client/{dom,events,style,tempestweb}.js`
and `tests/client/`).

## Deferred — needs a judgment/behavior decision, NOT applied

- **`client/events.js` `keyedAncestor` — redundant `el.hasAttribute &&` guard.**
  Line: `if (el.hasAttribute && el.hasAttribute(KEY_ATTR))`. By that point `el`
  has already been narrowed to element nodes (the preceding `nodeType !== 1`
  walk, and `parentElement` only ever yields elements), so `el.hasAttribute` is
  always defined and the `el.hasAttribute &&` short-circuit can never be falsy —
  it reads as dead defensive code. Removing it (`if (el.hasAttribute(KEY_ATTR))`)
  is almost certainly safe, but it is functional logic touching the event-routing
  hot path against exotic/non-standard nodes, so it sits outside a strictly
  behavior-neutral quality pass. Recommend dropping the redundant guard in a
  follow-up that the author reviews. No test currently exercises a node lacking
  `hasAttribute`, so it cannot be proven dead by the suite alone.

## Out of T1 scope (not this track — left untouched)

- `client/transport.js`, `client/transport-wasm.js`, `client/transport-ws.js`
  are foundation/transport-track files, not part of the `feat/client-render`
  diff. Not modified here.
- `tests/client/setup.js` line 15 uses single quotes for the HTML attribute
  `id='root'` *inside* a double-quoted JS string literal — that is HTML content,
  not a JS string delimiter, so it complies with the double-quote rule and was
  left as-is (escaping would only hurt readability).
