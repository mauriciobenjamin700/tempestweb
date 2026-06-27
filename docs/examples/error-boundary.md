# Error Boundary + Telemetria — Contendo Falhas em Produção 🛡️

Aprenda a proteger sua UI com `ErrorBoundary`, conectar o hook de erro a um `Logger` estruturado e a um `TelemetryProvider`, e ver o painel de log atualizar em tempo real — tudo isso sem que uma única subtree quebrada apague a tela inteira.

---

## O problema que vamos resolver

Em qualquer app real, uma subtree pode falhar ao renderizar: um componente lê de uma fonte de dados que pode ser `None`, um valor calculado levanta exceção com entradas inválidas, ou um widget de terceiros lança de forma inesperada.

Sem proteção, **uma única exceção em `view()` apaga o app inteiro**. O usuário vê uma tela em branco e você não tem nenhuma evidência do que aconteceu.

Este exemplo mostra como resolver os dois lados do problema:

| Problema | Solução |
|---|---|
| Subtree quebrada apaga a tela | `ErrorBoundary` contém a exceção e renderiza um fallback |
| Falha silenciosa sem rastro | `Logger` + `TelemetryProvider` via `telemetry_reporter` |
| Estado da UI desatualizado após crash | `on_error` chama `app.set_state` para refletir o crash |

!!! note "Nota — complementar ao rollback de estado"
    O `ErrorBoundary` cuida de **erros de render**. O rollback de estado do core cuida de **erros em event handlers**. Os dois trabalham juntos: um não substitui o outro.

---

## O que você vai construir

Um demo interativo com:

- 🟢 Uma subtree protegida que mostra contagem de renders bem-sucedidos
- 💥 Botão **Trigger crash** que simula uma falha de renderização
- 🔄 Botão **Disable crash** que restaura a subtree saudável
- 📊 Painel lateral com `crash_count`, `last_error` e `log_entries` (últimas 5 entradas)
- 📡 Telemetria: cada crash gera um evento `render_error` no `TelemetryProvider`
- 📋 Log estruturado: cada crash gera um `LogRecord` de nível `WARNING`

---

## Pré-requisitos

```bash
pip install tempestweb
```

Leitura recomendada:

- [Tutorial básico](../tutorial/index.md) — `App`, `view`, `set_state`
- [Gerenciando estado](../tutorial/state.md) — mutadores e closures
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor

---

## Criando o projeto

```bash
mkdir -p examples/error-boundary
touch examples/error-boundary/app.py
```

---

## Passo 1 — Entendendo `ErrorBoundary`

`ErrorBoundary` é um `Component` do core. Você passa dois argumentos essenciais:

- `child_builder` — uma função `() -> Widget` que pode levantar exceção
- `on_error` — um hook `(ErrorInfo) -> None` chamado quando a exceção é capturada

Quando `child_builder()` levanta, a boundary:

1. Captura a exceção em um `ErrorInfo` (tipo, mensagem, stack)
2. Chama `on_error(info)` — para log, telemetria, ou qualquer outra ação
3. Renderiza o `fallback_builder(info)` no lugar da subtree quebrada
4. **Nunca propaga a exceção** — o resto do app continua renderizando normalmente

```python
from tempestweb.observability import ErrorBoundary, ErrorInfo

reported: list[ErrorInfo] = []

def broken() -> Text:
    raise ValueError("boom")

boundary = ErrorBoundary(child_builder=broken, on_error=reported.append)
rendered = boundary.render()  # não levanta — chama on_error e retorna o fallback
assert reported[0].error_type == "ValueError"
```

!!! tip "Dica — `ErrorInfo` tem tudo que você precisa"
    `ErrorInfo` é um `dataclass(frozen=True)` com quatro campos:

    | Campo | Tipo | Conteúdo |
    |---|---|---|
    | `error` | `BaseException` | A exceção original |
    | `error_type` | `str` | Nome da classe (`"RuntimeError"`) |
    | `message` | `str` | `str(error)` |
    | `stack` | `str` | Traceback formatado |

    O `error_type` e `message` são seguros para mostrar ao usuário. O `stack` vai para o log/telemetria — nunca direto na tela.

