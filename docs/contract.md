# Contrato de fronteira (wire format)

Este é o contrato entre o **Python** (reconciliador, vindo do core) e o **cliente
JS** (que muta o DOM). É o **mesmo** nos três transportes (`pyodide.ffi` no Modo A;
WebSocket ou SSE no Modo B) — só o meio de transporte muda, nunca o shape dos
dados. Pinado por golden fixtures em
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

## Enquadramento por transporte (o payload é o mesmo)

O shape de Node/Patch/Evento acima **não muda** entre transportes; muda só o
envelope:

- **WASM (Modo A):** chamada de função em-processo via `pyodide.ffi`. Python passa
  a lista de patches (já JSON-able) direto ao cliente; eventos voltam por callback.
- **WebSocket (Modo B):** cada mensagem WS é um JSON `{ "kind": "patches", "data":
  [<Patch>...] }` (servidor→cliente) ou `{ "kind": "event", "data": <Evento> }`
  (cliente→servidor). Bidirecional no mesmo canal.
- **SSE (Modo B, B5):** o servidor responde `text/event-stream`. Cada tick é um
  evento SSE cujo `data:` é o JSON da **mesma** lista de patches. Heartbeat: evento
  nomeado `ping` em intervalo fixo. Como SSE é uni-direcional, os **eventos sobem
  por HTTP POST** (corpo = `<Evento>`), correlacionados à sessão pela URL. Reconnect
  usa `Last-Event-ID` para retomar do último tick.

## Chamada nativa (capacidade `native/`, Modo B — proxy)

O **4º cruzamento** da fronteira (além de IR→cliente, Evento→handler e Style). No
**Modo A** uma capacidade `native/` chama a Web API direto no browser, sem rede —
não há wire format. No **Modo B** a capacidade é **proxiada por um round-trip**: o
Python no servidor "pede" e o cliente executa a Web API. Duas mensagens novas no
transporte (WS ou SSE+POST):

```json
// servidor → cliente: pedido de capacidade nativa
{ "kind": "native_call", "call_id": "c1", "capability": "geolocation.get", "args": {} }

// cliente → servidor: resultado tipado (ou erro)
{ "kind": "native_result", "call_id": "c1", "ok": true,  "value": { "lat": -23.5, "lon": -46.6 } }
{ "kind": "native_result", "call_id": "c1", "ok": false, "error": "PermissionDenied" }
```

- `call_id` correlaciona pedido↔resultado (várias chamadas podem estar em voo).
- `capability` é o nome estável (`geolocation.get`, `clipboard.read`,
  `camera.capture`, …). `args`/`value` são **JSON-able**; binários (foto) vão como
  base64 ou referência de blob.
- O lado Python expõe isso como um **awaitable tipado** (`await geolocation.get()`):
  manda `native_call`, suspende a task até o `native_result` casar o `call_id`,
  valida o `value` com Pydantic e resolve. Erro vira exceção tipada.
- `notifications.subscribe` (WebPush, P3) e `storage.*` (IndexedDB, P2) seguem o
  mesmo envelope.

> No Modo A o mesmo awaitable Python resolve em-processo (sem `native_call`/
> `native_result`) — a **API Python é idêntica**, só o caminho muda. É a razão de a
> assinatura tipada morar no contrato, não no transporte.

## Navegação ↔ URL (deep links + back/forward)

O browser dona a **URL**; o app Python dona a **pilha de navegação**. As duas
pontas se sincronizam por mensagens nos dois sentidos:

```json
// cliente → servidor: a URL mudou (load, popstate). Reseta a pilha p/ a rota.
{ "type": "navigate", "key": "", "payload": { "path": "/details" } }

// servidor → cliente: o app navegou imperativamente (app.push/pop/reset).
{ "kind": "navigate", "path": "/details" }
```

- **URL → view:** no load e em cada `popstate` (voltar/avançar), o cliente reporta
  `location.pathname` como um **evento** `navigate` (`key` vazio). O runtime o
  trata antes da resolução de handler (`apply_navigate` → `routes_from_path`),
  resetando a pilha de navegação, então o `view` re-renderiza a tela linkada.
- **view → URL:** quando um handler navega (`app.push`/`pop`/`reset`), o topo da
  rota muda; o servidor emite o envelope `navigate` e o cliente faz
  `history.pushState` (no-op se a URL já bate — evita entrada duplicada logo após
  um round-trip URL→view). `pushState` não dispara `popstate`, então não há eco.

> No Modo A não há envelope: o `WasmRuntime` chama `history.pushState` direto via
> `pyodide.ffi` (callback `on_navigate`). A **semântica é idêntica** nos dois modos
> — só o transporte do sentido view→URL difere (envelope no B, callback no A).
