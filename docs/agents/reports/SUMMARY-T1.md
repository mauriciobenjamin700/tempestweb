# SUMMARY — Track T1 (Pure-JS client renderer)

Branch: `feat/client-render`

## What this track delivers

The full pure-JavaScript client renderer — the leaf that mutates the real DOM —
shared identically by both execution modes (A/WASM and B/server). No TypeScript,
no framework, no build step. ES modules, double quotes, JSDoc as the type surface.
Everything programmed against `docs/contract.md` and the golden fixtures in
`tests/fixtures/` (derived from the real core), verified with `node --test` + jsdom.

### `client/dom.js` — DOM build + patch application (W1)
- `buildElement(node)`: recursively builds a DOM subtree from a serialized IR
  `Node`. Maps widget `type` -> HTML tag (`Column/Row/Container/Stack` -> `div`,
  `Text` -> `span`, `Button` -> `button`; unknown types fall back to `div`).
  Stamps `data-tw-key` (when keyed) and `data-tw-type` on every element so event
  delegation can recover the originating widget key. `content` (Text) and `label`
  (Button) become text; `style` is translated via `styleToCss`.
- `applyPatches(root, patches)`: applies a coalesced tick batch in array order.
- `applyPatch` classifies each patch **by key presence** (per the contract — no
  explicit `op` field): `set_props`/`unset_props` -> Update, `order` -> Reorder,
  `node`+`index` -> Insert, `node` alone -> Replace, `index` alone -> Remove.
  Unrecognized shapes throw `TypeError`.
- `path` is resolved as child indices from the target root (`[]` = root).
- Reorder snapshots children first so `order` indices are pre-reorder positions.
- Exports: `buildElement`, `applyPatches`, `KEY_ATTR` (`data-tw-key`), `TYPE_ATTR`.

### `client/style.js` — Style -> CSS translator (W2)
- `styleToCss(style)`: `null`/empty -> `""`; otherwise a `"; "`-joined declaration
  body. Covers flex (`direction`->`display:flex`+`flex-direction`, `justify`,
  `align`, `align_self`, `grow`, `gap`, `flex_wrap`; `start`/`end`->`flex-start`/
  `flex-end`), box model (`padding`/`margin` via Edge four-value px shorthand),
  `border` (uniform `Npx solid rgba(...)`, per-side SideBorder, null color ->
  `currentColor`), `radius` (uniform float or per-corner Corners), paint
  (`background` Color->`rgba()` or Gradient->`linear-gradient(...)`, `color`,
  `opacity`), typography (`font_family/size/weight/style`, `text_align`,
  `text_decoration`, `letter_spacing`, `line_height`), and dimensions
  (`width/height/min_*/max_*` in px, unitless `aspect_ratio`).
- `Color {r,g,b,a}` -> `rgba(r, g, b, a)`; `Edge {top,right,bottom,left}` -> px.
- Field order is fixed (flex -> box -> paint -> typography -> dimensions) so output
  is stable run-to-run. Absent/null fields are skipped (browser default applies).
- Exports: `styleToCss`, `colorToRgba`.

### `client/events.js` — delegated event capture (W3)
- `bindEvents(root, transport)`: one delegated listener per captured DOM event
  type (`click`/`input`/`change`/`submit`) on `root`. Walks from `event.target`
  up to the nearest `data-tw-key` ancestor (clicks landing on text inside a keyed
  Button still resolve to the Button's key). Calls
  `transport.sendEvent({ type, key, payload })`. `input`/`change` carry
  `{ value }`; other types carry `{}`. Unkeyed events are ignored. Returns an
  unbind function that detaches every listener.
- Delegation means listeners survive patch churn without rebinding.

### `client/tempestweb.js` — mount orchestrator (W3)
- `mount(root, transport, initialNode)`: builds the initial tree, appends it to
  `root`, binds delegated events, and registers `transport.onPatches` to apply
  each batch to the mounted tree (patch `path` is rooted at the mounted tree, not
  the wrapper). Returns `{ root, unmount() }`; `unmount` unbinds events and
  removes the tree.

### `client/transport.js` — the seam contract
- JSDoc typedefs only (`Patch`, `Node`, `TWEvent`, `Transport`). The two mode
  impls (`transport-wasm.js`, `transport-ws.js`) are pre-existing stubs from the
  foundation commit and belong to the transport tracks, not T1.

## Tests (tests/client/, node --test + jsdom)
36 tests, all green:
- `dom.test.js`: all 5 patch kinds applied in sequence yield the expected DOM;
  Update with `unset_props`; nested path resolution; throw on unknown shape.
- `style.test.js`: `style_sample.json` -> expected CSS; null/empty -> `""`;
  colorToRgba; flex start/end mapping; gap/grow/wrap/align_self; Edge shorthands;
  uniform + per-side border (incl. currentColor fallback); uniform + per-corner
  radius; gradient background; typography; dimensions; opacity.
- `events.test.js`: Button click -> `sendEvent` with the right key; per-button key;
  unkeyed click sends nothing; click bubbling from inside a keyed widget uses the
  keyed ancestor; input/change carry `value`; unbind detaches listeners.
- `mount.test.js`: builds initial tree under root; applies pushed patches; wires
  events end-to-end; unmount tears down.
- `smoke.test.js`: fixtures load + jsdom works.

## Verification
```
node --test "tests/client/**/*.test.js"   # 36 pass / 0 fail
```

## What is stubbed / out of scope for T1
- `transport-wasm.js` and `transport-ws.js` are foundation stubs — the real
  per-transport framing (WS `{kind,data}` envelope, SSE, `native_call`/
  `native_result`) belongs to the transport tracks (A/B). T1 only depends on the
  `Transport` Protocol shape and is verified against a mock transport.
- Style fields with no v1 CSS analogue are intentionally not emitted: `shadow`,
  `transition`, `position`/`top`/`right`/`bottom`/`left` insets, `stack_align`,
  `max_lines`, `text_overflow`, `text_scale`, `font_asset`. Add them when a fixture
  and a renderer consumer require them.

## What a human must verify by hand
- **Real-browser rendering.** All logic is verified under jsdom, which does not
  do layout/paint. A live-browser pass (mount a real app, confirm flexbox/colors/
  spacing render and a click round-trips) is still recommended once a transport
  track lands — jsdom proves the DOM mutations and CSS strings, not pixels.

## Suggested merge order
1. **T1 (this branch) first** — it is self-contained (depends only on the
   `Transport` typedef + fixtures) and is what the transport tracks render through.
2. Then the transport tracks (WASM Mode A, WS/SSE Mode B), which implement the
   `Transport` Protocol and plug into `mount()` unchanged.
3. Then server/devserver/native tracks that drive the transports.