---

## Passo 2 — Definindo o estado

O estado precisa capturar tudo que a UI precisa refletir após um crash:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BoundaryState:
    """State for the error-boundary demo.

    Attributes:
        boom: When ``True`` the protected subtree raises a ``RuntimeError``,
            demonstrating the boundary's catch-and-fallback behaviour.
        render_count: Counts how many times the healthy subtree has rendered
            successfully.
        crash_count: Counts how many render errors have been caught by the
            boundary.
        last_error: The most recent captured error message, shown in the
            sidebar so the user can see what went wrong without losing the
            rest of the UI.
        log_entries: Human-readable log lines built from captured
            :class:`~tempestweb.observability.LogRecord` objects, shown in
            a live log panel.
    """

    boom: bool = False
    render_count: int = 0
    crash_count: int = 0
    last_error: str = ""
    log_entries: list[str] = field(default_factory=list)


def make_state() -> BoundaryState:
    """Build the initial state for the error-boundary demo.

    Returns:
        A fresh :class:`BoundaryState` with the protected subtree healthy.
    """
    return BoundaryState()
```

!!! info "Por que `log_entries` no estado?"
    O painel de log precisa ser reativo — ele deve atualizar automaticamente quando um novo crash acontece. Como o tempestweb é orientado a estado, a única forma de algo aparecer na UI é estar no estado. Por isso capturamos as entradas em `log_entries` via `set_state` dentro do `on_error`.

---

## Passo 3 — Configurando os sinks de observabilidade

Antes da `view`, criamos os dois sinks **no nível do módulo**. Isso é importante: em um app real, todos os componentes deveriam fan-in para o mesmo pipeline de telemetria.

### O Logger

```python
from tempestweb.observability import LogRecord, create_logger

#: Captura cada LogRecord emitido durante a sessão.
_log_records: list[LogRecord] = []


def _record_sink(record: LogRecord) -> None:
    """Append a log record to the module-level capture list.

    Args:
        record: The structured log record to store.

    Returns:
        None.
    """
    _log_records.append(record)


_logger = create_logger(sinks=[_record_sink], level="WARNING")
```

`create_logger` aceita uma lista de sinks — qualquer callable `(LogRecord) -> None`. Aqui passamos `_record_sink` para capturar os records para inspeção (e testes). Em produção você passaria também um `network_sink` que envia para o seu backend.

!!! tip "Dica — nível `WARNING`"
    Definimos `level="WARNING"` para que `DEBUG` e `INFO` sejam descartados antes de qualquer sink rodar. Erros de render são sempre `WARNING` ou superior, então nada se perde.

### O TelemetryProvider

```python
from typing import Any

from tempestweb.observability import ConsoleTelemetryAdapter, TelemetryProvider

#: Captura cada evento de telemetria para inspeção.
_telemetry_events: list[tuple[str, dict[str, Any]]] = []


def _make_telemetry_provider() -> TelemetryProvider:
    """Build a TelemetryProvider that captures events into the module list.

    Returns:
        A configured provider backed by a ConsoleTelemetryAdapter whose
        sink is also appending to _telemetry_events for test inspection.
    """

    def _sink(message: str) -> None:
        # Parseia a linha "[telemetry] track <event> <props>" emitida pelo adapter.
        if message.startswith("[telemetry] track "):
            rest = message[len("[telemetry] track ") :]
            space_idx = rest.find(" ")
            if space_idx != -1:
                event_name = rest[:space_idx]
                try:
                    import ast

                    props: dict[str, Any] = ast.literal_eval(rest[space_idx + 1 :])
                except Exception:  # noqa: BLE001
                    props = {"raw": rest[space_idx + 1 :]}
                _telemetry_events.append((event_name, props))

    return TelemetryProvider(ConsoleTelemetryAdapter(sink=_sink))


