// diff.js — reconcile two IR node trees into a patch list (Mode C, native JS).
//
// A faithful port of tempest_core.core.reconciler.diff (the Python core). Same
// data-in / patches-out contract, so it is locked against the same golden
// fixtures (tests/fixtures/transpile_diff_cases.json) as the Python side.
//
// Diffing strategy (v1), mirroring the core:
//   - Same position, same (type, key)  -> recurse, emitting an Update for changed
//     props.
//   - Differing type or key at a position -> Replace the subtree.
//   - Child lists diff positionally by default (Insert/Remove at the tail).
//   - When BOTH child lists are fully keyed with unique keys, a keyed diff runs:
//     removed keys -> Remove (descending), survivors realigned with one Reorder,
//     added keys -> Insert (ascending final index), matched keys recurse.
//
// Patch shapes (distinguished by key presence, see client/dom.js / transport.js):
//   Update  { path, set_props, unset_props }
//   Insert  { path, index, node }
//   Remove  { path, index }
//   Reorder { path, order }
//   Replace { path, node }

/**
 * @typedef {import("../transport.js").Node} Node
 * @typedef {import("../transport.js").Patch} Patch
 */

/**
 * Structural (deep) equality for JSON-able prop values.
 *
 * Mirrors Python's `!=` on dicts/lists/scalars: objects compare by their own
 * enumerable keys, arrays element-wise, scalars by `===`. Only compares the
 * JSON-able wire data (props carry no functions — handlers are serialized as
 * `null`; see widgets.js), so reference identity never leaks into the diff.
 *
 * @param {*} a  The left value.
 * @param {*} b  The right value.
 * @returns {boolean}  Whether the two values are deeply equal.
 */
function deepEqual(a, b) {
  if (a === b) {
    return true;
  }
  if (a === null || b === null || typeof a !== "object" || typeof b !== "object") {
    return false;
  }
  const aArray = Array.isArray(a);
  if (aArray !== Array.isArray(b)) {
    return false;
  }
  if (aArray) {
    if (a.length !== b.length) {
      return false;
    }
    for (let i = 0; i < a.length; i += 1) {
      if (!deepEqual(a[i], b[i])) {
        return false;
      }
    }
    return true;
  }
  const aKeys = Object.keys(a);
  const bKeys = Object.keys(b);
  if (aKeys.length !== bKeys.length) {
    return false;
  }
  for (const key of aKeys) {
    if (!Object.prototype.hasOwnProperty.call(b, key) || !deepEqual(a[key], b[key])) {
      return false;
    }
  }
  return true;
}

/**
 * Compute the prop changes between two prop maps.
 *
 * @param {Object<string, *>} oldProps  The old props.
 * @param {Object<string, *>} newProps  The new props.
 * @returns {{set_props: Object<string, *>, unset_props: string[]}}
 *          `set_props`: props to add/overwrite; `unset_props`: removed prop names.
 */
function diffProps(oldProps, newProps) {
  /** @type {Object<string, *>} */
  const setProps = {};
  for (const key of Object.keys(newProps)) {
    if (
      !Object.prototype.hasOwnProperty.call(oldProps, key) ||
      !deepEqual(oldProps[key], newProps[key])
    ) {
      setProps[key] = newProps[key];
    }
  }
  const unsetProps = Object.keys(oldProps).filter(
    (key) => !Object.prototype.hasOwnProperty.call(newProps, key),
  );
  return { set_props: setProps, unset_props: unsetProps };
}

/**
 * Report whether every node carries a key and all keys are unique.
 * @param {Node[]} nodes  The child nodes to inspect.
 * @returns {boolean}     `true` when no key is null and no key repeats.
 */
function fullyKeyed(nodes) {
  const keys = nodes.map((node) => node.key);
  if (keys.includes(null) || keys.includes(undefined)) {
    return false;
  }
  return new Set(keys).size === keys.length;
}

/**
 * Reconcile one node against another at `path`, appending patches.
 * @param {Node} oldNode  The old node at this position.
 * @param {Node} newNode  The new node at this position.
 * @param {number[]} path  The address of this node ([] = root).
 * @param {Patch[]} patches  The accumulator to append patches to.
 * @returns {void}
 */
function reconcile(oldNode, newNode, path, patches) {
  if (oldNode.type !== newNode.type || (oldNode.key ?? null) !== (newNode.key ?? null)) {
    patches.push({ path, node: newNode });
    return;
  }

  const { set_props, unset_props } = diffProps(oldNode.props ?? {}, newNode.props ?? {});
  if (Object.keys(set_props).length > 0 || unset_props.length > 0) {
    patches.push({ path, set_props, unset_props });
  }

  reconcileChildren(oldNode.children ?? [], newNode.children ?? [], path, patches);
}

