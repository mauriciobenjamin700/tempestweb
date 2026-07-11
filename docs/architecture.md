# Arquitetura

tempestweb é o reconciliador **renderer-agnostic** do tempestroid com um
**terceiro renderizador-folha** (DOM) e **três estratégias de execução**: dois
transportes de patch (FFI Pyodide e WebSocket/SSE) mais um **compilador** que
transcreve o app para JavaScript nativo (Modo C). Esta página dá a visão geral
didática; o documento canônico, mantido junto ao código, é
[`docs/arquitetura.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/arquitetura.md).

## A ideia central

```text
            Python tipado (view + state)        ← idêntico nos dois modos
                        │
                        ▼
        core: IR (Pydantic) ──diff──► patches    ← reusado do tempestroid
                        │
              ┌─────────┴──────────┐
        Modo A: transporte    Modo B: transporte
        FFI Pyodide           WebSocket / SSE
        (no browser)          (servidor → cliente)
              └─────────┬──────────┘
                        ▼
        cliente JS (puro): aplica patches no DOM
        + tradutor Style → CSS + captura de eventos    ← MESMO código nos dois modos
```

O **reconciliador** (Python) e o **cliente JS** são os mesmos nos dois modos. A
única coisa que muda é a **camada de transporte**.

## As quatro camadas

| Camada | O que faz | Onde vive |
|---|---|---|
| **Core** | IR, diff/patch, estado, estilo, widgets | pacote `tempest-core` (`import tempest_core`), extraído do tempestroid |
| **Renderizador-folha** | Aplica patches no DOM, traduz `Style → CSS`, captura eventos | `client/` — JavaScript puro |
| **Transporte** | Leva patches Python→JS e eventos JS→Python | `tempestweb/transports/{wasm,websocket}.py` + `client/transport-*.js` |
| **Runtime / host** | Hospeda o Python | Pyodide no browser (A) · FastAPI (B) |

A divergência entre os dois modos fica **trancada na camada de transporte**. Tudo
acima (o app Python) e tudo abaixo (o cliente JS que muta o DOM) é compartilhado.

!!! info "Por que o renderizador é o mesmo nos dois modos"
    Patches são **dados puros serializados**. O cliente JS só sabe consumir patch
    e mutar o DOM — não liga de onde o patch veio. No Modo A, o patch chega por
    uma chamada de função em-processo (`pyodide.ffi`); no Modo B, chega por uma
    mensagem WebSocket. O byte do patch é o mesmo. Por isso `client/dom.js` e
    `client/style.js` são escritos uma vez e servem os dois.

## A costura de transporte

A interface de transporte abstrai a diferença entre os modos. No cliente:

```js
// client/transport.js — contrato comum
// onPatches(callback): registra quem recebe listas de patches
// sendEvent(event):    envia um evento (click/input) de volta ao Python
```

E no lado Python:

```python
from typing import Protocol


class PatchTransport(Protocol):
    """Carries patches Python→client and events client→Python."""

    async def send_patches(self, patches: list[dict]) -> None: ...

    async def recv_event(self) -> dict: ...
```

`transports/wasm.py` implementa isso sobre `pyodide.ffi`;
`transports/websocket.py` sobre uma conexão WebSocket. Trocar de modo é trocar a
implementação — o `view()` do usuário não muda.

!!! info "Onde o Modo C entra"
    O **Modo C (transpile)** não usa um transporte: um compilador transcreve a
    **camada de app** (`view`/`state`/handlers) para JavaScript nativo no build,
    então o `diff` roda **em JS, no browser**. Mesmo assim o
    [renderizador-folha](transpile.md) é o **mesmo** `client/dom.js` / `style.js`
    dos Modos A/B — a fronteira que muda é *onde o `diff` roda*, não *como o
    patch é aplicado*. Por isso o Modo C herda o renderizador compartilhado sem
    reescrever nada.

## Style → CSS: o alvo mais fácil

No tempestroid, `Style → Compose` é a parte difícil, porque os vocabulários
divergem. Na web não há divergência: o `Style` do core **já foi desenhado
copiando o CSS** (flexbox, box model, tipografia). O tradutor `Style → CSS` é
quase identidade e vive no cliente JS — **um só tradutor** para os dois modos,
então não há como A e B discordarem na tradução de estilo.

## Onde a tipagem "vaza" (o contrato)

Análogo ao request/response do FastAPI, o Pydantic valida três cruzamentos na
fronteira Python↔cliente:

1. **IR → cliente** — a árvore/patches serializados.
2. **Eventos → handlers** — payloads do click/input validados antes de entrar no
   Python.
3. **Chamadas nativas** — wrappers tipados sobre Web APIs, expostos como
   awaitables.

O **schema é o mesmo** nos dois modos; só o meio de transporte difere.

??? note "Regra de ouro de execução (detalhe)"
    O Python roda sobre um **event loop asyncio**.

    - **Modo A:** o Pyodide integra o asyncio ao event loop do browser. Não há UI
      thread separada — trabalho pesado em Python **trava a aba**, então handlers
      devem ser async/leves.
    - **Modo B:** cada conexão WebSocket tem sua sessão asyncio no servidor.
      Patches saem pela conexão, eventos entram por ela; o estado vive no
      servidor, isolado por cliente.

## Conformância A ↔ B

Como o renderizador e o tradutor de estilo são únicos, o risco de divergência não
é de tradução, é de **transporte**: A e B não podem produzir DOM diferente para a
mesma `view()`. A suite de conformância fixa isso com golden snapshots, no CI — o
análogo web do Qt-vs-Compose do tempestroid.

## Recap

- Quatro camadas: **core**, **renderizador-folha**, **transporte**, **host**.
- Tudo acima e abaixo do transporte é **compartilhado**; só o transporte muda
  entre os modos.
- O risco real é de **transporte**, não de tradução — daí a suite de
  conformância.

Para mergulhar no detalhe completo, leia
[`docs/arquitetura.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/arquitetura.md)
e o [Plano de design](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
Para ver tudo isso na prática, vá ao [Tutorial](tutorial/index.md). 🚀