_telemetry_provider = _make_telemetry_provider()
```

`ConsoleTelemetryAdapter` formata cada evento como a string `[telemetry] track <event> <props>` e a passa para o `sink`. Ao injetar um `sink` customizado, conseguimos tanto ver os eventos no console (bom para dev) quanto capturá-los estruturados (bom para testes).

!!! note "Nota — adaptadores intercambiáveis"
    Trocar de `ConsoleTelemetryAdapter` para `SentryTelemetryAdapter` ou `PostHogTelemetryAdapter` é uma única linha de código — o restante do app não muda. O pattern adapter é o coração do Trilho O.

---

## Passo 4 — O hook `on_error`

O `on_error` é o ponto onde tudo se conecta. Ele recebe um `ErrorInfo` e tem três responsabilidades:

```python
from tempestweb.observability import ErrorInfo, telemetry_reporter


def on_error(info: ErrorInfo) -> None:
    """Handle a captured render error: log it, track it, update state.

    Args:
        info: The captured render failure from the boundary.
    """
    # 1. Log estruturado — WARNING level
    _logger.warning(
        "render_error_caught",
        error_type=info.error_type,
        error_msg=info.message,
    )
    # 2. Telemetria — encaminha para o provider
    telemetry_reporter(_telemetry_provider)(info)

    # 3. Estado — espelha o crash na UI
    def _update(s: BoundaryState) -> None:
        s.crash_count += 1
        s.last_error = f"{info.error_type}: {info.message}"
        entry = f"[{info.error_type}] {info.message}"
        s.log_entries = (s.log_entries + [entry])[-5:]  # mantém só as últimas 5

    app.set_state(_update)
```

Vamos dissecar cada parte:

**`_logger.warning(...)`** — emite um `LogRecord` com `level="WARNING"`. Os campos extras (`error_type`, `error_msg`) ficam disponíveis em `record.fields` para qualquer sink. Note o uso de `error_msg` em vez de `message` para não colidir com o parâmetro posicional do método.

**`telemetry_reporter(_telemetry_provider)(info)`** — `telemetry_reporter` é uma factory que recebe um `TelemetryProvider` e devolve um `ErrorReporter`. Quando chamado com `info`, ele chama `provider.track("render_error", {...})` com os campos `error_type`, `message` e `stack`.

**`app.set_state(_update)`** — atualiza o estado para que a UI reflita o crash. O painel de log e o contador são reativos: aparecem na próxima renderização automaticamente.

!!! warning "Atenção — `on_error` é chamado durante o render"
    `on_error` é chamado **síncrono** dentro de `ErrorBoundary.render()`. Não faça I/O bloqueante aqui. Sinks de rede devem ser fire-and-forget (enfileirar e enviar em background).

---

## Passo 5 — O `child_builder` e o `toggle_boom`

A "subtree protegida" é uma função simples que levanta quando `state.boom` é `True`:

```python
def child_builder() -> Widget:
    """Build the protected subtree; raises when state.boom is set.

    Returns:
        A healthy widget showing the render count, or raises
        RuntimeError when state.boom is True.

    Raises:
        RuntimeError: When state.boom is True, simulating a widget that
            fails to render due to bad data or a missing dependency.
    """
    if app.state.boom:
        raise RuntimeError("simulated render failure — bad data upstream")

    app.set_state(lambda s: setattr(s, "render_count", s.render_count + 1))

    return Column(
        key="healthy-subtree",
        style=Style(gap=4.0, padding=Edge.all(8)),
        children=[
            Text(
                content="Protected subtree is healthy.",
                key="healthy-label",
            ),
            Text(
                content=f"Successful renders: {app.state.render_count}",
                key="render-count",
            ),
        ],
    )
```

E o handler do botão de toggle:

```python
def toggle_boom() -> None:
    """Flip the boom flag to trigger / clear the simulated crash."""
    app.set_state(lambda s: setattr(s, "boom", not s.boom))
```

!!! tip "Dica — simule falhas reais"
    Em apps reais, `child_builder` seria algo como `lambda: UserProfileCard(user=fetch_user(id))` onde `fetch_user` pode retornar `None`. O `RuntimeError` aqui é apenas um atalho para o demo. O pattern é idêntico.

---

## Passo 6 — Montando o layout

O layout tem quatro seções fora da boundary (que nunca são afetadas por ela) e a boundary em si:

```python
from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


