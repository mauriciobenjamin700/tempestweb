# Observabilidade

A camada de **observabilidade / produção** (Trilho O) dá ao seu app telemetry,
logs estruturados, error boundary, feature flags e auth de cliente — tudo em
**Python tipado**, idêntico nos dois modos. 📊

!!! info "Em construção (Trilho O)"
    Esta camada é o **Trilho O** do roadmap. As fases O0–O4 estão detalhadas no
    [plano de design](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
    Esta página descreve a **superfície planejada** e o padrão adapter.

## O padrão adapter

Todos os provedores seguem o mesmo princípio: uma **interface mínima** que você
troca sem tocar no app. Você programa contra a API; o adapter decide para onde
vai (console, Sentry, GrowthBook, …).

```text
   seu app  ──chama──▶  Provider (API estável)  ──delega──▶  Adapter (backend)
                                                              console / sentry / posthog / ...
```

!!! check "Trocar backend não muda chamada"
    Migrar de `console` para `sentry` não altera **nenhuma** chamada `track()`. É
    a mesma promessa do `tempest-react-sdk`, agora em Python tipado.

## O0 — Telemetry

Instrumenta eventos do framework e do app (service worker, push, replay offline,
erros) com provedor plugável.

```python
from tempestweb.observability import telemetry
from tempestweb.observability.telemetry import ConsoleAdapter


telemetry.init(adapter=ConsoleAdapter())

telemetry.track("order_submitted", {"items": 3, "total": 99.9})
telemetry.identify("user-42")
```

!!! warning "Não vaze PII"
    Não coloque dados pessoais nos `props` e use amostragem para não inundar o
    backend. A telemetria é diagnóstico, não um banco de dados de usuários.

## O1 — Logger

Logging estruturado com **sinks plugáveis** e níveis tipados (`LogLevel`).

```python
from tempestweb.observability import create_logger, console_sink

log = create_logger(sinks=[console_sink])

log.info("order created", order_id="o-1", total=99.9)
log.error("payment failed", order_id="o-1", reason="card_declined")
```

!!! note "No Modo A o sink default é o console do browser"
    Sinks de rede (enviar logs a um servidor) devem ser **async/não-bloqueantes** —
    no Modo A um sink bloqueante trava a aba.

## O2 — Error boundary

Captura erro de **render** → mostra um fallback visual + dispara um report, sem
derrubar o app. O resto da árvore segue vivo.

```python
from tempestweb.observability import error_boundary
from tempestweb._core import Text, Widget


@error_boundary(fallback=lambda err: Text(content=f"Algo quebrou: {err}"))
def risky_panel(app: object) -> Widget:
    """Render a panel that may raise during build.

    Args:
        app: The running app handle.

    Returns:
        The rendered panel widget.
    """
    return build_dashboard(app.state)   # se lançar, o fallback aparece
```

!!! tip "Erro de render ≠ erro de handler async"
    O boundary pega erros de **render** (durante o `view()`). Erros de handler
    async vão para o tratamento do event loop. Em ambos os casos, **reporte** —
    nunca engula o stack.

## O3 — Feature flags

Liga/desliga features em runtime com rollout gradual. A interface do adapter é
minúscula (~20 linhas para implementar uma nova).

```python
from tempestweb.observability import feature_flags
from tempestweb.observability.feature_flags import InMemoryAdapter


feature_flags.init(adapter=InMemoryAdapter({"new_checkout": True}))


def view(app: object) -> object:
    """Render checkout, gated by a feature flag."""
    if feature_flags.is_enabled("new_checkout"):
        return new_checkout(app)
    return legacy_checkout(app)
```

!!! warning "Flags não são segredo; tenha default seguro"
    Quando o backend de flags está fora, `is_enabled` deve cair num **default
    seguro** — nunca quebrar o app. E nunca use flags para esconder segredos: elas
    são visíveis no cliente.

## O4 — Auth de cliente

Store de auth + guarda de rota + helpers de JWT + **fila de refresh** que
serializa renovações concorrentes (uma renovação, várias esperas).

```python
from tempestweb.observability import create_auth_store, create_refresh_queue

auth = create_auth_store()
refresh = create_refresh_queue(auth)


async def call_api(app: object) -> dict[str, object]:
    """Call a protected endpoint, refreshing the token once if needed.

    Args:
        app: The running app handle.

    Returns:
        The decoded JSON response.
    """
    if auth.is_token_expired():
        await refresh.run()   # várias chamadas concorrentes => UM refresh
    response = await app.native.http.request(
        "GET", "/api/me", headers={"Authorization": f"Bearer {auth.token}"}
    )
    return response.json()
```

!!! danger "O token vive em lugares diferentes por modo"
    No **Modo A** o token vive no browser (storage) — trate **XSS** como risco
    real. No **Modo B** ele vive na sessão do servidor, mais protegido. O servidor
    reusa `JWTUtils` do `tempest-fastapi-sdk`.

## Recap

- A observabilidade usa o **padrão adapter**: troca o backend sem mudar o app.
- **Telemetry** (O0), **Logger** (O1), **Error boundary** (O2), **Feature flags**
  (O3) e **Auth** (O4) são todos Python tipado, idênticos nos dois modos.
- Defaults seguros e cuidado com PII/tokens são parte do contrato.

Essa camada espelha os provedores do `tempest-react-sdk`. Para o detalhe
fase-a-fase, leia o
[plano de design](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
🚀
