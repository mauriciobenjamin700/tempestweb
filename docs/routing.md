# Roteamento e navegação

!!! abstract "O que você vai aprender"
    Como um app tempestweb navega entre **telas**: a **pilha de navegação**
    (`NavStack`), como definir e renderizar rotas, como navegar
    (`push`/`pop`/`replace`/`reset`), como a URL do browser fica **em sincronia**
    com a pilha (deep links + botão voltar), como **query e path params** fazem
    round-trip pela URL, e como fazer **guardas/redirect**. 🚀

A navegação no tempestweb não é um roteador separado com sua própria árvore: é a
**mesma** `view(app)` produzindo uma árvore diferente conforme a rota no topo da
pilha. O reconciliador difere o resultado em patches — sem tipo de patch novo,
sem mágica. É o modelo do `go_router` (Flutter) e do React Navigation. ✅

---

## Por que uma pilha

Um app de uma tela só é raro. Assim que você tem "Home → Detalhes → Voltar", você
tem uma **pilha**: uma lista ordenada de rotas, da raiz até a tela visível. O
tempestweb modela isso com dois valores simples, importados do
[`tempest-core`](https://pypi.org/project/tempest-core/):

- **`Route`** — um destino: um `name` (string tipo caminho, ex.: `"/"`,
  `"/details"`) e um dicionário `params` opcional.
- **`NavStack`** — a pilha ordenada de rotas. O topo (`stack.top`) é a tela
  visível; a base é a raiz.

O `App` **é dono** de uma `NavStack` (em `app.nav`) e a muta por você através de
`push`/`pop`/`replace`/`reset`, cada um agendando um rebuild. O seu `view()` lê
`app.nav.top` e decide qual tela construir.

---

## 1. Definir rotas: `view` lê `app.nav.top`

Não existe uma "tabela de rotas" declarativa. Você **despacha** na `view` pelo
nome da rota no topo da pilha. Este é o [`examples/router_demo/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/router_demo/app.py):

```python
from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.navigation import Route
from tempest_core.style import Edge


@dataclass
class RouterState:
    """A tela vem de app.nav, não do estado."""


def make_state() -> RouterState:
    """Estado inicial."""
    return RouterState()


def view(app: App[RouterState]) -> Widget:
    """Renderiza a tela da rota no topo da pilha."""
    route = app.nav.top.name  # (1)!
    if route == "/details":
        screen = Text(content="Tela de detalhes", key="screen")
    elif route == "/about":
        screen = Text(content="Tela sobre", key="screen")
    else:
        screen = Text(content="Tela inicial", key="screen")

    def go(path: str) -> None:
        app.push(Route(name=path))  # (2)!

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Rota: {route}", key="route"),
            screen,
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="Detalhes", on_click=lambda: go("/details"), key="d"),
                    Button(label="Sobre", on_click=lambda: go("/about"), key="a"),
                ],
            ),
        ],
    )
```

1.  `app.nav.top` é a `Route` visível; `.name` é o identificador que você usa para
    escolher a tela.
2.  Navegar é só empurrar uma rota na pilha. O rebuild é agendado sozinho.

!!! tip "O `name` é um caminho, não um enum"
    Use nomes tipo caminho (`"/"`, `"/settings"`, `"/shop/item"`). Isso não é só
    convenção: é **exatamente** o que aparece na URL do browser (próxima seção), e
    o que o deep-link resolve de volta para a pilha.

---

## 2. Navegar: `push` · `pop` · `replace` · `reset`

O `App` expõe quatro operações sobre a pilha. Todas agendam um rebuild:

| Método | Faz | Retorno |
|---|---|---|
| `app.push(route)` | Empurra uma rota no topo (avança uma tela). | `None` |
| `app.pop()` | Remove o topo (volta uma tela). No-op na raiz. | `bool` |
| `app.replace(route)` | Troca a rota do topo **sem** mudar a profundidade. | `None` |
| `app.reset(stack)` | Substitui a pilha inteira (ex.: deep link, logout). | `None` |

Além disso, você lê a pilha:

- `app.nav.top` → a `Route` visível.
- `app.nav.stack` → a lista completa de rotas (raiz → topo).
- `app.nav.can_pop` → `True` quando dá para voltar (mais de uma rota na pilha).

```python
from tempest_core import App, Route, Widget


def go_to_details(app: App) -> None:
    """Avança para os detalhes."""
    app.push(Route(name="/details"))


def go_back(app: App) -> None:
    """Volta uma tela — se houver para onde voltar."""
    if app.nav.can_pop:
        app.pop()


def open_login_fresh(app: App) -> None:
    """Zera a pilha na tela de login (ex.: após logout)."""
    app.reset([Route(name="/login")])