def view(app: App[BoundaryState]) -> Widget:
    """Render the error-boundary demo UI from the current state."""

    # ... (handlers definidos aqui — ver passos 4 e 5)

    status_text = "CRASH MODE ON" if app.state.boom else "healthy"
    toggle_label = "Disable crash" if app.state.boom else "Trigger crash"

    log_children: list[Widget] = [
        Text(content="Log panel (last 5 entries):", key="log-title")
    ]
    if app.state.log_entries:
        for i, entry in enumerate(app.state.log_entries):
            log_children.append(Text(content=entry, key=f"log-{i}"))
    else:
        log_children.append(Text(content="No errors captured yet.", key="log-empty"))

    return Column(
        key="root",
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            # Cabeçalho
            Text(content="Error Boundary Demo", key="title"),
            # Linha de controles
            Row(
                key="controls",
                style=Style(gap=8.0),
                children=[
                    Button(
                        label=toggle_label,
                        on_click=toggle_boom,
                        key="toggle-boom",
                    ),
                    Text(content=f"Status: {status_text}", key="status"),
                    Text(
                        content=f"Crashes caught: {app.state.crash_count}",
                        key="crash-count",
                    ),
                ],
            ),
            # Subtree protegida pela ErrorBoundary
            ErrorBoundary(
                key="boundary",
                child_builder=child_builder,
                on_error=on_error,
            ),
            # Último erro (fora da boundary — nunca afetado por ela)
            Text(
                content=(
                    f"Last error: {app.state.last_error}"
                    if app.state.last_error
                    else "No error captured yet."
                ),
                key="last-error",
            ),
            # Painel de log (também fora da boundary)
            Column(
                key="log-panel",
                style=Style(gap=2.0, padding=Edge.all(8)),
                children=log_children,
            ),
        ],
    )
