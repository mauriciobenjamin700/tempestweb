# Charts dashboard — gráficos em Canvas 🚀

Neste exemplo você vai montar um **mini dashboard de analytics**: dois gráficos
(barras e linhas multi-série) desenhados em `<canvas>`, uma fileira de cartões de
métrica, e um botão **Next week** que reescreve os dados. Tudo controlado por
estado Python tipado — você não escreve uma linha de JavaScript.

---

## O que você vai construir

- 📊 Um **BarChart** com a receita diária da semana.
- 📈 Um **LineChart** com duas séries (visitas e cadastros).
- 🧮 Uma fileira de **MetricCard** / **StatCard** com totais e variação percentual.
- 🔁 Um botão **Next week** que avança a janela de dados e repinta os gráficos.

!!! note "Nota — dados determinísticos"
    O exemplo guarda apenas um índice de semana (`week: int`) no estado. Todos os
    números — totais, deltas, séries — são **derivados** dentro de `view()` a cada
    render. Sem estado redundante, sem dessincronização.

---

## Pré-requisitos

```bash
pip install tempestweb
```

!!! tip "Dica"
    Se você ainda não conhece o ciclo estado → view → patches, leia primeiro o
    [tutorial de introdução](../tutorial/index.md).

---

## Passo 1 — Os dados de domínio

Começamos com duas semanas de números sintéticos. O dashboard mostra uma semana
por vez; o botão alterna entre elas.

```python
from __future__ import annotations

from dataclasses import dataclass, field

# Duas semanas de figuras diárias sintéticas.
WEEKLY_REVENUE: list[list[float]] = [
    [1200.0, 1500.0, 900.0, 1800.0, 2100.0, 2400.0, 1700.0],
    [1600.0, 1400.0, 2000.0, 2300.0, 1900.0, 2600.0, 2200.0],
]
WEEKLY_VISITS: list[list[float]] = [
    [320.0, 410.0, 280.0, 500.0, 640.0, 720.0, 480.0],
    [450.0, 390.0, 560.0, 680.0, 600.0, 810.0, 700.0],
]
WEEKLY_SIGNUPS: list[list[float]] = [
    [12.0, 18.0, 9.0, 22.0, 31.0, 40.0, 25.0],
    [20.0, 16.0, 28.0, 34.0, 30.0, 45.0, 38.0],
]
DAY_LABELS: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
```

Os dados ficam como constantes de módulo — nunca são copiados para o estado.

---

## Passo 2 — O estado

O estado é minúsculo: só o índice da semana e os rótulos do eixo X.

```python
@dataclass
class DashboardState:
    """State for the analytics dashboard.

    Attributes:
        week: Index of the currently displayed week (0 or 1).
        labels: The x-axis day labels shared by every chart.
    """

    week: int = 0
    labels: list[str] = field(default_factory=lambda: list(DAY_LABELS))


def make_state() -> DashboardState:
    """Build the initial dashboard state.

    Returns:
        A fresh :class:`DashboardState` showing the first week.
    """
    return DashboardState()
```

---

## Passo 3 — Helpers de formatação

Dois pequenos helpers puros mantêm a `view` limpa: um formata dinheiro, o outro
calcula a variação percentual entre dois totais.

```python
def _money(value: float) -> str:
    """Format a number as a compact USD string.

    Args:
        value: The raw monetary amount.

    Returns:
        The amount formatted with a dollar sign and thousands separators.
    """
    return f"${value:,.0f}"


def _delta_pct(current: float, previous: float) -> tuple[str, bool]:
    """Compute a percentage delta and its direction.

    Args:
        current: The current period's total.
        previous: The prior period's total to compare against.

    Returns:
        A tuple of the formatted percentage string and whether it went up.
    """
    if previous == 0.0:
        return "+0%", True
    change: float = (current - previous) / previous * 100.0
    return f"{change:+.1f}%", change >= 0.0
```

!!! tip "Dica — funções puras são testáveis"
    Como `_money` e `_delta_pct` não tocam em `app.state`, você pode testá-las
    diretamente com `pytest`, sem montar nenhum runtime.

---

## Passo 4 — Os cartões de métrica

`MetricCard` e `StatCard` recebem `label`, `value`, `delta`, `delta_up` e um
`color_scheme`. O `delta_up` controla a cor da seta (verde para cima, vermelho
para baixo).

