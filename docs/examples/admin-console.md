# Console Administrativo (presets)

> 🚀 **O que você vai construir:** um painel administrativo inteiro — shell com
> sidebar colapsável, dashboard de KPIs, listagem com busca e paginação e uma
> tela de ajustes — **descrevendo os dados**, sem escrever um `Style`, um tamanho
> de fonte ou um breakpoint. E responsivo de graça.

---

## Por que esse exemplo importa?

Este é o mesmo painel do exemplo [Dashboard App Shell](dashboard-shell.md),
escrito de outro jeito.

| | Dashboard App Shell | Console Administrativo |
|---|---|---|
| Linhas de `app.py` | **716** | **261** |
| Decide espaçamento, fonte, cor | você | o preset |
| Responsivo | não — larguras fixas | sim, sem código seu |
| O que você escreve | widgets de layout | registros tipados |

A diferença não é de tamanho, é de **quem decide**. No shell manual você monta
`Scaffold` + `Sidebar` + `Grid` e escolhe cada `padding`, cada `font_size`, cada
`Color` de item ativo — e repete essas escolhas em cada tela. Aqui você diz
*quais* itens o menu tem, *quais* KPIs a tela mostra, *quais* colunas a tabela
tem; o preset decide a aparência.

!!! question "Qual dos dois eu uso?"
    **Presets** quando a tela é um arquétipo de painel administrativo — que é a
    maioria das telas internas. **À mão** quando o layout é específico do seu
    produto e nenhum preset descreve. Os dois usam os mesmos widgets do core e
    convivem no mesmo app: você pode passar um widget seu como `body` de uma
    `Section`.

Neste tutorial você vai aprender a:

- Montar o shell com `admin_shell` — header, sidebar colapsável e área de conteúdo;
- Descrever um dashboard com `dashboard_page`, `Kpi` e `Section`;
- Descrever uma listagem com `list_page`, `TableColumn`, busca e paginação;
- Descrever um formulário com `settings_page`, `FormSection` e `FormField`;
- Entender por que o preset **nunca filtra nem pagina os seus dados**.

!!! note "Roda nos dois modos interativos, sem alteração"
    A mesma `view()` roda em WASM (Pyodide no browser) e em Servidor (FastAPI +
    WebSocket). A responsividade vem de `client/layouts.js`, que é o mesmo
    cliente JS nos dois casos.

!!! warning "Presets ainda não vão para o Modo C"
    O transpilador só aceita imports de `tempest_core` e `tempestweb.native`.
    Um `build --mode transpile` deste exemplo para na hora, com a linha exata:

    ```text
    tempestweb build: transpile failed: app.py:23: import from
    'tempestweb.presets' is not supported (only tempest_core and `tempestweb.native`)
    ```

    Por isso o selo da galeria é **[A/B]** e não [A/B/C]. Se a tela precisa ser
    um bundle estático, monte-a com widgets do core — é o que o
    [Tour do Modo C](transpile-tour.md) mostra.

## Pré-requisitos

```bash
pip install tempestweb
```

Nenhum extra é necessário para o Modo A. Para o Modo B, `pip install
"tempestweb[server]"`.

## Estrutura do projeto

```text
admin-console/
└── app.py        # tudo aqui — 261 linhas
```

Um arquivo só. Não há CSS, não há `styles/`, não há tokens de tema: o preset
emite marcadores de papel (`data-tw-layout`) e a folha responsiva do cliente
resolve a aparência.

## Passo 1 — Os registros que descrevem a tela

Presets não recebem widgets de layout, recebem **registros tipados**:

```python
from tempestweb.presets import (
    FormField,
    FormSection,
    Kpi,
    NavItem,
    Section,
    TableColumn,
    admin_shell,
    dashboard_page,
    list_page,
    settings_page,
)

NAV: list[NavItem] = [
    NavItem("Visão geral", "overview"),
    NavItem("Usuários", "users", badge="3"),
    NavItem("Ajustes", "settings"),
]
```

`NavItem(label, value, badge=...)` — o `value` é o que chega no seu
`on_navigate`. O `badge` é opcional e vira o contador ao lado do rótulo.

O estado é um dataclass comum:

```python
@dataclass
class State:
    """Application state."""

    tab: str = "overview"
    sidebar_open: bool = False
    query: str = ""
    page: int = 1
    company: str = "ACME Ltda"
    notify: str = "diário"
    errors: dict[str, str] = field(default_factory=dict)
```

!!! tip "Dica — `sidebar_open` é seu, não do preset"
    O preset desenha a sidebar aberta ou fechada conforme o `bool` que você
    passa, e chama o `on_toggle_sidebar` quando o usuário toca no burger. Ele não
    guarda estado nenhum. É a mesma regra de todos os presets: eles **renderizam**,
    o app **decide**.

## Passo 2 — O dashboard: `Kpi` + `Section`