/**
 * Reconcile two child lists under `path`.
 * @param {Node[]} oldChildren  The old children.
 * @param {Node[]} newChildren  The new children.
 * @param {number[]} path       The address of the parent node.
 * @param {Patch[]} patches     The accumulator to append patches to.
 * @returns {void}
 */
function reconcileChildren(oldChildren, newChildren, path, patches) {
  if (
    oldChildren.length > 0 &&
    newChildren.length > 0 &&
    fullyKeyed(oldChildren) &&
    fullyKeyed(newChildren)
  ) {
    reconcileKeyed(oldChildren, newChildren, path, patches);
    return;
  }

  const common = Math.min(oldChildren.length, newChildren.length);
  for (let index = 0; index < common; index += 1) {
    reconcile(oldChildren[index], newChildren[index], [...path, index], patches);
  }
  for (let index = oldChildren.length - 1; index >= common; index -= 1) {
    patches.push({ path, index });
  }
  for (let index = common; index < newChildren.length; index += 1) {
    patches.push({ path, index, node: newChildren[index] });
  }
}

/**
 * Diff two fully-keyed child lists into a minimal patch sequence.
 *
 * Emits, in order: Remove for keys gone from `new` (descending index), a single
 * Reorder realigning the survivors to their new relative order, Insert for keys
 * new to the list (ascending final index), then recurses each matched key at its
 * final index. Every index is valid against the live child list at the moment its
 * patch applies (see the core reconciler docstring).
 *
 * @param {Node[]} oldChildren  The old children (fully keyed, unique).
 * @param {Node[]} newChildren  The new children (fully keyed, unique).
 * @param {number[]} path       The address of the parent node.
 * @param {Patch[]} patches     The accumulator to append patches to.
 * @returns {void}
 */
function reconcileKeyed(oldChildren, newChildren, path, patches) {
  const newKeys = new Set(newChildren.map((node) => node.key));
  const oldKeys = new Set(oldChildren.map((node) => node.key));

  // 1. Remove keys gone from `new`, descending so lower indices stay valid.
  for (let index = oldChildren.length - 1; index >= 0; index -= 1) {
    if (!newKeys.has(oldChildren[index].key)) {
      patches.push({ path, index });
    }
  }

  // 2. Realign the survivors (old order) to their new relative order.
  /** @type {Map<?string, number>} */
  const survivorIndex = new Map();
  let seen = 0;
  for (const node of oldChildren) {
    if (newKeys.has(node.key)) {
      survivorIndex.set(node.key, seen);
      seen += 1;
    }
  }
  const order = newChildren
    .filter((node) => oldKeys.has(node.key))
    .map((node) => survivorIndex.get(node.key));
  if (!isIdentity(order)) {
    patches.push({ path, order });
  }

  // 3. Insert keys new to the list at their final indices, ascending.
  newChildren.forEach((node, index) => {
    if (!oldKeys.has(node.key)) {
      patches.push({ path, index, node });
    }
  });

  // 4. Recurse matched keys at their final (new) indices.
  /** @type {Map<?string, Node>} */
  const oldByKey = new Map(oldChildren.map((node) => [node.key, node]));
  newChildren.forEach((node, index) => {
    if (oldKeys.has(node.key)) {
      reconcile(oldByKey.get(node.key), node, [...path, index], patches);
    }
  });
}

/**
 * Whether `order` is the identity permutation `[0, 1, 2, ...]`.
 * @param {number[]} order  The permutation.
 * @returns {boolean}
 */
function isIdentity(order) {
  for (let i = 0; i < order.length; i += 1) {
    if (order[i] !== i) {
      return false;
    }
  }
  return true;
}

/**
 * Diff two IR node trees into an ordered list of patches.
 *
 * Patches are ordered so a renderer can apply them sequentially: a node's own
 * update/reorder precedes its descendants' patches, and within a child list
 * removals run tail-first before insertions. Empty when the trees are identical.
 *
 * @param {Node} before  The previously rendered tree.
 * @param {Node} after   The freshly built tree.
 * @returns {Patch[]}    The patches that transform `before` into `after`.
 */
export function diff(before, after) {
  /** @type {Patch[]} */
  const patches = [];
  reconcile(before, after, [], patches);
  return patches;
}
