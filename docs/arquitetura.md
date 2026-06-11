# Arquitetura

tempestweb é o irmão web do [tempestroid](../../tempestroid): a mesma ideia de
**uma árvore, múltiplos renderizadores**, com um renderizador-folha para o **DOM**
e **dois transportes** de patch (FFI Pyodide e WebSocket) que dão origem aos dois
modos de execução.

## A ideia central

```
            Python tipado (view + state)        ← idêntico nos dois modos
                        │
                        ▼
        tempest-core: IR (Pydantic) ──diff──► patches    ← reusado do tempestroid
                        │
              ┌─────────┴──────────┐
        Modo A: transporte    Modo B: transporte
        FFI Pyodide           WebSocket
        (no browser)          (servidor → cliente)
              └─────────┬──────────┘
                        ▼
        cliente JS (puro): aplica patches no DOM
        + tradutor Style → CSS + captura de eventos    ← MESMO código nos dois modos
```

O **reconciliador** (Python, vindo do `tempest-core`) e o **cliente JS** são os
mesmos nos dois modos. A única coisa que muda é a **camada de transporte**.

## As quatro camadas

| Camada | O que faz | Onde vive |
|---|---|---|
| **Core** | IR, diff/patch, estado, estilo, widgets | `tempest-core` (pacote PyPI extraído do tempestroid) |
| **Renderizador-folha** | Aplica patches no DOM, traduz `Style → CSS`, captura eventos | `client/` — JavaScript puro |
| **Transporte** | Leva patches Python→JS e eventos JS→Python | `tempestweb/transports/{wasm,websocket}.py` + `client/transport-*.js` |
| **Runtime / host** | Hospeda o Python | Pyodide no browser (A) · FastAPI + tempest-fastapi-sdk (B) |

A divergência entre os dois modos fica **trancada na camada de transporte**. Tudo
acima (o app Python) e tudo abaixo (o cliente JS que muta o DOM) é compartilhado.

## Por que o renderizador é o mesmo nos dois modos

Patches são **dados puros serializados**. O cliente JS só sabe consumir patch e
mutar o DOM — não liga de onde o patch veio. No Modo A, o patch chega por uma
chamada de função em-processo (`pyodide.ffi`); no Modo B, chega por uma mensagem
WebSocket. O bytes do patch é o mesmo. Por isso `client/dom.js` e `client/style.js`
são escritos uma vez e servem os dois.

A interface de transporte abstrai a diferença:

```js
// client/transport.js — contrato comum
// onPatches(callback): registra quem recebe listas de patches
// sendEvent(event):    envia um evento (click/input) de volta ao Python
```

```python
# tempestweb/transports/base.py — lado Python
from typing import Protocol

class PatchTransport(Protocol):
    """Carries patches Python→client and events client→Python."""

    async def send_patches(self, patches: list[dict]) -> None: ...
    async def recv_event(self) -> dict: ...
```

`transports/wasm.py` implementa isso sobre `pyodide.ffi`; `transports/websocket.py`
sobre uma conexão WebSocket. Trocar de modo é trocar a implementação — o `view()`
do usuário não muda.

## Style → CSS: o alvo mais fácil

No tempestroid, `Style → Compose` é a parte difícil, porque os vocabulários do
Compose e do CSS divergem. Na web não há divergência: o `Style` do `tempest-core`
**já foi desenhado copiando o CSS** (flexbox, box model, tipografia). O tradutor
`Style → CSS` é quase identidade e vive no cliente JS — **um só tradutor** para os
dois modos, então não há como A e B discordarem na tradução de estilo.

## Onde a tipagem "vaza" (o contrato)

Análogo ao request/response do FastAPI, o Pydantic valida três cruzamentos na
fronteira Python↔cliente:

1. **IR → cliente** — a árvore/patches serializados.
2. **Eventos → handlers** — payloads do click/input validados antes de entrar no
   Python.
3. **Chamadas nativas** — wrappers tipados sobre Web APIs, expostos como awaitables.

O **schema é o mesmo** nos dois modos; só o meio de transporte difere (FFI
em-processo vs WebSocket na rede).

## Regra de ouro de execução

O Python roda sobre um **event loop asyncio**.

- **Modo A:** o Pyodide integra o asyncio ao event loop do browser. Não há UI
  thread separada — trabalho pesado em Python **trava a aba**, então handlers devem
  ser async/leves e ceder o controle.
- **Modo B:** cada conexão WebSocket tem sua sessão asyncio no servidor. Patches
  saem pela conexão, eventos entram por ela; o estado vive no servidor, isolado por
  cliente.

## Diferenças que o desenvolvedor percebe

A maior parte do código é idêntica, mas duas coisas vazam para o app:

- **Latência e localidade dos handlers.** No Modo A o handler roda local e
  síncrono-ish; no Modo B há um round-trip de rede por interação e o estado é
  remoto. A regra async-first (handler → estado → rebuild coalescido) absorve isso,
  mas é bom saber.
- **`native/` (capacidades).** É onde os modos mais divergem. No Modo A tudo é Web
  API no browser. No Modo B, decide-se o que roda no servidor (DB, push) e o que é
  sempre no cliente (camera, geolocation) — estes últimos proxiados por um
  round-trip WebSocket.

## Conformância A ↔ B

Como o renderizador e o tradutor de estilo são únicos, o risco de divergência não é
de tradução, é de **transporte**: A e B não podem produzir DOM diferente para a
mesma `view()`. A suite de conformância (Trilho D) fixa isso com golden snapshots,
no CI — o análogo web do Qt-vs-Compose do tempestroid.
