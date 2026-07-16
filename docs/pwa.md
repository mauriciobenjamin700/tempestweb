# PWA e offline

!!! abstract "O que você vai aprender"
    Como transformar seu app num **PWA instalável e offline** — service worker,
    fila de mutações durável e **WebPush ponta a ponta** — com o mínimo de código.

A camada **PWA / offline-first / WebPush** (Trilho P) torna seu app **instalável**
e capaz de rodar **sem rede**. Ela é mais turnkey no **[Modo C (transpile)](transpile.md)**:
como o bundle é 100% estático, o `build --mode transpile` já emite a PWA inteira
sozinho. 📱

!!! success "PWA de fábrica no Modo C"
    Comece uma PWA em um comando:

    ```bash
    tempestweb new meuapp --template pwa
    ```

    Isso gera um projeto Modo C já configurado (`mode = "transpile"` + bloco
    `[pwa]`) com um contador e um botão **Install**. Um `tempestweb build --mode
    transpile` emite o manifest, os ícones, o `sw.js` (service worker cache-first)
    e o `register.js` — sem você escrever uma linha de plumbing. 🚀

## As quatro peças

<div class="grid cards" markdown>

-   :material-cellphone-arrow-down: __Instalável (P0)__

    ---

    Manifest + ícones + prompt de instalação. O app entra na tela inicial como um
    nativo.

