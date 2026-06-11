# 3. Patches na rede

Na [página anterior](state.md) vimos o ciclo **evento → estado → rebuild →
patches**. Agora vamos abrir a caixa: o que exatamente o reconciliador emite
quando a contagem muda — e como o cliente JS aplica isso no DOM. Esse é o
**contrato de fronteira**, idêntico nos dois modos. 🔌

## A árvore vira dados puros

Quando `view()` roda, o core **serializa** a árvore numa IR JSON-able. Cada nó
tem sempre o mesmo shape:

```json
{
  "type": "Text",
  "key": "label",
  "props": { "content": "Count: 0", "style": null },
  "children": []
}
```

- `type` — o nome do widget (`Column`, `Row`, `Text`, `Button`, …).
- `key` — a identidade estável (pode ser `null`).
- `props` — as props do widget, incluindo `style` (objeto `Style` ou `null`).
- `children` — a lista de nós filhos.

!!! info "Handlers não atravessam a fronteira"
    `on_click` **não** vai como função no JSON. O core guarda a referência; o
    cliente só devolve a `key` do widget quando o usuário clica, e o **lado
    Python** resolve qual handler chamar. O cliente nunca executa lógica de app.

## Os 5 tipos de patch

O reconciliador faz `diff(árvore_antiga, árvore_nova)` e emite uma **lista de
patches**. Cada patch tem um `path` — uma lista de índices da raiz até o nó-alvo
(`[]` = raiz, `[0]` = primeiro filho, `[0, 1]` = segundo filho do primeiro
filho).

| Tipo | Shape | Semântica |
|---|---|---|
| **Update** | `{ "path": [0], "set_props": {...}, "unset_props": [...] }` | No nó em `path`, aplica `set_props` e remove `unset_props`. |
| **Insert** | `{ "path": [], "index": 1, "node": {Node} }` | No pai em `path`, insere `node` na posição `index`. |
| **Remove** | `{ "path": [], "index": 1 }` | No pai em `path`, remove o filho na posição `index`. |
| **Reorder** | `{ "path": [], "order": [1, 0] }` | No pai em `path`, reordena: novo filho `i` = antigo filho `order[i]`. |
| **Replace** | `{ "path": [0], "node": {Node} }` | Substitui o nó em `path` inteiro (tipo diferente, mesma posição). |

!!! note "Como o cliente distingue o tipo"
    Pela presença das chaves: `set_props` → Update, `node` + `index` → Insert, só
    `index` → Remove, `order` → Reorder, `node` sem `index` → Replace. O detalhe
    completo está no [contrato de fronteira](../wire-contract.md).

## O counter, na prática

Comece com a contagem em `0`. O `Text` é o primeiro filho da `Column`, então seu
`path` é `[0]`. O usuário clica no `+`, `value` vira `1`, a view roda de novo e o
único nó que mudou é o texto. O diff é **mínimo**:

```json
[
  {
    "path": [0],
    "set_props": { "content": "Count: 1" },
    "unset_props": []
  }
]
```

Um único **Update**. Os botões não mudaram, então não geram patch. É aqui que a
`key="label"` faz seu trabalho: ela ancora o `Text` entre rebuilds, e o
reconciliador percebe que basta trocar a prop `content`.

!!! check "Por que isso importa"
    O cliente não recria o DOM inteiro a cada clique — ele aplica um patch
    cirúrgico. O texto vira `Count: 1` mudando um único `textContent`. Rápido e
    sem flicker. ✨

## Como o cliente aplica

O cliente JS (`client/dom.js`) percorre o `path`, encontra o nó-alvo e aplica a
operação. Em pseudo-código:

```js
// Resolve o nó-alvo seguindo os índices do path
function resolve(root, path) {
  let node = root;
  for (const i of path) node = node.childNodes[i];
  return node;
}

// Aplica um Update: troca props, remove as que saíram
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

O mesmo `applyUpdate` roda no Modo A e no Modo B — o byte do patch é idêntico,
só o **meio de transporte** que o entrega difere.

??? note "Onde os patches reais são fixados (golden fixtures)"
    O shape acima não é inventado: ele é **derivado do core real** e congelado em
    fixtures em
    [`tests/fixtures/`](https://github.com/mauriciobenjamin700/tempestweb/tree/main/tests/fixtures):

    - [`node_initial.json`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/tests/fixtures/node_initial.json) — a IR serializada.
    - [`patches_all_kinds.json`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/tests/fixtures/patches_all_kinds.json) — os 5 tipos de patch.
    - [`style_sample.json`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/tests/fixtures/style_sample.json) — um objeto `Style`.

    O cliente é testado contra essas fixtures; mudar o shape exige regenerá-las a
    partir do core.

## Recap

- A árvore vira **dados JSON-able**: `{type, key, props, children}`.
- O diff emite uma **lista de 5 tipos de patch**, endereçados por `path`.
- Mudar a contagem gera **um único Update** no `Text` ancorado pela `key`.
- O cliente percorre o `path` e aplica a operação — **mesmo código** nos dois
  modos.

Agora a pergunta final: como o **mesmo** `app.py` roda nos dois modos sem mudar
uma linha? Vamos [rodar os dois modos](modes.md). 🚀
