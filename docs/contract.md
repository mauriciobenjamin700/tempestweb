# Contrato de fronteira (wire format)

Este é o contrato entre o **Python** (reconciliador, vindo do core) e o **cliente
JS** (que muta o DOM). É o **mesmo** nos dois modos (WASM e servidor) — só o
transporte (`pyodide.ffi` vs WebSocket) muda. Pinado por golden fixtures em
[`tests/fixtures/`](../tests/fixtures/), **derivadas do core real** (não
inventadas). Qualquer agente que trabalhe no cliente JS ou nos transportes
programa contra este documento e essas fixtures.

## Node (IR serializada)

Uma árvore de `Node`. Cada nó:

```json
{
  "type": "Column",        // nome do widget: Column, Row, Text, Button, Container, ...
  "key": "label",          // chave estável p/ reconciliação (pode ser null)
  "props": { "...": "..." },  // props do widget, incl. "style" (objeto Style ou null)
  "children": [ /* Nodes */ ]
}
```

Fixture: [`node_initial.json`](../tests/fixtures/node_initial.json).

`props` varia por tipo de widget. Exemplos:

- `Text`: `{ "style": <Style|null>, "content": "Count: 0", ... }`
- `Button`: `{ "style": <Style|null>, "label": "+", "on_click": <handler-ref|null>, "focusable": ..., ... }`

> Handlers (`on_click`, etc.) **não** atravessam como função. O core serializa uma
> referência; o evento volta com a `key` do widget e o cliente NÃO precisa resolver
> o handler — quem resolve é o lado Python (ver Evento).

## Patches (5 tipos)

O reconciliador faz `diff(old, new)` e emite uma lista de patches. `path` é uma
lista de índices da raiz até o nó-alvo (`[]` = raiz, `[0]` = primeiro filho,
`[0,1]` = segundo filho do primeiro filho). Fixtures:
[`patches_all_kinds.json`](../tests/fixtures/patches_all_kinds.json).

| Tipo | Shape | Semântica |
|---|---|---|
| **Update** | `{ "path": [0], "set_props": {...}, "unset_props": [...] }` | No nó em `path`, aplica `set_props` e remove as chaves de `unset_props`. |
| **Insert** | `{ "path": [], "index": 1, "node": {Node} }` | No nó-pai em `path`, insere `node` na posição `index` (entre os filhos). |
| **Remove** | `{ "path": [], "index": 1 }` | No nó-pai em `path`, remove o filho na posição `index`. |
| **Reorder** | `{ "path": [], "order": [1, 0] }` | No nó-pai em `path`, reordena os filhos: novo filho `i` = antigo filho `order[i]`. |
| **Replace** | `{ "path": [0], "node": {Node} }` | Substitui o nó em `path` inteiro por `node` (tipo diferente, mesma posição). |

Como distinguir o tipo no cliente: pela presença das chaves
(`set_props`→Update, `node`+`index`→Insert, só `index`→Remove, `order`→Reorder,
`node` sem `index`→Replace). O W1 pode normalizar adicionando um campo `op`
explícito no transporte se preferir — mas o shape acima é o que o core emite.

## Style

`props.style` é um objeto `Style` (ou `null`). Campos relevantes para v1 (todos
opcionais/`null` quando ausentes). Fixture:
[`style_sample.json`](../tests/fixtures/style_sample.json).

```json
{
  "direction": "column",                 // FlexDirection: "row" | "column"
  "justify": null,                        // JustifyContent
  "align": null,                          // AlignItems
  "grow": null,                           // float -> flex-grow
  "gap": 8.0,                             // float (px) -> gap
  "padding": {"top":16,"right":16,"bottom":16,"left":16},  // Edge -> padding
  "margin": null,                         // Edge -> margin
  "border": null,                         // Border | SideBorder
  "radius": null,                         // float | Corners -> border-radius
  "background": {"r":255,"g":255,"b":255,"a":1.0},  // Color (rgba) | Gradient
  "color": {"r":17,"g":17,"b":17,"a":1.0},          // Color -> color
  "opacity": null, "shadow": null,
  "font_family": null, "font_size": null, "font_weight": null,
  "font_style": null, "text_align": null, "text_decoration": null,
  "letter_spacing": null, "line_height": null, "max_lines": null,
  "width": 320.0, "height": null, "min_width": null, "max_width": null,
  "min_height": null, "max_height": null, "aspect_ratio": null,
  "position": null, "top": null, "right": null, "bottom": null, "left": null,
  "transition": null
}
```

`Color` é `{r,g,b,a}` (r/g/b 0–255, a 0–1) → CSS `rgba(r,g,b,a)`. `Edge` é
`{top,right,bottom,left}` em px. `direction: "column"` mapeia a um container flex
com `flex-direction: column`.

**Referência de tradução `Style → CSS`:** o tempestroid já mapeia `Style` para QSS
(Qt) e Compose Modifier. O QSS é a linguagem mais próxima do CSS — leia
`../../tempestroid/tempestroid/renderers/qt/style_translator.py` como guia de
mapeamento campo-a-campo (padding, border, background, radius, tipografia). O
mapeamento `Style → CSS` deve ser **mais simples** que o QSS, pois CSS é o alvo
nativo do vocabulário.

## Evento (client → Python)

```json
{ "type": "click", "key": "inc", "payload": {} }
```

- `type`: `"click" | "input" | "change" | "submit" | ...`
- `key`: a `key` do widget que originou o evento.
- `payload`: dados do evento (ex.: `{"value": "texto"}` para `input`).

O lado Python resolve a `key` → handler do nó na árvore atual, valida o `payload`
(Pydantic) e invoca o handler. Sync ou `async`.

## Regra de coalescência

O core já coalesce múltiplos `set_state` do mesmo tick num único `diff`. O
transporte recebe **uma lista de patches por tick** — o cliente aplica a lista
inteira antes do próximo frame.