```

!!! check "Ponto-chave — o layout externo nunca quebra"
    O header, os botões de controle, o display de último erro e o painel de log estão **fora** da `ErrorBoundary`. Eles continuam renderizando normalmente mesmo quando `child_builder` levanta. Somente a área da boundary (onde `healthy-subtree` ou o fallback aparece) é afetada pelo crash.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Error boundary + telemetry — demonstrating production-grade crash containment.

A real app has subtrees that can go wrong: a component reads from a data source
that can be null, a computed value raises on bad input, or a third-party widget
throws unexpectedly. Without an :class:`~tempestweb.observability.ErrorBoundary`
one broken subtree blanks the whole screen. This example shows how to:

1. Wrap a risky subtree in ``ErrorBoundary`` so the rest of the app keeps
   rendering when the child raises.
2. Wire ``on_error`` to both a structured :class:`~tempestweb.observability.Logger`
   (for human-readable crash records) and a
   :class:`~tempestweb.observability.TelemetryProvider` (for analytics / alerting)
   using :func:`~tempestweb.observability.telemetry_reporter`.
3. Toggle the failure from the UI so you can see the live transition:
   healthy subtree → fallback + log entry + telemetry event → healthy again.

Run it in either mode::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.observability import (
    ConsoleTelemetryAdapter,
    ErrorBoundary,
    ErrorInfo,
    LogRecord,
    TelemetryProvider,
    create_logger,
    telemetry_reporter,
)

# ---------------------------------------------------------------------------
# Shared observability sinks — in a real app these would live at the module
# level so that all components fan into the same telemetry pipeline.
# ---------------------------------------------------------------------------

#: Captures every :class:`~tempestweb.observability.LogRecord` emitted during the
#: session so the test (and a dev console panel) can inspect them.
_log_records: list[LogRecord] = []

#: Captures every telemetry event dict so the test can assert on them.
_telemetry_events: list[tuple[str, dict[str, Any]]] = []


def _make_telemetry_provider() -> TelemetryProvider:
    """Build a :class:`TelemetryProvider` that captures events into the module list.

    Returns:
        A configured provider backed by a :class:`ConsoleTelemetryAdapter` whose
        sink is also appending to :data:`_telemetry_events` for test inspection.
    """

    def _sink(message: str) -> None:
        # Parse the conventional "[telemetry] track <event> <props>" line emitted
        # by ConsoleTelemetryAdapter so the test list is structured.
        if message.startswith("[telemetry] track "):
            rest = message[len("[telemetry] track ") :]
            space_idx = rest.find(" ")
            if space_idx != -1:
                event_name = rest[:space_idx]
                try:
                    import ast

                    props: dict[str, Any] = ast.literal_eval(rest[space_idx + 1 :])
                except Exception:  # noqa: BLE001
                    props = {"raw": rest[space_idx + 1 :]}
                _telemetry_events.append((event_name, props))

    return TelemetryProvider(ConsoleTelemetryAdapter(sink=_sink))


def _record_sink(record: LogRecord) -> None:
    """Append a log record to the module-level capture list.

    Args:
        record: The structured log record to store.

    Returns:
        None.
    """
    _log_records.append(record)


# Module-level providers (created once; tests can inspect the captured lists).
_telemetry_provider = _make_telemetry_provider()
_logger = create_logger(sinks=[_record_sink], level="WARNING")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class BoundaryState:
    """State for the error-boundary demo.

    Attributes:
        boom: When ``True`` the protected subtree raises a ``RuntimeError``,
            demonstrating the boundary's catch-and-fallback behaviour.
        render_count: Counts how many times the healthy subtree has rendered
            successfully.
        crash_count: Counts how many render errors have been caught by the
            boundary.
        last_error: The most recent captured error message, shown in the
            sidebar so the user can see what went wrong without losing the
            rest of the UI.
        log_entries: Human-readable log lines built from captured
            :class:`~tempestweb.observability.LogRecord` objects, shown in
            a live log panel.
    """

    boom: bool = False
    render_count: int = 0
    crash_count: int = 0
    last_error: str = ""
    log_entries: list[str] = field(default_factory=list)


def make_state() -> BoundaryState:
    """Build the initial state for the error-boundary demo.

    Returns:
        A fresh :class:`BoundaryState` with the protected subtree healthy.
    """
    return BoundaryState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[BoundaryState]) -> Widget:
    """Render the error-boundary demo UI from the current state.

    The view nests an :class:`~tempestweb.observability.ErrorBoundary` inside a
    larger layout. When ``state.boom`` is ``True`` the child raises; the boundary
    renders the fallback, calls :data:`_logger` and :data:`_telemetry_provider` via
    the ``on_error`` hook, and updates ``crash_count`` / ``last_error`` on the app
    state. The outer layout — header, controls, log panel — keeps rendering
    regardless.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # -----------------------------------------------------------------------
    # Handlers
    # -----------------------------------------------------------------------

    def toggle_boom() -> None:
        """Flip the ``boom`` flag to trigger / clear the simulated crash."""
        app.set_state(lambda s: setattr(s, "boom", not s.boom))

    def on_error(info: ErrorInfo) -> None:
        """Handle a captured render error: log it, track it, update state.

        Args:
            info: The captured render failure from the boundary.
        """
        # Structured log — WARNING level so it surfaces even in production.
        # NOTE: use ``error_msg`` as the field name to avoid shadowing the
        # positional ``message`` parameter of Logger.warning.
        _logger.warning(
            "render_error_caught",
            error_type=info.error_type,
            error_msg=info.message,
        )
        # Telemetry (forwards to the module-level provider).
        telemetry_reporter(_telemetry_provider)(info)

        # Mirror onto app state so the UI reflects the crash.
        def _update(s: BoundaryState) -> None:
            s.crash_count += 1
            s.last_error = f"{info.error_type}: {info.message}"
            # Append only the last 5 log lines so the panel stays readable.
            entry = f"[{info.error_type}] {info.message}"
            s.log_entries = (s.log_entries + [entry])[-5:]

        app.set_state(_update)

    # -----------------------------------------------------------------------
    # Protected child builder
    # -----------------------------------------------------------------------

    def child_builder() -> Widget:
        """Build the protected subtree; raises when ``state.boom`` is set.

        Returns:
            A healthy widget showing the render count, or raises
            ``RuntimeError`` when ``state.boom`` is ``True``.

        Raises:
            RuntimeError: When ``state.boom`` is ``True``, simulating a
                widget that fails to render due to bad data or a missing
                dependency.
        """
        if app.state.boom:
            raise RuntimeError("simulated render failure — bad data upstream")

        # Bump render_count so the test can confirm successful re-renders.
        app.set_state(lambda s: setattr(s, "render_count", s.render_count + 1))

        return Column(
            key="healthy-subtree",
            style=Style(gap=4.0, padding=Edge.all(8)),
            children=[
                Text(
                    content="Protected subtree is healthy.",
                    key="healthy-label",
                ),
                Text(
                    content=f"Successful renders: {app.state.render_count}",
                    key="render-count",
                ),
            ],
        )

    # -----------------------------------------------------------------------
    # Assemble the layout
    # -----------------------------------------------------------------------

    # Status badge next to the toggle button.
    status_text = "CRASH MODE ON" if app.state.boom else "healthy"
    toggle_label = "Disable crash" if app.state.boom else "Trigger crash"

    # Log panel entries.
    log_children: list[Widget] = [
        Text(content="Log panel (last 5 entries):", key="log-title")
    ]
    if app.state.log_entries:
        for i, entry in enumerate(app.state.log_entries):
            log_children.append(Text(content=entry, key=f"log-{i}"))
    else:
        log_children.append(Text(content="No errors captured yet.", key="log-empty"))

    return Column(
        key="root",
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            # Header
            Text(content="Error Boundary Demo", key="title"),
            # Controls row
            Row(
                key="controls",
                style=Style(gap=8.0),
                children=[
                    Button(
                        label=toggle_label,
                        on_click=toggle_boom,
                        key="toggle-boom",
                    ),
                    Text(content=f"Status: {status_text}", key="status"),
                    Text(
                        content=f"Crashes caught: {app.state.crash_count}",
                        key="crash-count",
                    ),
                ],
            ),
            # Protected subtree wrapped in ErrorBoundary
            ErrorBoundary(
                key="boundary",
                child_builder=child_builder,
                on_error=on_error,
            ),
            # Last error display (outside the boundary — never affected by it)
            Text(
                content=(
                    f"Last error: {app.state.last_error}"
                    if app.state.last_error
                    else "No error captured yet."
                ),
                key="last-error",
            ),
            # Live log panel (also outside the boundary)
            Column(
                key="log-panel",
                style=Style(gap=2.0, padding=Edge.all(8)),
                children=log_children,
            ),
        ],
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/error-boundary/app.py
```