```

!!! note "`pop` na raiz é um no-op seguro"
    Com uma única rota na pilha, `app.pop()` retorna `False` e **não** esvazia a
    pilha — um app sempre tem uma tela para renderizar. Cheque `app.nav.can_pop`
    antes de mostrar um botão "voltar".

!!! tip "Botão voltar pronto"
    Renderize o botão voltar só quando `app.nav.can_pop` for verdadeiro:

    ```python
    from tempest_core import Button


    def back_button(app: App) -> Button | None:
        """Um botão voltar, ou None na raiz."""
        if not app.nav.can_pop:
            return None
        return Button(label="← Voltar", on_click=app.pop, key="back")
    ```

---

## 3. URL do browser: deep links e voltar/avançar

Aqui está a parte que torna o app "web de verdade": **a URL fica em sincronia com
a pilha**, nos três modos (WASM, servidor e transpile). O browser é dono da URL; o
app Python é dono da pilha; o tempestweb liga os dois:

- **URL → view.** Ao carregar (um deep link / bookmark) e a cada `popstate`
  (voltar/avançar), o cliente reporta a **URL** do documento (caminho + query). O
  runtime resolve para uma pilha (`path_to_routes`) e chama `app.reset` — então
  a `view` re-renderiza a tela linkada, com a pilha de retorno já montada e os
  query params no `params` do topo.
- **view → URL.** Quando o seu app navega imperativamente (`push`/`pop`/`reset`), o
  runtime serializa o route do topo (`route_to_path`, incluindo os `params` como
  query string) e o cliente faz `history.pushState` — então
  voltar/avançar e bookmarks continuam corretos.

```text
  URL "/shop/item?ref=home"  ──(load / popstate)──►  path_to_routes  ──►  app.reset
                                                                            │
                                                                view(app) re-renderiza
                                                                            │
  app.push(Route("/checkout", params={"cart":"42"}))  ──►  route_to_path
                                                            "/checkout?cart=42"  ──►  pushState
```

!!! info "A pilha de retorno é cumulativa"
    Um caminho `"/a/b"` abre a pilha `["/", "/a", "/a/b"]` — segmentos
    **cumulativos**. Assim, chegar por deep link em `/shop/item` ainda deixa o
    usuário voltar para `/shop` e depois para `/`. A raiz (`"/"`) vira a pilha só
    com a rota raiz. O mapeamento URL↔pilha vive em
    `tempestweb.runtime.routing` (`path_to_routes` / `route_to_path`) e é
    espelhado no cliente do Modo C — o comportamento é **idêntico nos três modos**.

!!! check "Feito quando"
    Você abre `http://127.0.0.1:8000/about` direto e vê a tela "Sobre"; clica em
    "Detalhes" e a URL vira `/details`; o **botão voltar do browser** te leva de
    volta para `/about`. Tudo com a mesma `view`, sem código de histórico no app.

---

## 4. Query params: `Route.params` faz round-trip pela URL

Passe dados na rota via `params` e eles **aparecem na URL como query string** e
**sobrevivem a reload/deep-link** — nos três modos. `app.push(Route("/shop",
params={"ref": "home"}))` mostra `/shop?ref=home` na barra; ao voltar (deep link
ou back/forward), `app.nav.top.params` traz de volta `{"ref": "home"}`.

```python
from __future__ import annotations

from tempest_core import App, Column, Text, Widget


def open_shop(app: App) -> None:
    """Navega para a loja com um parâmetro de origem."""
    app.push(Route(name="/shop", params={"ref": "home"}))  # (1)!


def view(app: App) -> Widget:
    """Lê os params do route no topo da pilha."""
    top = app.nav.top
    if top.name == "/shop":
        ref = top.params.get("ref", "direto")               # (2)!
        return Text(content=f"Loja (via: {ref})", key="shop")
    return Text(content="Início", key="home")
```

1.  Isso vira a URL `/shop?ref=home` (`route_to_path` serializa `params` como query
    string). Recarregar ou compartilhar o link reconstrói o mesmo route.
2.  Ao chegar por URL, `path_to_routes` anexa a query parseada ao `params` do route
    do topo. Você lê direto de `app.nav.top.params`.

!!! info "Valores de query/path são **strings**"
    A URL só carrega texto, então tudo em `app.nav.top.params` (e o que o
    `match_path` extrai) chega como **`str`**. Tipagem rica é responsabilidade do
    app: converta na `view` (`int(params["page"])`, etc.).

---

## 5. Path params: `:name` com `match_path`

Para identidade no **caminho** (ex.: `/users/42`), navegue com o valor no `name` e
extraia com o `match_path` — o casador de padrões `:name` embutido:

