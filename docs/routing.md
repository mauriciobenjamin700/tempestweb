# Roteamento e navegação

!!! abstract "O que você vai aprender"
    Como um app tempestweb navega entre **telas**: a **pilha de navegação**
    (`NavStack`), como definir e renderizar rotas, como navegar
    (`push`/`pop`/`replace`/`reset`), como a URL do browser fica **em sincronia**
    com a pilha (deep links + botão voltar) e como fazer **guardas/redirect**. 🚀

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
  (voltar/avançar), o cliente reporta o **caminho** do documento. O runtime
  resolve o caminho para uma pilha (`routes_from_path`) e chama `app.reset` — então
  a `view` re-renderiza a tela linkada, com a pilha de retorno já montada.
- **view → URL.** Quando o seu app navega imperativamente (`push`/`pop`/`reset`), o
  runtime emite o novo caminho e o cliente faz `history.pushState` — então
  voltar/avançar e bookmarks continuam corretos.

```text
  URL "/shop/item"  ──(load / popstate)──►  routes_from_path  ──►  app.reset
                                                                      │
                                                          view(app) re-renderiza
                                                                      │
  app.push(Route(name="/checkout"))  ──►  runtime emite "/checkout"  ──►  pushState
```

!!! info "`routes_from_path` monta a pilha de retorno"
    Um caminho `"/a/b"` abre a pilha `["/", "/a", "/a/b"]` — segmentos
    **cumulativos**. Assim, chegar por deep link em `/shop/item` ainda deixa o
    usuário voltar para `/shop` e depois para `/`. A raiz (`"/"`) vira a pilha só
    com a rota raiz.

!!! check "Feito quando"
    Você abre `http://127.0.0.1:8000/about` direto e vê a tela "Sobre"; clica em
    "Detalhes" e a URL vira `/details`; o **botão voltar do browser** te leva de
    volta para `/about`. Tudo com a mesma `view`, sem código de histórico no app.

---

## 4. Path params: identidade codificada no nome

O tempestweb **não** tem padrões de rota com placeholders (nada de `/users/:id`
com extração automática). A identidade vai **no próprio nome** da rota — é assim
que o core modela, e é o que sobrevive na URL. Você navega com o caminho completo
e faz o parse do segmento na `view`:

```python
from __future__ import annotations

from tempest_core import App, Route, Text, Widget


def open_user(app: App, user_id: int) -> None:
    """Navega para a página de um usuário específico."""
    app.push(Route(name=f"/users/{user_id}"))  # (1)!


def user_screen(route_name: str) -> Widget:
    """Extrai o id do nome da rota e renderiza."""
    user_id = route_name.removeprefix("/users/")  # (2)!
    return Text(content=f"Usuário #{user_id}", key="user")


def view(app: App) -> Widget:
    """Despacha por prefixo de rota."""
    name = app.nav.top.name
    if name.startswith("/users/"):
        return user_screen(name)
    return Text(content="Início", key="home")
```

1.  O id vira parte do caminho — e portanto da URL (`/users/42`) e do deep link.
2.  Sem placeholder mágico: você fatia a string do nome. Um `startswith`/
    `removeprefix` cobre o caso comum.

!!! warning "`Route.params` NÃO vai para a URL"
    Você **pode** passar dados na rota via `Route(name="/users", params={"id": 42})`,
    e ler em `app.nav.top.params["id"]`. Mas esses `params` vivem **só em memória**:
    o runtime só serializa o **`name`** da rota no histórico do browser (a URL). Ao
    recarregar a página ou entrar por deep link, `params` volta **vazio**. Por isso,
    para identidade que precisa sobreviver a um reload, **codifique no `name`** (como
    acima) — não no `params`.

---

## 5. Query params

!!! danger "Gap: query params não chegam ao Python"
    O tempestweb **não** expõe os query params (`?q=...&page=2`) ao app hoje. A
    ponte URL→navegação reporta apenas `location.pathname` — a query string
    (`location.search`) é descartada antes de chegar ao Python. Não há API tipada
    de query param; **não invente uma**.

O contorno é o mesmo dos path params: se um valor precisa estar na URL e
sobreviver a um reload, **coloque-o no caminho** (o `name` da rota) e faça o parse
você mesmo. Para estado que **não** precisa estar na URL (um filtro efêmero, uma
aba selecionada), guarde no seu `State` normal — não na rota.

```python
from tempest_core import App, Route


def search(app: App, term: str, page: int) -> None:
    """Coloca a busca no caminho para que ela sobreviva a um reload."""
    app.push(Route(name=f"/search/{term}/{page}"))
    # depois, na view: name.removeprefix("/search/").split("/") → [term, page]
```

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
  resolvem via `routes_from_path`; navegação imperativa faz `pushState`.
- **Path params** vão no `name` da rota (você faz o parse). `Route.params` é só em
  memória — **não** sobrevive a reload/URL.
- **Query params não são expostos** hoje (gap conhecido); codifique no caminho ou
  guarde no `State`.
- **Guardas/redirect** vêm do `route_guard` (`tempestweb.observability`): uma
  função pura `rota_pedida -> rota_efetiva` que você aplica na `view`.

Quer ver tudo junto? O [exemplo de navegação com drawer](examples/router-drawer.md)
compõe `NavStack`, `Navigator`, `RouteDrawer` e `Breadcrumb` num app completo. 🚀