-   :material-sync: __Service worker (P1)__

    ---

    Precache do app-shell → **offline após o 1º load** + update lifecycle ("nova
    versão, recarregar").

-   :material-database: __Offline-first (P2)__

    ---

    Fila de mutações durável no IndexedDB + replay no reconnect (Background Sync).

-   :material-bell-ring: __WebPush (P3)__

    ---

    Subscribe no browser (`native.notifications`); envio via `webpush_router`
    (VAPID) no servidor.

</div>

## P0 — App instalável

O prompt de instalação é exposto ao Python pela capacidade
[`native.install`](capabilities.md). O controlador já suprime o mini-infobar frio
do browser e guarda o evento `beforeinstallprompt`, então você mostra um botão
"Instalar" no momento certo:

```python
from tempestweb import native


async def maybe_show_install_button() -> bool:
    """Return whether an Install button should be shown."""
    state = await native.install.state()   # InstallState(can_install, installed)
    return state.can_install and not state.installed


async def on_install_tap() -> None:
    """Fire the native install prompt from a button handler."""
    outcome = await native.install.prompt()   # "accepted" | "dismissed" | "unavailable"
```

!!! tip "Chame o prompt depois de um gesto do usuário"
    Os browsers só permitem `install.prompt()` a partir de um gesto real (clique).
    Renderize o botão quando `can_install` for verdadeiro e dispare o prompt no
    `on_click`.

## P1 — Service worker: offline após o 1º load

No Modo C, o `sw.js` gerado **pré-cacheia o bundle estático inteiro** —
`index.html`, o cliente compartilhado, o seu `app.gen.js`, os ícones e o manifest.
Depois da primeira carga, o app abre e roda **sem rede**.

!!! check "Offline de verdade ✅"
    Com o servidor HTTP **desligado**, recarregar a página ainda **renderiza o
    app** e a navegação continua funcionando — verificado ao vivo no Playwright.
    Como o Modo C é um bundle estático sem Python, nada depende do servidor depois
    do primeiro fetch.

!!! warning "Teste offline com `build`/`run`, não com `dev`"
    O `tempestweb dev` **não registra o service worker** de propósito (ele injeta um
    *kill-switch* para você nunca ver bundle cacheado velho — veja
    [Usando a CLI](cli.md)). Ou seja, o comportamento offline só existe no artefato
    de produção: teste-o com `tempestweb build --mode transpile` (e sirva o `dist/`)
    ou com `tempestweb run --mode transpile`.

!!! tip "Prompt de atualização (automático)"
    Quando você publica uma versão nova, o service worker antigo continua no ar
    até a aba fechar. O shell detecta o worker em espera e mostra um banner
    discreto **"nova versão disponível → Atualizar"**; ao confirmar, o worker novo
    assume e a página recarrega uma vez. Nada a escrever no app.

## P2 — Offline-first: fila de mutações durável

Escritas feitas offline **sobrevivem**. A capacidade
[`native.offline`](transpile.md) grava cada mutação numa fila durável no
IndexedDB (com chave de idempotência) e reaplica em ordem FIFO quando a conexão
volta — via o evento `online`, via Background Sync (aba fechada) ou explicitamente:

```python
from tempestweb import native


async def save_note(text: str) -> None:
    """Persist a note, queueing the write if we are offline."""
    await native.offline.enqueue("POST", "/api/notes", {"text": text})


async def flush_when_online() -> None:
    """Replay any pending mutations in FIFO order."""
    await native.offline.replay()
```

Inspecione a fila com `native.offline.size()` e `native.offline.pending()`. Uma
mutação que falha de forma permanente vira **dead-letter**
(`native.offline.failed()`) e um conflito `409` vai pra **lane de conflito**
(`native.offline.conflicts()`) — nenhum dos dois trava a fila. Veja
[Offline + sincronização](offline-sync.md) para o ciclo completo.

!!! warning "Replay precisa de idempotência"
    Ao voltar a rede, a fila reenvia as mutações. O servidor **deduplica pela chave
    de idempotência**, então um replay nunca aplica o efeito duas vezes. É a mesma
    chave da capacidade [`native.http`](capabilities.md).

## P3 — WebPush ponta a ponta

O browser cria a assinatura; o servidor envia. Os dois lados usam a **chave
VAPID** que prova ao serviço de push do navegador que o envio é legítimo.

### No cliente — `native.notifications`

```python
from tempestweb import native


async def enable_push(vapid_public_key: str) -> None:
    """Ask for permission and subscribe the browser to WebPush."""
    state = await native.notifications.push_state()   # {supported, permission}
    if not state.supported:
        return
    await native.notifications.request_permission()
    sub = await native.notifications.subscribe(vapid_public_key)
    # Envie `sub` (JSON da assinatura) ao seu backend — via native.http
    # ou enfileirado com native.offline. O framework não decide seu schema.
    await native.http.request("POST", "/webpush/subscribe", json=sub)
```

### No servidor — `tempestweb vapid` + `webpush_router`

Gere o par de chaves VAPID uma vez com o CLI e monte o roteador pronto:

```bash
tempestweb vapid --env   # imprime VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY
```

```python
from fastapi import FastAPI

from tempestweb.server import WebPushService, webpush_router

app = FastAPI()
service = WebPushService()                       # lê as chaves de VAPID_* no ambiente
app.include_router(webpush_router(service))       # /webpush/subscribe, /send, …
```

O `webpush_router` já expõe os endpoints de assinatura e envio; o
`WebPushService` guarda as assinaturas e dispara os envios assinados via
`tempest-fastapi-sdk[webpush]` (pywebpush).

!!! danger "iOS/Safari exige PWA instalada"
    No iOS (16.4+), o WebPush **só funciona com o PWA instalado** na tela inicial.
    Em browsers desktop e Android funciona sem instalar. Teste em device real —
    veja [Verificação manual](#verificacao-manual).

!!! info "O fluxo completo tem uma página só pra ele"
    O exemplo [WebPush ponta a ponta (servidor)](examples/webpush-server.md)
    percorre a geração de chaves, o roteador, a assinatura e o envio, passo a
    passo, com um diagrama de sequência.

## Configurando o manifest com `[pwa]`

Os metadados de instalação vêm de uma seção opcional `[pwa]` no seu
`tempestweb.toml`. Todos os campos são opcionais — sem a seção, o build usa
padrões sensatos derivados do nome do projeto:

```toml
[pwa]
name = "Weather Pro"
short_name = "WPro"
theme_color = "#0a84ff"
display = "standalone"
```

Os campos completos estão documentados na página
[Modo C — transpile](transpile.md#configurando-o-manifest-com-pwa).

## Verificação manual

!!! note "O que exige device/browser real"
    Algumas garantias de PWA **não dá** para automatizar 100%; confirme à mão:

    - Instalar o app a partir do prompt e abrir da tela inicial.
    - Desligar a rede e confirmar que o **2º load** abre o app (offline).
    - Receber uma notificação WebPush — **no iOS, com o PWA instalado**.

## Recap

- A PWA é mais turnkey no **[Modo C](transpile.md)**: `build --mode transpile`
  emite manifest, ícones e service worker sozinho.
- **Instalável** (P0) via `native.install`; **offline após o 1º load** (P1) via o
  service worker que pré-cacheia o bundle.
- O runtime offline (P2) usa **fila de mutações no IndexedDB** com chave de
  idempotência (`native.offline`).
- **WebPush** (P3): `native.notifications.subscribe` no cliente; `tempestweb vapid`
  + `webpush_router` no servidor.
- Alguns testes de PWA exigem device real — veja a verificação manual.

Para a saúde em produção, veja [Observabilidade](observability.md). 🚀
