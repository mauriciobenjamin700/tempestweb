# Observabilidade

A camada de **observabilidade / produção** (Trilho O) dá ao seu app telemetry,
logs estruturados, error boundary, feature flags e auth de cliente — tudo em
**Python tipado**, idêntico quer o Python rode no browser (Modo A) ou no servidor
(Modo B). 📊

!!! check "Superfície entregue (Trilho O · O0–O4)"
    As cinco fases estão **no pacote** e importáveis de
    `tempestweb.observability`. Cada uma tem um app completo em
    [Exemplos](../examples/index.md): [feature flags](../examples/feature-flags.md),
    [error boundary + telemetria](../examples/error-boundary.md) e
    [auth com JWT](../examples/auth-jwt.md).

## O padrão adapter

Todos os provedores seguem o mesmo princípio: uma **interface mínima** que você
troca sem tocar no app. Você programa contra o **provider**; o adapter decide para
onde vai (console, Sentry, GrowthBook, …).

```text
   seu app  ──chama──▶  Provider (API estável)  ──delega──▶  Adapter (backend)
                                                              console / sentry / posthog / ...
```

!!! check "Trocar backend não muda chamada"
    Migrar de `console` para `sentry` não altera **nenhuma** chamada `track()`. É
    a mesma promessa do `tempest-react-sdk`, agora em Python tipado.

!!! info "Provider é objeto, não singleton"
    Não existe `init()` global: você **constrói** o provider com o adapter que
    quer e guarda a instância (num módulo, no `State`, ou onde fizer sentido). No
    Modo A cada aba tem a sua; no Modo B cada sessão tem a sua. Sem estado global
    escondido para vazar entre usuários.

## O0 — Telemetry

Instrumenta eventos do framework e do app (service worker, push, replay offline,
erros) com provedor plugável.

```python hl_lines="3 5"
from tempestweb.observability import ConsoleTelemetryAdapter, TelemetryProvider

telemetry = TelemetryProvider(ConsoleTelemetryAdapter())

telemetry.track("order_submitted", {"items": 3, "total": 99.9})
telemetry.identify("user-42", {"plan": "pro"})
```

O construtor aceita dois ajustes que valem em produção:

```python
from tempestweb.observability import ConsoleTelemetryAdapter, TelemetryProvider

telemetry = TelemetryProvider(
    ConsoleTelemetryAdapter(),
    default_props={"app": "checkout", "release": "1.4.0"},
    sample_rate=0.1,
)
```

- `default_props` entra em **todo** evento, então você não repete o mesmo dict.
- `sample_rate=0.1` manda 10% dos eventos — o corte acontece no provider, antes
  do adapter, então o backend nem vê o resto.

Trocar de backend é trocar o adapter: `PostHogTelemetryAdapter`,
`SentryTelemetryAdapter`, ou o seu (a interface é `TelemetryAdapter`). Para
capturar eventos num teste, o console adapter aceita um `sink`:

```python
from typing import Any

from tempestweb.observability import ConsoleTelemetryAdapter, TelemetryProvider

captured: list[Any] = []
telemetry = TelemetryProvider(ConsoleTelemetryAdapter(sink=captured.append))
telemetry.track("checkout_opened")
```

!!! warning "Não vaze PII"
    Não coloque dados pessoais nos `props` e use `sample_rate` para não inundar o
    backend. A telemetria é diagnóstico, não um banco de dados de usuários.

## O1 — Logger

Logging estruturado com **sinks plugáveis** e níveis tipados (`LogLevel` é
`Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]`).

```python hl_lines="3"
from tempestweb.observability import console_sink, create_logger

log = create_logger(sinks=[console_sink], level="INFO")

log.info("order created", order_id="o-1", total=99.9)
log.error("payment failed", order_id="o-1", reason="card_declined")
```

Todo `**fields` extra viaja no `LogRecord` (`level`, `message`, `fields`), então
um sink de rede serializa o registro inteiro sem parsear string.

!!! note "No Modo A o sink default é o console do browser"
    Sinks de rede (enviar logs a um servidor) devem ser **async/não-bloqueantes** —
    no Modo A um sink bloqueante trava a aba.

## O2 — Error boundary

Captura erro de **render** → mostra um fallback visual + dispara um report, sem
derrubar o app. O resto da árvore segue vivo.

`ErrorBoundary` é um widget: ele recebe o filho como **builder** (`child_builder`),
não como widget já construído — é isso que permite chamar o build dentro do
`try`.

