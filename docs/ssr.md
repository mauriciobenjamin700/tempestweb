# SSR estático — `render_to_html`

Até aqui o tempestweb rodava a mesma árvore de widgets de dois jeitos: no browser
(**Modo A**, WASM) e no servidor com cliente fino (**Modo B**, WebSocket/SSE).
Ambos são **interativos** e dependem de JavaScript.

Agora existe um terceiro alvo: **HTML estático**. A mesma árvore tipada vira uma
**string de HTML** no servidor — sem JavaScript, sem DOM, sem runtime. É a tese
"uma árvore, N renderizadores" levada ao fim: o HTML é só mais um renderizador
folha, ao lado do cliente DOM. 🚀

!!! info "Quando usar SSR"
    Use `render_to_html` quando você precisa de **first paint instantâneo**,
    **SEO**, e-mails em HTML, ou uma página que funciona **sem JS**. Para telas
    ricas e interativas, continue nos Modos A/B. Os dois convivem: você pode
    renderizar o casco no servidor e hidratar com o cliente depois.

## Um exemplo mínimo e completo

Escreva uma árvore tipada e transforme em HTML:

```python
from tempest_core import Column, Text, Button, Style
from tempest_core.style import Edge
from tempestweb.html import render_to_html


def view() -> Column:
    """Build a tiny typed page."""
    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content="Olá, mundo!"),
            Button(label="Clique"),
        ],
    )


html: str = render_to_html(view())
print(html)
```

O resultado é uma **string de HTML** pronta para servir:

```html
<div style="display: flex; flex-direction: column; gap: 8px; padding: 16px 16px 16px 16px"><span>Olá, mundo!</span><button>Clique</button></div>
```

Repare: um `Column` virou `<div>` com `display: flex`, o `Text` virou `<span>` e o
`Button` virou `<button>` — o **mesmo** mapeamento que o cliente DOM faz em
`client/dom.js`, e o **mesmo** CSS que o cliente geraria a partir do `Style`.

## Uma página completa

`render_to_html` devolve um **fragmento**. Para uma página `<!doctype html>`
inteira, use `render_document`:

```python
from tempest_core import Column, Text
from tempestweb.html import render_document


def view() -> Column:
    """Build the page body."""
    return Column(children=[Text(content="Página renderizada no servidor")])


page: str = render_document(
    view(),
    title="Minha página",
    lang="pt-BR",
    htmx=True,          # injeta o <script> do htmx
    css_reset=True,     # injeta um reset de CSS mínimo
)
```

Você recebe um documento auto-contido com `<meta charset>`, `<title>` escapado,
o reset opcional e — com `htmx=True` — a tag de script do htmx.

!!! note "Entrega do htmx"
    Com `htmx=True` a página aponta para o htmx via CDN (`unpkg.com`). Um ciclo
    futuro do SDK vai servir o htmx localmente; por isso a URL é apenas uma
    string parametrizável na saída, nunca uma dependência rígida daqui.

## HTML semântico com `tag` e `attrs`

Desde o `tempest-core` 0.9.0, **todo** `Widget` aceita dois campos opcionais:

- `tag: str | None` — troca a tag HTML gerada (por exemplo `<nav>` no lugar de
  `<div>`).
- `attrs: dict[str, str]` — atributos HTML arbitrários: `id`, `class`, `data-*`,
  `aria-*` e, claro, `hx-*` do htmx.

Ambos fluem pelo `build()` e são honrados pelo renderizador de HTML:

```python
from tempest_core import Container, Column, Text
from tempestweb.html import render_to_html


def nav() -> Container:
    """Build a semantic <nav> with an htmx attribute."""
    return Container(
        tag="nav",
        attrs={"aria-label": "primary", "class": "topbar"},
        child=Column(
            tag="ul",
            children=[
                Container(tag="li", child=Text(tag="a", content="Início")),
                Container(tag="li", child=Text(tag="a", content="Docs")),
            ],
        ),
    )


print(render_to_html(nav()))
```

```html
<nav aria-label="primary" class="topbar"><ul style="display: flex; flex-direction: column"><li><a>Início</a></li><li><a>Docs</a></li></ul></nav>
```

!!! tip "A `tag` muda o elemento, não o layout"
    O `<ul>` acima ainda é um `Column`, então mantém `display: flex` pela sua
    natureza — a `tag` troca o elemento HTML, não a semântica de layout.

## Segurança: tudo é escapado

Conteúdo de texto e valores de atributo passam **sempre** por escape:

```python
from tempest_core import Text
from tempestweb.html import render_to_html

render_to_html(Text(content="<script>alert(1)</script>"))
# -> "<span>&lt;script&gt;alert(1)&lt;/script&gt;</span>"
```

!!! danger "Guarda contra injeção de atributo"
    Além de escapar os **valores**, o renderizador valida as **chaves** de
    `attrs` contra `^[a-zA-Z][a-zA-Z0-9:_-]*$`. Uma chave inválida (por exemplo
    `"onload x"` ou `"a>b"`) levanta `ValueError` — assim ninguém contrabandeia
    markup por uma chave maliciosa.

## Componentes também funcionam

Um `Component` é expandido pelo `build()` antes do render, então SSR funciona com
suas abstrações de alto nível sem nenhuma mudança:

```python
from tempest_core import Component, Container, Column, Text, Widget
from tempestweb.html import render_to_html


class NavBar(Component):
    """A composite that expands to a semantic nav tree."""

    items: list[str]

    def render(self) -> Widget:
        """Lower the nav into primitive widgets with semantic tags."""
        return Container(
            tag="nav",
            child=Column(
                tag="ul",
                children=[
                    Container(tag="li", child=Text(tag="a", content=item))
                    for item in self.items
                ],
            ),
        )


print(render_to_html(NavBar(items=["Início", "Docs"])))
```

## Limitações conhecidas

!!! warning "Icon e Canvas no SSR estático"
    `Icon` precisa de JavaScript para injetar o glifo SVG e `Canvas` é uma
    superfície de desenho imperativa — nenhum dos dois tem forma **estática**
    útil. No SSR eles viram placeholders vazios (`<span data-tw-type="Icon">`
    `</span>` e `<canvas></canvas>`) em vez de quebrar. Use-os nos modos
    interativos (A/B).

## Recapitulando

- `render_to_html(widget)` transforma uma árvore tipada em um **fragmento** de
  HTML estático, reusando `tempest_core.build()`.
- `render_document(...)` envolve a árvore em uma **página** `<!doctype html>`
  completa, com `title`, `lang`, `head` extra, reset de CSS e htmx opcionais.
- O CSS é **byte-idêntico** ao do cliente DOM (`style_to_css` é um port fiel de
  `client/style.js`), então servidor e cliente concordam.
- `tag` e `attrs` (novos no `tempest-core` 0.9.0) deixam você emitir **HTML
  semântico e pronto para htmx** a partir de uma árvore tipada.
- Todo texto e atributo é **escapado**; chaves de `attrs` inválidas levantam
  `ValueError`.
- `Icon`/`Canvas` são placeholders no SSR estático — uma limitação documentada,
  não um crash.