```python
def _overview() -> Widget:
    """Build the dashboard screen."""
    return dashboard_page(
        title="Visão geral",
        subtitle="Últimos 30 dias",
        kpis=[
            Kpi("Receita", "R$ 82.400", delta="+12%", tone="success"),
            Kpi("Usuários ativos", "1.284", delta="+4%", tone="success"),
            Kpi("Churn", "1,8%", delta="-0,3%", up=False, tone="warning"),
            Kpi("Chamados abertos", "17", delta="+5", tone="danger"),
        ],
        sections=[
            Section(
                "Receita por semana",
                LineChart(
                    key="revenue",
                    series=[
                        ChartSeries(label="2026", points=[12.0, 18.0, 15.0, 22.0, 28.0])
                    ],
                ),
                subtitle="Em milhares de reais",
                span="full",
            ),
            Section("Notas", Text(content="Sem incidentes na semana.", key="notes")),
        ],
    )
```

Você não escreveu nenhum número de coluna. O grid de KPIs é
`repeat(auto-fit, minmax(…, 1fr))`: cabem quantos cartões couberem na largura
disponível — quatro numa tela de 1440px, um num celular de 390px — e o número
muda sozinho conforme a janela. `tone` é `"neutral"` (padrão), `"success"`,
`"warning"` ou `"danger"`, e `up=False` inverte a seta do delta sem mexer na cor.

`Section(title, body, subtitle=..., span=...)` é o cartão de conteúdo. O `body`
é **qualquer widget** — aqui um `LineChart` do core, ali um `Text`. `span="full"`
faz a seção ocupar a linha inteira do grid.

!!! info "Info — o preset não sabe o que é um gráfico"
    `Section` recebe um `Widget` e o desenha dentro do cartão. Isso é o que
    mantém os presets úteis: o arquétipo cobre a moldura, e o miolo continua
    sendo o catálogo inteiro do `tempest_core`.

## Passo 3 — A listagem: `list_page`

```python
def _users(app: App[State]) -> Widget:
    """Build the user listing screen."""

    def search(text: str) -> None:
        app.set_state(lambda s: (setattr(s, "query", text), setattr(s, "page", 1))[0])

    def go(page: int) -> None:
        app.set_state(lambda s: setattr(s, "page", page))

    rows = _matching(app.state.query)
    return list_page(
        title="Usuários",
        subtitle=f"{len(rows)} de {len(USERS)}",
        columns=[
            TableColumn("Nome"),
            TableColumn("Email"),
            TableColumn("Papel"),
            TableColumn("Saldo", align="end"),
        ],
        rows=[
            [name, email, Badge(label=role, tone="info", key=f"role-{email}"), balance]
            for name, email, role, balance in rows
        ],
        search=app.state.query,
        on_search=search,
        actions=[Button(label="Novo usuário", on_click=lambda: None, key="new-user")],
        page=app.state.page,
        page_count=2,
        on_page=go,
        empty_title="Nenhum usuário encontrado",
        empty_subtitle="Ajuste a busca ou convide alguém para a equipe.",
    )
```

Uma célula de `rows` é uma **string ou um widget** — repare no `Badge` na terceira
coluna. `TableColumn("Saldo", align="end")` alinha a coluna inteira à direita,
cabeçalho junto. `empty_title`/`empty_subtitle` só aparecem quando `rows` está
vazia; você não escreve o `if`.

!!! warning "Aviso — o preset **não** filtra nem pagina os seus dados"
    `search=` e `page=` são **valores exibidos**, não instruções. Quem corta a
    lista é você:

    ```python
    def _matching(query: str) -> list[tuple[str, str, str, str]]:
        """Filter the user list by name or email."""
        needle = query.strip().lower()
        if not needle:
            return USERS
        return [
            row for row in USERS if needle in row[0].lower() or needle in row[1].lower()
        ]
    ```

    É deliberado. No mundo real a busca costuma virar um `WHERE` no banco ou um
    parâmetro de API, não um filtro em memória — um preset que "filtrasse
    sozinho" só funcionaria no caso de brinquedo. Repare também que `search()`
    devolve `page` para `1`: mudar o filtro sem resetar a página é o bug clássico
    dessa tela.

## Passo 4 — O formulário: `settings_page`

```python
    return settings_page(
        title="Ajustes",
        subtitle="Preferências da organização",
        sections=[
            FormSection(
                "Organização",
                [
                    FormField(
                        "Razão social",
                        Input(value=app.state.company, on_change=set_company, key="company"),
                        help="Aparece nas notas fiscais.",
                    ),
                    FormField(
                        "Domínio",
                        Input(value="acme.com", key="domain"),
                        error=app.state.errors.get("domain"),
                    ),
                ],
                subtitle="Dados usados em documentos e emails.",
            ),
            FormSection(
                "Notificações",
                [
                    FormField(
                        "Resumo por email",
                        Input(value=app.state.notify, key="notify"),
                        help="diário, semanal ou nunca",
                        span="full",
                    )
                ],
            ),
        ],
        actions=[
            Button(label="Cancelar", on_click=lambda: None, key="cancel"),
            Button(label="Salvar", on_click=lambda: None, key="save"),
        ],
    )
```

