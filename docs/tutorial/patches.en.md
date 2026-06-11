# 3. Patches on the wire

On the [previous page](state.md) we saw the cycle **event → state → rebuild →
patches**. Now let's open the box: what exactly the reconciler emits when the
count changes — and how the JS client applies it to the DOM. This is the **wire
contract**, identical in both modes. 🔌

## The tree becomes plain data

When `view()` runs, the core **serializes** the tree into JSON-able IR. Every
node always has the same shape:

```json
{
  "type": "Text",
  "key": "label",
  "props": { "content": "Count: 0", "style": null },
  "children": []
}
```

- `type` — the widget name (`Column`, `Row`, `Text`, `Button`, …).
- `key` — the stable identity (may be `null`).
- `props` — the widget props, including `style` (a `Style` object or `null`).
- `children` — the list of child nodes.

!!! info "Handlers do not cross the wire"
    `on_click` does **not** go as a function in the JSON. The core keeps the
    reference; the client only returns the widget's `key` when the user clicks,
    and the **Python side** resolves which handler to call. The client never runs
    app logic.

## The 5 patch types

The reconciler runs `diff(old_tree, new_tree)` and emits a **patch list**. Each
patch has a `path` — a list of indices from the root to the target node (`[]` =
root, `[0]` = first child, `[0, 1]` = second child of the first child).

| Type | Shape | Semantics |
|---|---|---|
| **Update** | `{ "path": [0], "set_props": {...}, "unset_props": [...] }` | On the node at `path`, apply `set_props` and remove `unset_props`. |
| **Insert** | `{ "path": [], "index": 1, "node": {Node} }` | On the parent at `path`, insert `node` at position `index`. |
| **Remove** | `{ "path": [], "index": 1 }` | On the parent at `path`, remove the child at position `index`. |
| **Reorder** | `{ "path": [], "order": [1, 0] }` | On the parent at `path`, reorder: new child `i` = old child `order[i]`. |
| **Replace** | `{ "path": [0], "node": {Node} }` | Replace the whole node at `path` (different type, same position). |

!!! note "How the client tells the type apart"
    By the presence of keys: `set_props` → Update, `node` + `index` → Insert, only
    `index` → Remove, `order` → Reorder, `node` without `index` → Replace. Full
    detail in the [wire contract](../wire-contract.md).

## The counter, in practice

Start with the count at `0`. The `Text` is the first child of the `Column`, so
its `path` is `[0]`. The user clicks `+`, `value` becomes `1`, the view runs
again and the only node that changed is the text. The diff is **minimal**:

```json
[
  {
    "path": [0],
    "set_props": { "content": "Count: 1" },
    "unset_props": []
  }
]
```

A single **Update**. The buttons did not change, so they produce no patch. This
is where `key="label"` does its job: it anchors the `Text` across rebuilds, and
the reconciler realizes it only needs to swap the `content` prop.

!!! check "Why this matters"
    The client does not recreate the whole DOM on every click — it applies a
    surgical patch. The text becomes `Count: 1` by changing a single
    `textContent`. Fast and flicker-free. ✨

## How the client applies it

The JS client (`client/dom.js`) walks the `path`, finds the target node and
applies the operation. In pseudo-code:

```js
// Resolve the target node by following the path indices
function resolve(root, path) {
  let node = root;
  for (const i of path) node = node.childNodes[i];
  return node;
}

// Apply an Update: set props, remove the ones that left
function applyUpdate(root, patch) {
  const el = resolve(root, patch.path);
  for (const [name, value] of Object.entries(patch.set_props)) {
    setProp(el, name, value); // content -> textContent, style -> CSS, ...
  }
  for (const name of patch.unset_props) {
    unsetProp(el, name);
  }
}
```

The same `applyUpdate` runs in Mode A and Mode B — the patch bytes are identical,
only the **transport** that delivers them differs.

??? note "Where the real patches are pinned (golden fixtures)"
    The shape above is not made up: it is **derived from the real core** and
    frozen into fixtures in
    [`tests/fixtures/`](https://github.com/mauriciobenjamin700/tempestweb/tree/main/tests/fixtures):

    - [`node_initial.json`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/tests/fixtures/node_initial.json) — the serialized IR.
    - [`patches_all_kinds.json`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/tests/fixtures/patches_all_kinds.json) — the 5 patch types.
    - [`style_sample.json`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/tests/fixtures/style_sample.json) — a `Style` object.

    The client is tested against these fixtures; changing the shape requires
    regenerating them from the core.

## Recap

- The tree becomes **JSON-able data**: `{type, key, props, children}`.
- The diff emits a **list of 5 patch types**, addressed by `path`.
- Changing the count produces **a single Update** on the `Text` anchored by its
  `key`.
- The client walks the `path` and applies the operation — **same code** in both
  modes.

Now the final question: how does the **same** `app.py` run in both modes without
changing a line? Let's [run both modes](modes.md). 🚀