```python hl_lines="13 14 15"
from tempest_core import Text, Widget

from tempestweb.observability import (
    ErrorBoundary,
    ErrorInfo,
    TelemetryProvider,
    telemetry_reporter,
)


def panel(telemetry: TelemetryProvider) -> Widget:
    """Build the dashboard panel, guarded by a boundary."""
    return ErrorBoundary(
        key="dashboard",
        child_builder=lambda: build_dashboard(),
        fallback_builder=lambda info: Text(content=f"Algo quebrou: {info.message}"),
        on_error=telemetry_reporter(telemetry),
    )
```

O `ErrorInfo` que chega no fallback e no `on_error` traz `error`, `error_type`,
`message` e `stack` — dá para mostrar o tipo na tela e mandar o stack para o
backend.

Quando o padrão é sempre o mesmo, `with_error_boundary` monta o decorator:

```python hl_lines="6 7 8 9"
from tempest_core import Text, Widget

from tempestweb.observability import ErrorInfo, with_error_boundary


@with_error_boundary(
    fallback_builder=lambda info: Text(content=f"Algo quebrou: {info.message}"),
)
def risky_panel() -> Widget:
    """Build a panel that may raise during build."""
    return build_dashboard()
```

O decorator envolve um builder **sem argumentos** e devolve outro callable: chamar
`risky_panel()` te dá o `ErrorBoundary` pronto para pôr na árvore. Sem passar
`fallback_builder`, entra o `default_fallback`.

!!! tip "Erro de render ≠ erro de handler async"
    O boundary pega erros de **render** (durante o build do filho). Erros de
    handler async vão para o tratamento do event loop. Em ambos os casos,
    **reporte** — nunca engula o stack.

## O3 — Feature flags

Liga/desliga features em runtime com rollout gradual. A interface do adapter é
minúscula (`get` + `subscribe`), então escrever um novo dá ~20 linhas.

```python hl_lines="3"
from tempestweb.observability import FeatureFlagsProvider, InMemoryFeatureFlagsAdapter

flags = FeatureFlagsProvider(InMemoryFeatureFlagsAdapter({"new_checkout": True}))


def view() -> object:
    """Render checkout, gated by a feature flag."""
    if flags.is_enabled("new_checkout"):
        return new_checkout()
    return legacy_checkout()
```

- `is_enabled(key, default=False)` coage o valor para `bool` — flag ausente cai no
  `default`.
- `get(key, default)` devolve o valor cru (`bool`, `str`, número) para flag de
  variante: `flags.get("checkout_variant", "control")`.
- `on_change(listener)` registra um callback **sem argumentos** (avisa que algo
  mudou; você relê a flag) e devolve a função de cancelamento.

```python
unsubscribe = flags.on_change(lambda: app.request_rebuild())
```

Em produção, troque o adapter por `GrowthBookFeatureFlagsAdapter` ou
`LaunchDarklyFeatureFlagsAdapter` — nenhuma chamada `is_enabled` muda.

!!! warning "Flags não são segredo; tenha default seguro"
    Quando o backend de flags está fora, `is_enabled` cai no **default seguro** —
    nunca quebra o app. E nunca use flags para esconder segredos: elas são
    visíveis no cliente.

## O4 — Auth de cliente

Store de auth + guarda de rota + helpers de JWT + **fila de refresh** que
serializa renovações concorrentes (uma renovação, várias esperas).

```python hl_lines="10 12"
from tempestweb.observability import (
    create_auth_store,
    create_refresh_queue,
    is_jwt_expired,
    route_guard,
)

auth = create_auth_store()


async def renew() -> str:
    """Fetch a fresh token from the backend.

    Returns:
        The new access token.
    """
    response = await app.native.http.request("POST", "/api/refresh")
    return str(response.json_body["token"])


refresh = create_refresh_queue(auth, renew)
guard = route_guard(auth, redirect_to="/login")


async def call_api() -> dict[str, object]:
    """Call a protected endpoint, refreshing the token once if needed.

    Returns:
        The decoded JSON response.
    """
    token = auth.token
    if token is None or is_jwt_expired(token):
        token = await refresh.refresh()
    response = await app.native.http.request(
        "GET", "/api/me", headers={"Authorization": f"Bearer {token}"}
    )
    return dict(response.json_body)
```

A fila é o ponto sutil: `refresh.refresh()` é **single-flight**. Dez chamadas
concorrentes que acham o token expirado geram **uma** renovação e esperam todas o
mesmo resultado — `refresh.refresh_calls` conta as renovações reais, e é isso que
você afirma no teste.

O store guarda a sessão e avisa quem se inscreveu:

```python
from tempestweb.observability import create_auth_store

auth = create_auth_store()
auth.login(token, {"name": "Ana"})   # ou set_token(token) para só trocar o token
unsubscribe = auth.subscribe(lambda: app.request_rebuild())

print(auth.is_authenticated, auth.user, auth.token)
auth.logout()
```

