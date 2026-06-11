# PWA e offline

A camada **PWA / offline-first / WebPush** (Trilho P) torna seu app **instalável**
e capaz de rodar **sem rede**. É compartilhada pelos dois modos — você escreve a
casca PWA uma vez. 📱

!!! info "Em construção (Trilho P)"
    Esta camada é o **Trilho P** do roadmap. As fases P0–P5 estão detalhadas no
    [plano de design](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
    Esta página descreve a **superfície planejada** e os fluxos principais.

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

    Store IndexedDB + fila/replay de eventos no reconnect (Background Sync).

-   :material-bell-ring: __WebPush (P3)__

    ---

    Subscribe no browser; envio via `tempest-fastapi-sdk[webpush]` (VAPID).

</div>

## P0 — App instalável

O primeiro passo é o **manifest** e a captura do prompt de instalação. O cliente
guarda o evento `beforeinstallprompt` e sua UI decide quando oferecer "Instalar".

```python
from tempestweb.pwa import install


def view(app: object) -> object:
    """Show an Install button only when installation is available."""
    if install.can_prompt():
        return install_button(on_click=install.prompt)
    return already_installed_banner()
```

!!! tip "Modo A também ganha com o PWA"
    No Modo A, o precache do service worker (P1) resolve o **cold-start do bundle
    WASM** — o segundo load abre instantâneo e offline.

## P1 — Service worker: offline após o 1º load

O service worker faz **precache do app-shell** (assets com hash) e gerencia o
ciclo de atualização. Quando uma versão nova é publicada, a UI mostra "nova
versão, recarregar"; ao confirmar, `skipWaiting` ativa a nova versão.

```python
from tempestweb.pwa import service_worker


async def setup_sw(app: object) -> None:
    """Register the service worker and wire the update lifecycle.

    Args:
        app: The running app handle.
    """
    await service_worker.register(
        url="/sw.js",
        on_update=lambda: app.set_state(lambda s: setattr(s, "update_ready", True)),
        on_error=lambda err: app.log.error("SW failed", error=err),
    )


async def apply_update() -> None:
    """Activate the waiting service worker and reload."""
    await service_worker.skip_waiting()
```

!!! check "Feito quando"
    O **segundo load offline** abre o app. Publicar uma versão nova dispara o
    banner "recarregar" — e ao confirmar, o app já está na versão nova.

## P2 — Offline-first em runtime

A store **IndexedDB** (owner-scoped por domínio) guarda dados e estado offline.
Mutations feitas offline entram numa **fila durável** com idempotency key (do
`native.http`) e **reaplicam sozinhas** ao voltar a rede (Background Sync).

```python
from tempestweb.native import storage


async def save_draft(text: str) -> None:
    """Persist a draft to IndexedDB, surviving offline.

    Args:
        text: The draft body to store.
    """
    await storage.put("drafts", {"id": "current", "text": text})


async def list_drafts() -> list[dict[str, object]]:
    """List stored drafts, newest first.

    Returns:
        The drafts ordered by creation time, most recent first.
    """
    return await storage.list("drafts", order_by="created_at", reverse=True)
```

A divergência por modo é só de **comportamento**, não de API:

| | Modo A | Modo B |
|---|---|---|
| Dados offline | Vivem no browser; offline é **pleno** | Último estado em cache (read-only) |
| Mutations offline | Aplicadas localmente | **Enfileiradas**; o servidor reconcilia ao reconectar |
| Banner online/offline | Ligado ao status de rede | Ligado ao status da conexão WS/SSE |

!!! warning "Replay precisa de idempotency"
    Ao voltar a rede, a fila reenvia as mutations. Sem a `idempotency_key` do
    [`native.http`](capabilities.md), um replay poderia duplicar efeito. Por isso a
    fila offline depende da capacidade HTTP.

## P3 — WebPush

O cliente faz `subscribe` (com a chave pública VAPID); o servidor envia via
`tempest-fastapi-sdk[webpush]` (pywebpush).

```python
from tempestweb.pwa import webpush


async def enable_notifications(app: object) -> None:
    """Subscribe the browser to WebPush and persist the subscription.

    Args:
        app: The running app handle.
    """
    sub = await webpush.subscribe(vapid_public_key=app.settings.VAPID_PUBLIC_KEY)
    await app.native.http.request("POST", "/webpush/subscribe", json=sub.to_dict())
```

!!! danger "iOS/Safari exige PWA instalada"
    No iOS (16.4+), o WebPush **só funciona com o PWA instalado** na tela inicial.
    Em browsers desktop e Android funciona sem instalar. Teste em device real —
    veja [Verificação manual](#verificacao-manual).

## P4 e P5 — Gate no CI e extras de manifest

- **P4 — Gate PWA no CI.** Um job roda **Lighthouse PWA** (headless) + testes de
  service worker; o CI reprova um PR que quebre "installable", o offline ou o push.
- **P5 — Extras de manifest.** `share_target` (pareia com [`native.share`](capabilities.md)),
  shortcuts e file handlers.

## Verificação manual

!!! note "O que exige device/browser real"
    Algumas garantias de PWA **não dá** para automatizar 100%; o CI usa Lighthouse
    headless (P4), mas confirme à mão:

    - Instalar o app a partir do prompt e abrir da tela inicial.
    - Desligar a rede e confirmar que o **2º load** abre o app (offline).
    - Receber uma notificação WebPush — **no iOS, com o PWA instalado**.

## Recap

- O Trilho P torna o app **instalável** (P0) e **offline após o 1º load** (P1).
- O runtime offline (P2) usa **IndexedDB + fila/replay** com idempotency key.
- **WebPush** (P3) faz subscribe no browser e envia via `tempest-fastapi-sdk`.
- O **CI** (P4) trava regressões com Lighthouse; alguns testes exigem device real.

A store offline é exposta ao Python como a capacidade `storage` — veja
[Capacidades](capabilities.md). Para a saúde em produção, veja
[Observabilidade](observability.md). 🚀
