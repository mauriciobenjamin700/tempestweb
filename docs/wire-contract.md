# Contrato de fronteira

O **contrato de fronteira** (wire format) é o acordo entre o **Python** (o
reconciliador, vindo do core) e o **cliente JS** (que muta o DOM). Ele é o
**mesmo** nos três transportes — `pyodide.ffi` (Modo A), WebSocket e SSE (Modo B).
Só o envelope muda; nunca o shape dos dados. 🤝

!!! info "Esta página é o resumo didático"
    O documento canônico, pinado por golden fixtures **derivadas do core real**,
    vive junto ao código:
    [`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
    Qualquer agente que trabalhe no cliente ou nos transportes programa contra ele
    e contra as fixtures. Aqui damos a visão geral; o link tem cada campo.

## Os quatro cruzamentos

A tipagem "vaza" pela fronteira em quatro pontos — análogo ao request/response do
FastAPI:

<div class="grid cards" markdown>

-   __1. IR → cliente__

    ---

    A árvore de `Node` serializada e a lista de patches do `diff`.

-   __2. Evento → handler__

    ---

    O payload do click/input que sobe e é validado (Pydantic) antes de entrar no
    Python.

-   __3. Style → CSS__

    ---

    O objeto `Style` tipado que o cliente traduz para CSS.

-   __4. Chamada nativa__

    ---

    Web APIs expostas como awaitables tipados (`native_call`/`native_result`).

</div>

## 1. Node — a IR serializada

Cada nó da árvore tem o mesmo shape:

```json
{
  "type": "Column",
  "key": "label",
  "props": { "style": null },
  "children": []
}
```

- `type` — o nome do widget (`Column`, `Row`, `Text`, `Button`, `Container`, …).
- `key` — chave estável para reconciliação (pode ser `null`).
- `props` — props do widget, incluindo `"style"` (objeto `Style` ou `null`).
- `children` — lista de `Node`s filhos.

!!! warning "Handlers não atravessam como função"
    O core serializa uma **referência**; o evento volta com a `key` do widget. É
    o lado Python que resolve qual handler chamar — o cliente nunca executa lógica
    de app.

## 2. Os 5 patches

O reconciliador faz `diff(old, new)` e emite uma lista. `path` endereça o nó-alvo
por índices (`[]` = raiz, `[0]` = primeiro filho).

| Tipo | Distingue-se por | Semântica |
|---|---|---|
| **Update** | `set_props` | Aplica props e remove `unset_props`. |
| **Insert** | `node` + `index` | Insere um filho na posição. |
| **Remove** | só `index` | Remove o filho na posição. |
| **Reorder** | `order` | Reordena os filhos. |
| **Replace** | `node` sem `index` | Troca o nó inteiro. |

## 3. Style

`props.style` é um objeto `Style` (ou `null`). `Color` é `{r,g,b,a}` (r/g/b
0–255, a 0–1) → CSS `rgba(...)`. `Edge` é `{top,right,bottom,left}` em px.

```json
{
  "direction": "column",
  "gap": 8.0,
  "padding": { "top": 16, "right": 16, "bottom": 16, "left": 16 },
  "background": { "r": 255, "g": 255, "b": 255, "a": 1.0 },
  "color": { "r": 17, "g": 17, "b": 17, "a": 1.0 },
  "width": 320.0
}
```

!!! note "Style → CSS é quase identidade"
    O `Style` foi desenhado copiando o vocabulário do CSS, então a tradução é
    direta e vive no cliente (`client/style.js`) — um só tradutor para os dois
    modos.

## 4. Evento (cliente → Python)

```json
{ "type": "click", "key": "inc", "payload": {} }
```

O lado Python resolve a `key` → handler do nó na árvore atual, valida o `payload`
com Pydantic e invoca o handler (sync ou `async`).

## Enquadramento por transporte

O shape de Node/Patch/Evento **não muda** entre transportes; muda só o envelope:

=== "WASM (Modo A)"

    Chamada de função em-processo via `pyodide.ffi`. Python passa a lista de
    patches direto ao cliente; eventos voltam por callback. Sem rede, sem
    envelope.

=== "WebSocket (Modo B)"

    Cada mensagem WS é um JSON com `kind`:

    ```json
    { "kind": "patches", "data": [ /* Patch... */ ] }   // servidor → cliente
    { "kind": "event",   "data": { /* Evento */ } }      // cliente → servidor
    ```

=== "SSE (Modo B, B5)"

    O servidor responde `text/event-stream`. Cada tick é um evento SSE cujo
    `data:` é o JSON da **mesma** lista de patches. Eventos sobem por HTTP POST
    (corpo = `Evento`). Reconnect usa `Last-Event-ID`.

## A chamada nativa (Modo B — proxy)

O **4º cruzamento**. No Modo A uma capacidade `native/` chama a Web API direto no
browser. No Modo B ela é **proxiada** por um round-trip:

```json
// servidor → cliente: pedido de capacidade nativa
{ "kind": "native_call", "call_id": "c1", "capability": "geolocation.get", "args": {} }

// cliente → servidor: resultado tipado (ou erro)
{ "kind": "native_result", "call_id": "c1", "ok": true,  "value": { "lat": -23.5, "lon": -46.6 } }
{ "kind": "native_result", "call_id": "c1", "ok": false, "error": "PermissionDenied" }
```

- `call_id` correlaciona pedido ↔ resultado (várias chamadas podem estar em voo).
- `capability` é o nome estável (`geolocation.get`, `clipboard.read`, …).
- O lado Python expõe isso como **awaitable tipado** — ver [Capacidades](capabilities.md).

!!! tip "A API Python é idêntica nos dois modos"
    No Modo A o mesmo `await geolocation.get()` resolve em-processo; no Modo B ele
    dispara o round-trip `native_call`/`native_result`. Só o caminho muda — por
    isso a assinatura tipada mora no contrato, não no transporte.

## Recap

- O contrato é o **mesmo** nos três transportes; só o envelope difere.
- Quatro cruzamentos: **IR → cliente**, **Evento → handler**, **Style → CSS**,
  **chamada nativa**.
- Os shapes são fixados por golden fixtures derivadas do core real.

Para cada campo, leia o
[`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md)
canônico. Para ver o contrato em ação, faça o [Tutorial](tutorial/index.md). 🚀