```python
from tempest_core import Row, Style
from tempestweb.components import MetricCard, StatCard

metrics: Row = Row(
    style=Style(gap=12.0),
    children=[
        MetricCard(
            key="m-revenue",
            label="Revenue",
            value=_money(revenue_total),
            delta=revenue_delta,
            delta_up=revenue_up,
            color_scheme="primary",
        ),
        MetricCard(
            key="m-visits",
            label="Visits",
            value=f"{visits_total:,.0f}",
            delta=visits_delta,
            delta_up=visits_up,
            color_scheme="secondary",
        ),
        StatCard(
            key="m-signups",
            label="Sign-ups",
            value=f"{signups_total:,.0f}",
            delta=signups_delta,
            delta_up=signups_up,
            color_scheme="tertiary",
        ),
    ],
)
```

---

## Passo 5 — Os gráficos em Canvas

O `BarChart` recebe `values` + `labels`. O `LineChart` recebe uma lista de
`ChartSeries`, cada uma com seus `points`, um `label` e um `color_scheme`. Ambos
desenham no `<canvas>` — `width`/`height` definem o tamanho do bitmap.

```python
from tempest_core import Card, Text
from tempestweb.components import BarChart, ChartSeries, LineChart

revenue_card: Card = Card(
    key="card-revenue",
    children=[
        Text(content="Daily revenue", key="title-revenue"),
        BarChart(
            key="chart-revenue",
            width=520.0,
            height=220.0,
            color_scheme="primary",
            values=revenue,
            labels=app.state.labels,
        ),
    ],
)

trends_card: Card = Card(
    key="card-trends",
    children=[
        Text(content="Engagement trends", key="title-trends"),
        LineChart(
            key="chart-trends",
            width=520.0,
            height=220.0,
            series=[
                ChartSeries(points=visits, label="Visits", color_scheme="primary"),
                ChartSeries(
                    points=signups,
                    label="Sign-ups",
                    color_scheme="tertiary",
                ),
            ],
        ),
    ],
)
```

!!! info "Info — o Canvas é só mais um nó da árvore"
    O renderizador DOM emite um `<canvas>` e reexecuta o desenho quando os
    `values`/`series` mudam. Para você, autor do app, o gráfico é apenas um widget
    como qualquer outro — nada de manipular contexto 2D na mão.

---

## Passo 6 — O handler "Next week"

Um único handler avança a janela de dados, fazendo `wrap` com módulo:

```python
def next_week() -> None:
    app.set_state(lambda s: setattr(s, "week", (s.week + 1) % len(WEEKLY_REVENUE)))
```

Como tudo é derivado de `state.week`, mudar esse índice repinta **todos** os
gráficos e cartões de uma só vez.

---

## O app completo