`FormField(label, control, help=..., error=..., span=...)`. O rótulo, o texto de
ajuda e a linha de erro nascem posicionados e com a cor certa; `error` não-vazio
troca a cor e mostra a linha. `span="full"` faz o campo ocupar a largura inteira
da seção.

!!! tip "Dica — `form_page` e `settings_page` renderizam igual"
    `settings_page` **é** `form_page` com a assinatura mais estreita: só aceita
    `sections`, nunca campos soltos. Use `form_page` quando a tela é um
    formulário simples (`fields=[...]` numa grade só) e `settings_page` quando os
    campos sempre pertencem a um grupo. O resultado visual é o mesmo — a
    diferença é o que o tipo deixa você escrever.

    A barra de ações fica alinhada à direita no desktop e **empilha no celular
    com a última ação da lista em cima** (`flex-direction: column-reverse`).
    Ponha a ação primária por último em `actions=`, como o exemplo faz com
    `[Cancelar, Salvar]`.

## Passo 5 — O shell que costura tudo

```python
def view(app: App[State]) -> Widget:
    """Render the console."""

    def navigate(value: str) -> None:
        app.set_state(
            lambda s: (setattr(s, "tab", value), setattr(s, "sidebar_open", False))[0]
        )

    def toggle() -> None:
        app.set_state(lambda s: setattr(s, "sidebar_open", not s.sidebar_open))

    bodies = {
        "overview": _overview,
        "users": lambda: _users(app),
        "settings": lambda: _settings(app),
    }
    return admin_shell(
        title="Console ACME",
        brand="ACME",
        nav=NAV,
        active=app.state.tab,
        on_navigate=navigate,
        sidebar_open=app.state.sidebar_open,
        on_toggle_sidebar=toggle,
        actions=[Button(label="Sair", on_click=lambda: None, key="logout")],
        footer=Text(content="ana@acme.com", key="signed-in", style=Style(font_size=12.0)),
        body=bodies[app.state.tab](),
    )
```

Um `dict` de funções e um `str` no estado — é toda a "navegação". O `body` é o
resultado da tela ativa.

!!! tip "Dica — feche o drawer ao navegar"
    Repare que `navigate` também escreve `sidebar_open = False`. No celular a
    sidebar é um drawer sobreposto; sem essa linha ele fica aberto por cima do
    conteúdo que o usuário acabou de pedir.

## Passo 6 — Executar

```bash
tempestweb dev --mode server --path examples/admin-console   # Modo B
tempestweb dev --mode wasm   --path examples/admin-console   # Modo A
```

O que você vê no desktop (≥1024px): sidebar fixa à esquerda, KPIs em quatro
colunas, seção de gráfico ocupando a linha, tabela com cabeçalho fixo.

No celular (≤430px): a sidebar vira drawer atrás de um burger no header, os KPIs
empilham, o formulário cai para uma coluna, a barra de ações empilha com a ação
primária em cima, e a tabela rola horizontalmente dentro do próprio cartão — a
página nunca rola de lado.

!!! check "Verificado no browser"
    Os comportamentos acima foram conferidos no Chromium contra o Modo B real,
    em 1440×900 e 390×844: burger ausente no desktop e presente no mobile,
    drawer com scrim, fechamento automático ao navegar, tabela com rolagem
    própria, busca fazendo o round-trip pelo WebSocket (`5 de 5` → `1 de 5`),
    e zero mensagem no console.

## Recapitulando

Neste tutorial você montou um painel administrativo inteiro e aprendeu:

- 💡 **`admin_shell`** entrega header + sidebar colapsável + área de conteúdo; o
  `bool` de aberto/fechado é seu.
- 💡 **`dashboard_page`** recebe `Kpi` e `Section` — número de colunas e
  breakpoints não são decisão sua.
- 💡 **`list_page`** entrega toolbar de busca, tabela, paginação e estado vazio;
  uma célula pode ser um widget.
- 💡 **`settings_page`** posiciona rótulo, ajuda e erro a partir de `FormField`.
- 💡 O preset **renderiza, o app decide**: filtrar, paginar e validar continuam
  sendo código seu — e é por isso que a mesma tela serve para um `WHERE` no banco.
- 💡 **261 linhas** contra **716** do mesmo painel montado à mão, e essas 261 são
  responsivas.

---

## Próximos passos

- Leia [Telas prontas (presets)](../presets.md) para a referência dos cinco
  presets e de todos os registros.
- Compare com o [Dashboard App Shell](dashboard-shell.md), o mesmo painel montado
  widget a widget.
- Veja [Componentes prontos](../components.md) para o catálogo que você usa
  dentro de uma `Section`.