O Python roda **dentro do browser** via Pyodide. Sem servidor necessário. Ideal para demos e protótipos.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/error-boundary/app.py
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica ao DOM. Ideal para produção com SEO e first-paint rápido.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Título **"Error Boundary Demo"**
    2. Botão **Trigger crash** + Status: **healthy** + **Crashes caught: 0**
    3. Subtree saudável: _"Protected subtree is healthy."_ + _"Successful renders: N"_
    4. _"No error captured yet."_ abaixo
    5. Painel de log: _"No errors captured yet."_

    Ao clicar **Trigger crash**:

    6. Botão muda para **Disable crash** + Status: **CRASH MODE ON**
    7. A área da boundary mostra o fallback: _"Something went wrong."_ + `(RuntimeError)`
    8. **Crashes caught: 1** atualiza
    9. _"Last error: RuntimeError: simulated render failure — bad data upstream"_
    10. Painel de log adiciona `[RuntimeError] simulated render failure — bad data upstream`
    11. O cabeçalho, botões e painel de log **continuam visíveis e funcionais**

    Ao clicar **Disable crash**:

    12. Subtree saudável volta — _"Protected subtree is healthy."_
    13. `render_count` reinicia a contar

---

## Verificação automatizada ✅

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes (14 testes, todos verdes)
pytest -q tests/unit/test_example_error_boundary.py
```

!!! note "Nota — 14 testes cobrindo todo o ciclo"
    A suite cobre: montagem inicial, tipos de widgets na árvore, estado inicial, fallback com boom=True, atualização de crash_count/last_error, log_entries, captura de ErrorInfo, evento telemetria via telemetry_reporter, captura no módulo, recuperação, diff entre estados, acumulação de crash_count após múltiplos ciclos, e cap de 5 entradas no log.

---

## Como funciona por dentro

### O fluxo completo de um crash

```
view(app) chamada
      │
      ▼
