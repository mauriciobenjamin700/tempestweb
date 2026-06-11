# Track T10 — Trilho O (observability / produção)

Branch: `feat/observability`

## O que foi construído

Pacote `tempestweb/observability/` — cinco provedores de produção, todos no
**padrão adapter** (interface mínima estável + adapters trocáveis). Trocar o
backend nunca toca um call site. Nenhum SDK de terceiro é dependência: cada
adapter envolve uma instância **injetada**.

| Fase | Arquivo | Superfície pública |
|------|---------|--------------------|
| **O0 — Telemetry** | `telemetry.py` | `TelemetryProvider.track/identify`, `TelemetryAdapter` (Protocol), adapters `ConsoleTelemetryAdapter` (sink injetável), `SentryTelemetryAdapter`, `PostHogTelemetryAdapter`. Sampling determinístico + `default_props` globais. |
| **O1 — Logger** | `logger.py` | `create_logger`, `Logger` (`debug/info/warning/error/critical/log`, `set_level`), `LoggerSink` (Protocol), `console_sink`, `LogLevel` (`Literal`), `LogRecord`. Filtro por nível; sink que levanta não derruba os outros. |
| **O2 — Error boundary** | `error_boundary.py` | `ErrorBoundary` (core `Component` que envolve um builder de subárvore), `default_fallback`, `with_error_boundary` (decorator), `telemetry_reporter` (liga no O0), `ErrorInfo`. |
| **O3 — Feature flags** | `feature_flags.py` | `FeatureFlagsProvider.is_enabled/get/on_change`, `FeatureFlagsAdapter` (Protocol), adapters `InMemoryFeatureFlagsAdapter` (notifica no `set`), `GrowthBookFeatureFlagsAdapter`, `LaunchDarklyFeatureFlagsAdapter`. Default seguro quando a flag é desconhecida. |
| **O4 — Auth** | `auth.py` | `decode_jwt`/`is_jwt_expired` (sem verificar assinatura — lado cliente), `create_auth_store`/`AuthStore` (login/logout/set_token/subscribe), `route_guard`, `create_refresh_queue`/`RefreshQueue`, `server_decode_jwt` (reusa `tempest-fastapi-sdk` `JWTUtils`). |

Tudo re-exportado em `tempestweb/observability/__init__.py` com `__all__`
atualizado (38 nomes); imports são sempre de nível de pacote.

## "Feito quando" — atendido

- **Cada provider tem interface mínima + >=1 adapter funcional.** Sim (ver tabela).
- **Trocar o adapter não muda call sites.** Testado explicitamente em
  `test_swapping_adapter_changes_no_call_sites` (telemetry e feature_flags): a
  mesma função `emit(provider)` / `read(provider)` dirige backends diferentes.
- **Teste unitário por provider com terceiros mockados.** 54 testes; Sentry,
  PostHog, GrowthBook e LaunchDarkly entram via `unittest.mock.MagicMock`.
- **A fila de refresh serializa refresh concorrente numa única renovação.**
  `test_concurrent_refreshes_collapse_into_single_renewal`: 5 chamadas
  concorrentes -> `refresh_calls == 1`, todas recebem o mesmo token. Também
  coberto: reset após settle (refresh posterior renova de novo) e propagação de
  falha com retry.

## Verificação (verde)

```
ruff check .              PASS
ruff format --check .     PASS
mypy tempestweb           PASS (strict, 15 arquivos)
pytest tests/unit/test_observability*.py   54 passed
pytest -q (suíte inteira) 58 passed
```

Comando-alvo do escopo: `pytest tests/unit/test_observability*.py -q` -> verde.

## O que está stubbed / decisões de design

- **`decode_jwt` NÃO verifica assinatura** — intencional e documentado: é uma
  conveniência de cliente para inspecionar expiry/claims de exibição. A
  verificação real é responsabilidade do servidor (Modo B) via `server_decode_jwt`
  -> `tempest_fastapi_sdk.JWTUtils`.
- **`tempest-fastapi-sdk` não está instalado** neste worktree e **não foi
  adicionado como dependência** (o escopo do T10 é cliente-side; o uso do SDK é
  server-only). `server_decode_jwt` faz import lazy e levanta `RuntimeError` com
  instrução de instalar o extra `[auth]` se o SDK estiver ausente. **Para
  verificar o caminho servidor de verdade é preciso instalar o SDK** (ver abaixo).
- Adapters de Sentry/PostHog/GrowthBook/LaunchDarkly assumem a superfície mínima
  comum de cada SDK (ex.: Sentry `capture_message`/`set_user`, PostHog
  `capture`/`identify`, GrowthBook `get_feature_value`, LaunchDarkly
  `variation`). Se uma versão real divergir, o ajuste é local ao adapter — o
  provider e os call sites não mudam.
- GrowthBook/LaunchDarkly não empurram mudança no wrapper mínimo; expõem
  `refresh()`/`notify()` para o caller disparar a notificação após recarregar
  features / receber stream update.

## Verificação manual necessária

1. **Integração real com SDKs de terceiros.** Os testes usam mocks. Antes de usar
   em produção, instanciar cada adapter com o cliente real
   (`sentry_sdk`, `posthog`, `growthbook`, `launchdarkly-server-sdk`) e confirmar
   que os nomes de método batem com a versão instalada.
2. **`server_decode_jwt` com o SDK presente.** Instalar
   `tempest-fastapi-sdk[auth]` e validar `JWTUtils.decode(token, secret)` num
   token assinado de verdade (o teste só cobre o ramo "SDK ausente").
3. **Error boundary ao vivo no DOM.** `ErrorBoundary.render()` é testado em
   Python (produz o fallback sem levantar). O efeito visual real depende do
   patcher do cliente (T1) e do loop de eventos; verificar no browser após o
   merge com T1.

## Ordem de merge sugerida

T10 é **ortogonal** (dirs próprios, sem dependência de runtime de outro track) e
pode mergear a qualquer momento após T1. Ordem do MANIFEST:
`T1 -> T2/T3 -> T4 -> T9 -> T5/T7/T8/T10 -> T6`. Nada em T10 bloqueia outro track.

## Commits (nesta branch, após a base)

- `feat: add O0 telemetry + O1 logger observability providers`
- `feat: add O2 error boundary (render-error fallback + report hook)`
- `feat: add O3 feature flags (provider + in-memory/growthbook/launchdarkly)`
- `feat: add O4 client auth (store + guard + JWT helpers + refresh queue)`
- `fix: serialize refresh queue via a single shared asyncio.Task`
- `test: cover O0-O4 observability providers (54 tests)`