```python
"""Charts dashboard — a tempestweb example showcasing Canvas-backed charts.

This small analytics dashboard renders two charts (a bar chart and a multi-series
line chart) plus a row of metric cards, all driven entirely by typed Python state.
Like every tempestweb example, the same ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

A "Next week" button mutates the state to advance the data window, demonstrating
that the charts re-render reactively from the same source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import (
    BarChart,
    Card,
    ChartSeries,
    LineChart,
    MetricCard,
    StatCard,
)

# Two weeks of synthetic daily figures. The dashboard shows one week at a time and
# the "Next week" button toggles between them.
WEEKLY_REVENUE: list[list[float]] = [
    [1200.0, 1500.0, 900.0, 1800.0, 2100.0, 2400.0, 1700.0],
    [1600.0, 1400.0, 2000.0, 2300.0, 1900.0, 2600.0, 2200.0],
]
WEEKLY_VISITS: list[list[float]] = [
    [320.0, 410.0, 280.0, 500.0, 640.0, 720.0, 480.0],
    [450.0, 390.0, 560.0, 680.0, 600.0, 810.0, 700.0],
]
WEEKLY_SIGNUPS: list[list[float]] = [
    [12.0, 18.0, 9.0, 22.0, 31.0, 40.0, 25.0],
    [20.0, 16.0, 28.0, 34.0, 30.0, 45.0, 38.0],
]
DAY_LABELS: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class DashboardState:
    """State for the analytics dashboard.

    Attributes:
        week: Index of the currently displayed week (0 or 1).
        labels: The x-axis day labels shared by every chart.
    """

    week: int = 0
    labels: list[str] = field(default_factory=lambda: list(DAY_LABELS))


def make_state() -> DashboardState:
    """Build the initial dashboard state.

    Returns:
        A fresh :class:`DashboardState` showing the first week.
    """
    return DashboardState()


def _money(value: float) -> str:
    """Format a number as a compact USD string.

    Args:
        value: The raw monetary amount.

    Returns:
        The amount formatted with a dollar sign and thousands separators.
    """
    return f"${value:,.0f}"


def _delta_pct(current: float, previous: float) -> tuple[str, bool]:
    """Compute a percentage delta and its direction.

    Args:
        current: The current period's total.
        previous: The prior period's total to compare against.

    Returns:
        A tuple of the formatted percentage string and whether it went up.
    """
    if previous == 0.0:
        return "+0%", True
    change: float = (current - previous) / previous * 100.0
    return f"{change:+.1f}%", change >= 0.0


def view(app: App[DashboardState]) -> Widget:
    """Render the dashboard UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def next_week() -> None:
        app.set_state(lambda s: setattr(s, "week", (s.week + 1) % len(WEEKLY_REVENUE)))

    week: int = app.state.week
    prev: int = (week - 1) % len(WEEKLY_REVENUE)

    revenue: list[float] = WEEKLY_REVENUE[week]
    visits: list[float] = WEEKLY_VISITS[week]
    signups: list[float] = WEEKLY_SIGNUPS[week]

    revenue_total: float = sum(revenue)
    visits_total: float = sum(visits)
    signups_total: float = sum(signups)

    revenue_delta, revenue_up = _delta_pct(revenue_total, sum(WEEKLY_REVENUE[prev]))
    visits_delta, visits_up = _delta_pct(visits_total, sum(WEEKLY_VISITS[prev]))
    signups_delta, signups_up = _delta_pct(signups_total, sum(WEEKLY_SIGNUPS[prev]))

    metrics: Row = Row(
        style=Style(gap=12.0),
        children=[
            MetricCard(
                key="m-revenue",
                label="Revenue",
                value=_money(revenue_total),
                delta=revenue_delta,
                delta_up=revenue_up,
                color_scheme="primary",
            ),
            MetricCard(
                key="m-visits",
                label="Visits",
                value=f"{visits_total:,.0f}",
                delta=visits_delta,
                delta_up=visits_up,
                color_scheme="secondary",
            ),
            StatCard(
                key="m-signups",
                label="Sign-ups",
                value=f"{signups_total:,.0f}",
                delta=signups_delta,
                delta_up=signups_up,
                color_scheme="tertiary",
            ),
        ],
    )

    revenue_card: Card = Card(
        key="card-revenue",
        children=[
            Text(content="Daily revenue", key="title-revenue"),
            BarChart(
                key="chart-revenue",
                width=520.0,
                height=220.0,
                color_scheme="primary",
                values=revenue,
                labels=app.state.labels,
            ),
        ],
    )

    trends_card: Card = Card(
        key="card-trends",
        children=[
            Text(content="Engagement trends", key="title-trends"),
            LineChart(
                key="chart-trends",
                width=520.0,
                height=220.0,
                series=[
                    ChartSeries(points=visits, label="Visits", color_scheme="primary"),
                    ChartSeries(
                        points=signups,
                        label="Sign-ups",
                        color_scheme="tertiary",
                    ),
                ],
            ),
        ],
    )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24)),
        children=[
            Row(
                style=Style(gap=12.0),
                children=[
                    Text(content=f"Analytics — Week {week + 1}", key="heading"),
                    Button(label="Next week", on_click=next_week, key="next-week"),
                ],
            ),
            metrics,
            Row(
                style=Style(gap=16.0),
                children=[revenue_card, trends_card],
            ),
        ],
    )
```

---

## Rodando o exemplo ▶

=== "Modo A — WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/charts-dashboard
    ```

    O Pyodide carrega o Python no browser; o `<canvas>` é desenhado localmente.

=== "Modo B — Servidor (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server --path examples/charts-dashboard
    ```

    O Python roda no servidor; o cliente recebe patches JSON e repinta o canvas.

!!! check "Verificação"
    Você deve ver dois gráficos e três cartões de métrica. Clique em **Next week**
    → o título muda para "Week 2", as barras e linhas se reorganizam, e os deltas
    recalculam. ✅

---

## Recapitulando

- ✅ Guardar **só o mínimo** no estado (`week`) e derivar o resto na `view`.
- ✅ Renderizar gráficos em Canvas com `BarChart` e `LineChart` + `ChartSeries`.
- ✅ Exibir métricas com `MetricCard` / `StatCard` (`delta` + `delta_up`).
- ✅ Repintar tudo com uma única mutação de estado.
- ✅ Rodar o mesmo `app.py` nos dois modos sem alterar uma linha.

!!! tip "Próximos passos"
    - Adicione um seletor de intervalo (dia/semana/mês) com `SegmentedControl`.
    - Veja o [Dashboard app shell](dashboard-shell.md) para um layout completo.