ErrorBoundary.render()
      │
      ├─ child_builder() → levanta RuntimeError
      │
      ▼
ErrorInfo.from_exception(exc)
      │
      ├─ on_error(info)
      │       ├─ _logger.warning(...)     → LogRecord em _log_records
      │       ├─ telemetry_reporter(...)  → evento em _telemetry_events
      │       └─ app.set_state(_update)   → crash_count++, last_error, log_entries
      │
      ▼
fallback_builder(info) → Column("Something went wrong.", "(RuntimeError)")
      │
      ▼
Resto do layout continua renderizando normalmente
```

### Por que `telemetry_reporter` é uma factory?

`telemetry_reporter(provider)` recebe um `TelemetryProvider` e devolve um `ErrorReporter` (que é apenas `Callable[[ErrorInfo], None]`). Isso permite compor o reporter com outros reporters ou passá-lo diretamente como `on_error`:

```python
# Forma direta — sem logger customizado
boundary = ErrorBoundary(
    child_builder=risky_component,
    on_error=telemetry_reporter(my_provider),
)

# Forma composta — com logger + telemetria (como neste exemplo)
def on_error(info: ErrorInfo) -> None:
    _logger.warning("render_error_caught", error_type=info.error_type)
    telemetry_reporter(my_provider)(info)
    app.set_state(lambda s: setattr(s, "crash_count", s.crash_count + 1))
```

### O decorator `@with_error_boundary`

Para casos simples onde você quer proteger um builder existente sem mudar a call site, use o decorator:

```python
from tempestweb.observability import with_error_boundary

@with_error_boundary(on_error=telemetry_reporter(my_provider))
def profile_card() -> Widget:
    # pode levantar — agora protegida
    return Column(children=[Text(content=user.name)])
```

`profile_card()` agora retorna um `ErrorBoundary` em vez de um `Widget` diretamente — transparente para quem chama.

### `log_entries` é limitado a 5

O painel de log usa um slice `[-5:]` para manter no máximo 5 entradas:

```python
s.log_entries = (s.log_entries + [entry])[-5:]
```

Isso evita que o painel cresça sem limites em produção onde crashes podem se acumular.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Usar `ErrorBoundary` para conter falhas de render em subtrees específicas
- ✅ Entender os campos de `ErrorInfo` (`error_type`, `message`, `stack`)
- ✅ Conectar `on_error` a um `Logger` estruturado com `create_logger`
- ✅ Usar `telemetry_reporter` para encaminhar crashes ao `TelemetryProvider`
- ✅ Usar `ConsoleTelemetryAdapter` com sink injetável para dev e testes
- ✅ Atualizar o estado do app dentro de `on_error` via `app.set_state`
- ✅ Limitar listas reativas a um tamanho máximo com slice `[-N:]`
- ✅ Criar sinks de observabilidade no nível do módulo para fan-in de componentes
- ✅ Usar o decorator `@with_error_boundary` para proteger builders existentes

---

## Próximos passos

- 💡 Troque `ConsoleTelemetryAdapter` por `SentryTelemetryAdapter` para ver o mesmo padrão direcionando crashes ao Sentry
- 💡 Adicione um segundo sink ao `create_logger` que envia records para um endpoint HTTP em background
- 💡 Explore [Feature Flags](./feature-flags.md) (Trilho O3) para desabilitar features instáveis sem deploy
- 💡 Explore [Gate de autenticação JWT](./auth-jwt.md) (Trilho O4) para proteger rotas com JWT + refresh automático