`decode_jwt(token)` lê as claims **sem** verificar assinatura (é cliente: a
verificação é do servidor) e `is_jwt_expired(token, leeway_seconds=30)` decide
expiração com folga.

!!! danger "O token vive em lugares diferentes por modo"
    No **Modo A** o token vive no browser (storage) — trate **XSS** como risco
    real. No **Modo B** ele vive na sessão do servidor, mais protegido. O servidor
    reusa `JWTUtils` do `tempest-fastapi-sdk`, e `server_decode_jwt` faz a
    verificação com segredo.

## S8 — Observabilidade de servidor (Modo B)

`create_app(..., metrics=True)` já respondia **quantas** sessões existem. Não
respondia se elas estão lentas, onde o tempo é gasto, nem o que o servidor fez
para o cliente que acabou de reclamar — e Modo B é o modo que se opera em
produção.

```python
from tempestweb.observability import (
    PatchMetrics,
    ServerObservability,
    create_logger,
    json_log_sink,
    otel_tracer,
)
from tempestweb.server import create_app

app = create_app(
    state_factory=lambda: 0,
    view=view,
    metrics=True,
    observability=ServerObservability(
        metrics=PatchMetrics(),
        logger=create_logger(sinks=[json_log_sink], level="INFO"),
        tracer=otel_tracer(),  # opcional: precisa de tempestweb[otel]
    ),
)
```

### Latência e throughput

O histograma sai em `GET /metrics`, ao lado dos contadores de conexão:

```text
tempestweb_patch_seconds_bucket{le="0.005"} 40
tempestweb_patch_seconds_sum 0.012
tempestweb_patch_seconds_count 40
tempestweb_patches_total 40
```

O que ele mede é a espera que o **cliente** sente: do evento chegar até os patches
serem entregues ao transporte, **rebuild incluído**. Isso importa porque o rebuild
é coalescido — ele roda depois do handler retornar. Cronometrar o handler daria um
número que para antes do trabalho que o cliente está esperando (medido: rodadas com
zero patches).

!!! tip "O número bate com o do cliente"
    Medido num app real de 40 linhas: cliente 0,62 ms de ida e volta, servidor 0,30
    ms de tempo de patch — 49% da espera é servidor, o resto é WebSocket e
    loopback. O valor do servidor é sempre **menor**; se ele encostar no do cliente,
    a rede não é o problema.

### Log estruturado

Uma linha JSON por evento de ciclo de vida, com o `session_id` como **campo** —
que é o ponto: junta com o span pela mesma chave.

```json
{"level": "INFO", "message": "session.open", "session_id": "s-7f60c8ba0980", "transport": "ws"}
{"duration_s": 0.027, "level": "INFO", "message": "session.close", "reason": "closed", "session_id": "s-7f60c8ba0980", "transport": "ws"}
```

Sessão que morre de exceção fecha com `reason` sendo o nome da exceção, não
`"closed"`.

### Tracing

Um span por sessão, um por dispatch e um por lote de patches, atrás de um adapter.
`otel_tracer()` importa `opentelemetry` **dentro da função**: o default nunca
toca a lib, e um app que não faz tracing não paga o import. Exporter e sampler
ficam com o OpenTelemetry (env var ou setup de SDK que a app controla) —
embrulhar isso seria uma segunda superfície de configuração, pior que a primeira.

!!! note "Custo quando está desligado, medido"
    Default (`observability=None`): o dispatch não toma relógio e não abre span.
    Com métricas **e** log estruturado ligados, 200 cliques num app de 40 linhas
    passaram de 0,665 ms para 0,689 ms de média — **+3,6%**. É o preço de saber o
    que está acontecendo.

## Recap

- A observabilidade usa o **padrão adapter**: troca o backend sem mudar o app.
- **Provider é objeto que você constrói** — `TelemetryProvider(adapter)`,
  `FeatureFlagsProvider(adapter)` — não existe `init()` global.
- **Telemetry** (O0), **Logger** (O1), **Error boundary** (O2), **Feature flags**
  (O3) e **Auth** (O4) são todos Python tipado, idênticos nos Modos A e B.
- `ErrorBoundary` recebe **builders**, não widgets prontos; a fila de refresh é
  **single-flight**.
- Defaults seguros e cuidado com PII/tokens são parte do contrato.

Essa camada espelha os provedores do `tempest-react-sdk`. Para ver tudo junto num
app que roda, comece por
[error boundary + telemetria](../examples/error-boundary.md). 🚀