```python
from __future__ import annotations

from tempest_core import App, Route, Text, Widget
from tempestweb.runtime.routing import match_path  # (1)!


def open_user(app: App, user_id: int) -> None:
    """Navega para a página de um usuário específico."""
    app.push(Route(name=f"/users/{user_id}"))       # /users/42


def view(app: App) -> Widget:
    """Despacha por padrão de rota, extraindo o :id."""
    params = match_path("/users/:id", app.nav.top.name)  # (2)!
    if params is not None:
        return Text(content=f"Usuário #{params['id']}", key="user")
    return Text(content="Início", key="home")
```

1.  `match_path` vive em `tempestweb.runtime.routing`.
2.  `match_path("/users/:id", "/users/42")` → `{"id": "42"}`; um caminho que não
    casa (contagem de segmentos diferente ou literal diferente) → `None`. A query
    string, se houver, é **ignorada** aqui — combine com `app.nav.top.params` para
    lê-la.

!!! tip "Path params + query params juntos"
    Os dois se complementam: o `match_path` extrai os segmentos do **caminho**
    (`:id`), e `app.nav.top.params` traz a **query string**. Ex.: em
    `/users/42?tab=posts`, `match_path("/users/:id", app.nav.top.name)` dá
    `{"id": "42"}` e `app.nav.top.params` dá `{"tab": "posts"}`.

---

## 6. Guardas e redirect

Precisa proteger uma tela (ex.: exigir login antes do `/dashboard`)? O tempestweb
traz um **route guard** pronto em `tempestweb.observability`: dado o estado de
autenticação, ele mapeia a rota **pedida** para a rota que deve **de fato**
renderizar. Este é o coração do [`examples/auth-jwt/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/auth-jwt/app.py):

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Text, Widget
from tempestweb.observability import AuthStore, create_auth_store, route_guard


@dataclass
class GateState:
    """Estado que carrega o AuthStore."""

    store: AuthStore = field(default_factory=create_auth_store)


def make_state() -> GateState:
    """Estado inicial."""
    return GateState()


def view(app: App[GateState]) -> Widget:
    """Renderiza a tela protegida ou redireciona para o login."""
    guard = route_guard(app.state.store, redirect_to="/login")  # (1)!
    effective_route = guard(app.nav.top.name)                    # (2)!

    if effective_route == "/dashboard":
        return Text(content="Dashboard protegido", key="dash")
    return Text(content="Faça login", key="login")
```

1.  `route_guard(store, redirect_to=...)` devolve uma função pura
    `Callable[[str], str]`.
2.  Ela retorna a rota pedida quando autenticado (ou quando já é o alvo do
    redirect), senão `redirect_to`. Você renderiza a tela **efetiva**, não a pedida.

!!! info "Guarda é uma função pura na `view`, não um middleware"
    O `route_guard` não intercepta a navegação nem faz `pushState` — ele só decide
    **o que renderizar**. Isso mantém tudo dentro da `view` (uma árvore para o
    estado atual) e funciona igual nos três modos. Para guardas próprias (papéis,
    feature flags), escreva a sua função `str -> str` seguindo o mesmo formato.

!!! tip "Redirect imperativo"
    Se você prefere **trocar a pilha** em vez de só renderizar outra tela (para a
    URL refletir o redirect), chame `app.reset` no handler:

    ```python
    from tempest_core import App, Route


    def require_auth(app, authenticated: bool) -> None:
        """Manda para o login quando não autenticado."""
        if not authenticated and app.nav.top.name != "/login":
            app.reset([Route(name="/login")])
    ```

---

## Recap

- A navegação é uma **pilha** (`app.nav`, uma `NavStack` de `Route`). A `view` lê
  `app.nav.top.name` e constrói a tela — não há tabela de rotas separada.
- Navegue com `app.push` / `app.pop` / `app.replace` / `app.reset`; leia
  `app.nav.top`, `app.nav.stack` e `app.nav.can_pop`.
- A **URL fica em sincronia** com a pilha nos três modos: deep link e voltar/avançar
  resolvem via `path_to_routes`; navegação imperativa serializa com `route_to_path`
  e faz `pushState`.
- **Query params fazem round-trip:** `Route.params` vira query string na URL e
  **sobrevive** a reload/deep-link; leia em `app.nav.top.params`.
- **Path params** saem do padrão `:name` com
  `match_path("/users/:id", app.nav.top.name)` → `{"id": "42"}` (ou `None`).
- **Valores de query/path são sempre `str`** — tipagem rica é trabalho do app.
- **Guardas/redirect** vêm do `route_guard` (`tempestweb.observability`): uma
  função pura `rota_pedida -> rota_efetiva` que você aplica na `view`.

Quer ver tudo junto? O [exemplo de navegação com drawer](examples/router-drawer.md)
compõe `NavStack`, `Navigator`, `RouteDrawer` e `Breadcrumb` num app completo. 🚀
