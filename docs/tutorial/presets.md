# Telas prontas (presets)

!!! abstract "O que você vai aprender"
    Como montar um painel administrativo inteiro — shell com sidebar, dashboard
    de KPIs, listagem com busca e paginação, formulário e tela de login —
    **descrevendo os dados**, sem escrever um `Style`, um tamanho de fonte ou um
    breakpoint. E como o layout vira responsivo de graça. 🚀

## O problema

Componente pronto o tempestweb já tem: `Card`, `DataTable`, `StatCard`,
`AppBar`, `EmptyState`… Ainda assim, montar um painel dá trabalho — o exemplo
[`dashboard-shell`](https://github.com/mauriciobenjamin700/tempestweb/tree/main/examples/dashboard-shell)
gasta **716 linhas**, quase todas decidindo espaçamento, tamanho de fonte, cor
de item ativo e quantas colunas o grid tem.

Pior: nada disso se adapta. O `Style` inline não tem media query, então um
layout montado na mão nasce de largura fixa.

Os **presets** resolvem os dois: você diz *o que* tem na tela, eles decidem
*como* aparece.

=== "Com preset"

    ```python
    from tempestweb.presets import Kpi, NavItem, admin_shell, dashboard_page


    def view(app: App[State]) -> Widget:
        return admin_shell(
            title="Console ACME",
            nav=[NavItem("Visão geral", "overview"), NavItem("Usuários", "users")],
            active=app.state.tab,
            on_navigate=lambda value: app.set_state(lambda s: setattr(s, "tab", value)),
            body=dashboard_page(
                title="Visão geral",
                kpis=[
                    Kpi("Receita", "R$ 82.400", delta="+12%", tone="success"),
                    Kpi("Churn", "1,8%", delta="-0,3%", up=False, tone="warning"),
                ],
            ),
        )
    ```

=== "Na mão"

    ```python
    return Scaffold(
        app_bar=AppBar(title="Console ACME", ...),
        sidebar=Sidebar(children=[
            Button(label="Visão geral", on_click=..., style=Style(
                padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                radius=8.0, background=ACCENT if active else ...,
                color=..., font_size=14.0, font_weight=...,
            )),
            # … repetido por item, e de novo em cada tela
        ]),
        body=Column(style=Style(gap=24.0, padding=Edge.all(24.0)), children=[
            Text(content="Visão geral", style=Style(font_size=24.0, ...)),
            Grid(columns=4, children=[...]),   # 4 fixo: quebra no celular
        ]),
    )
    ```

## Os cinco presets

| Preset | Para que serve |
|---|---|
| `admin_shell` | Header + sidebar colapsável + área de conteúdo |
| `dashboard_page` | Linha de KPIs + grid de seções |
| `list_page` | Toolbar com busca, tabela, paginação, estado vazio |
| `form_page` / `settings_page` | Campos rotulados em grid + barra de ações |
| `auth_page` | Card centrado com o seu formulário dentro |

Cada um recebe **registros tipados**, não widgets de layout:

```python
from tempestweb.presets import (
    FormField, FormSection, Kpi, NavItem, Section, TableColumn,
)
```

## Um app completo

```python
from dataclasses import dataclass

from tempest_core import App, Text, Widget
from tempest_core.widgets import Button
from tempestweb.presets import (
    Kpi, NavItem, Section, TableColumn, admin_shell, dashboard_page, list_page,
)

USERS = [("Ana", "ana@acme.com", "R$ 12.400"), ("Bruno", "bruno@acme.com", "R$ 8.900")]


@dataclass
class State:
    tab: str = "overview"
    sidebar_open: bool = False
    query: str = ""


def make_state() -> State:
    return State()


def view(app: App[State]) -> Widget:
    def navigate(value: str) -> None:
        app.set_state(lambda s: (setattr(s, "tab", value), setattr(s, "sidebar_open", False))[0])

    def toggle() -> None:
        app.set_state(lambda s: setattr(s, "sidebar_open", not s.sidebar_open))

    def search(text: str) -> None:
        app.set_state(lambda s: setattr(s, "query", text))

    if app.state.tab == "overview":
        body = dashboard_page(
            title="Visão geral",
            subtitle="Últimos 30 dias",
            kpis=[
                Kpi("Receita", "R$ 82.400", delta="+12%", tone="success"),
                Kpi("Usuários ativos", "1.284", delta="+4%", tone="success"),
                Kpi("Churn", "1,8%", delta="-0,3%", up=False, tone="warning"),
            ],
            sections=[Section("Notas", Text(content="Sem incidentes.", key="n"))],
        )
    else:
        rows = [r for r in USERS if app.state.query.lower() in r[0].lower()]
        body = list_page(
            title="Usuários",
            columns=[TableColumn("Nome"), TableColumn("Email"), TableColumn("Saldo", align="end")],
            rows=[list(row) for row in rows],
            search=app.state.query,
            on_search=search,
            actions=[Button(label="Novo usuário", on_click=lambda: None, key="new")],
            empty_title="Nenhum usuário encontrado",
        )

    return admin_shell(
        title="Console ACME",
        brand="ACME",
        nav=[NavItem("Visão geral", "overview"), NavItem("Usuários", "users", badge="3")],
        active=app.state.tab,
        on_navigate=navigate,
        sidebar_open=app.state.sidebar_open,
        on_toggle_sidebar=toggle,
        body=body,
    )
```

Rode com `tempestweb dev --mode server` (ou `--mode wasm`) e você tem: sidebar
fixa no desktop, gaveta com scrim no celular, KPIs que refluem, tabela com
cabeçalho fixo e rolagem lateral, zebra nas linhas — sem uma linha de CSS.

!!! check "Nada aqui mede a tela"
    Não existe `if largura < 768` no seu código nem no dos presets. Os
    breakpoints moram em `client/layouts.js`, a folha que o cliente injeta no
    mount. **A mesma árvore está certa em qualquer largura**, nos três modos.

## O que a folha entrega

| Comportamento | Onde aparece |
|---|---|
| Sidebar vira gaveta sobreposta abaixo de 1024px | `admin_shell` |
| Botão ☰ aparece só onde a sidebar é gaveta | `admin_shell` |
| Scrim que fecha a gaveta ao tocar fora | `admin_shell` |
| KPIs refluem 4 → 3 → 2 → 1 conforme a largura | `dashboard_page` |
| Seções em grid, com `span="full"` ocupando a linha | `dashboard_page` |
| Tabela rola na horizontal com cabeçalho fixo | `list_page` |
| Zebra e realce de linha sob o ponteiro | `list_page` |
| Campos em grid, uma coluna no celular | `form_page` |
| Barra de ações empilhada (ação primária por último) | `form_page` |
| Card de login centrado e limitado a 420px | `auth_page` |
| Impressão sem sidebar, header nem botões | todos |
| `prefers-reduced-motion` desliga a animação da gaveta | `admin_shell` |

## Como funciona por dentro

Cada preset carimba `data-tw-layout="<papel>"` nos containers que ele controla,
usando o escape hatch `attrs` do core. A folha casa as regras por esse atributo:

```html
<div data-tw-layout="shell">
  <div data-tw-layout="shell-sidebar" data-tw-open="false">…</div>
  <div data-tw-layout="shell-header">…</div>
  <div data-tw-layout="shell-main">
    <div data-tw-layout="page">…</div>
  </div>
</div>
```

O vocabulário de papéis é **fechado** e vive em `tempestweb/presets/roles.py`;
testes quebram se a folha estilizar um papel que ninguém emite ou se um papel
ficar sem regra. Você não precisa (nem deve) carimbar esses atributos na mão —
eles vêm de usar um preset.

!!! warning "Style inline sempre ganha"
    Nada na folha usa `!important`. Se você passar um `Style` num widget, o valor
    dele vence — a folha é piso, não gaiola. O outro lado da moeda: um widget que
    **já** tem cor inline (todo `Button` tem, resolvido pela variante do core)
    não pode ser recolorido pela folha. Por isso o realce de hover do item de
    navegação é um `filter`, não um `background`.

## Personalizando

Os presets leem tokens CSS que você sobrescreve com um `<style>` seu:

```html
<style>
  :root {
    --tw-layout-sidebar-width: 300px;
    --tw-layout-content-max: 1440px;
    --tw-layout-page-padding: 32px;
    --tw-layout-kpi-min: 240px;   /* KPIs mais largos = menos colunas */
    --tw-primary: #0b57d0;        /* token do tema base, herdado pelos títulos */
  }
</style>
```

Precisa de mais que isso? Os presets compõem os **mesmos componentes públicos**
que você usaria. Troque só o miolo:

```python
admin_shell(
    ...,
    body=my_hand_built_screen(app),   # o shell continua; o conteúdo é seu
)
```

## Recapitulando

- **Você descreve, o preset desenha.** `NavItem`, `Kpi`, `Section`,
  `TableColumn`, `FormField` — dados, não layout.
- **Responsivo sem media query sua.** Tudo em `client/layouts.js`, ligado por
  `data-tw-layout`.
- **Nada de beco sem saída.** Inline `Style` ainda ganha, tokens rebrandeiam a
  folha, e qualquer região aceita um widget seu no lugar.

!!! warning "Modos A e B — presets não transpilam"
    O compilador do Modo C só aceita imports de `tempest_core` e
    `tempestweb.native`. Um app que importe `tempestweb.presets` para no
    `build --mode transpile`, com `file:line`:

    ```text
    tempestweb build: transpile failed: app.py:23: import from
    'tempestweb.presets' is not supported (only tempest_core and `tempestweb.native`)
    ```

    Presets são para painel interno e app logado, onde o Modo B é a escolha
    natural. Tela pública que precisa de bundle estático continua sendo montada
    com widgets do core.

Exemplo completo, comentado passo a passo:
[**Console Administrativo**](../examples/admin-console.md) — as mesmas telas do
[`dashboard-shell`](../examples/dashboard-shell.md) em 261 linhas em vez de 716.

!!! info "Referência de API"
    Assinatura de cada preset e de cada registro: [`tempestweb.presets`](../reference/presets.md).
