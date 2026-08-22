# 1. A árvore de view

A unidade básica do tempestweb é a função `view()`. Ela recebe o **app** (que
expõe o estado atual) e devolve uma **árvore de widgets**. Não há JSX, não há
template — é Python puro, tipado.

## A função `view`

```python
from tempest_core import App, Column, Style, Text, Widget
from tempest_core import Edge


def view(app: App[CounterState]) -> Widget:  # (1)!
    """Render the counter UI from the current state."""
    return Column(  # (2)!
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),  # (3)!
        ],
    )
```

1. `view` recebe `App[CounterState]` — o handle tipado do estado — e **sempre**
   devolve um `Widget`. Tipo de entrada e saída são parte do contrato.
2. `Column` é um container flex vertical. `Row` é o horizontal. Ambos recebem
   `style` e `children`.
3. `Text` mostra texto. `app.state.value` lê o estado atual — a view é uma
   **função do estado**.

!!! note "A view é pura"
    `view()` **não muta nada**. Ela lê `app.state` e descreve a UI que
    corresponde àquele estado. Mudar o estado é trabalho dos handlers (próxima
    página) — a view só desenha.

## Os widgets do counter

O counter usa quatro tipos de widget, todos vindos do core:

| Widget | O que é | Props principais |
|---|---|---|
| `Column` | Container flex vertical | `style`, `children` |
| `Row` | Container flex horizontal | `style`, `children` |
| `Text` | Texto | `content`, `style`, `key` |
| `Button` | Botão clicável | `label`, `on_click`, `style`, `key` |

## A `key`: identidade estável

Repare no `key="label"`. A `key` dá ao widget uma **identidade estável** entre
rebuilds. Quando o estado muda e a view roda de novo, o reconciliador usa a `key`
para casar o widget novo com o antigo — e assim emitir um patch mínimo (mudar só
o texto) em vez de recriar o nó.

```python
Text(content=f"Count: {app.state.value}", key="label")
```

!!! tip "Quando dar `key`"
    Dê `key` a qualquer widget que **persiste entre rebuilds** e cujo conteúdo
    muda (o texto da contagem, os botões). Itens de lista dinâmica também querem
    `key` estável. Sem `key`, a reconciliação cai no casamento posicional.

## Estilo é um objeto tipado

`Style` é um objeto Pydantic — não uma string CSS. Você declara intenção e o
cliente traduz para CSS:

```python
Style(gap=8.0, padding=Edge.all(16))  # gap: 8px; padding: 16px;
```

- `gap=8.0` → `gap: 8px` no container flex.
- `Edge.all(16)` → `padding: 16px 16px 16px 16px`.

!!! info "Style → CSS é quase identidade"
    O `Style` foi desenhado copiando o vocabulário do CSS (flexbox, box model,
    tipografia). A tradução vive no cliente (`client/style.js`) e é compartilhada
    pelos dois modos. Detalhe completo no [contrato de fronteira](../advanced/wire-contract.md#3-style).

## A árvore completa do counter

Juntando container, texto e botões:

```python
from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core import Edge


def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state."""
    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", key="dec"),  # on_click vem na página 2
                    Button(label="+", key="inc"),
                ],
            ),
        ],
    )
```

Isso produz a árvore (IR) que o reconciliador serializa para o cliente — o
formato exato está fixado em
[`tests/fixtures/node_initial.json`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/tests/fixtures/node_initial.json).

## Responsividade: `app.media`

O browser é dono do viewport; a `view` lê ele em `app.media`. O cliente reporta
tamanho, densidade, dark mode do OS e orientação na montagem e a cada mudança,
nos **três** modos — então escolher layout por largura é só um `if`:

```python
from tempest_core import App, Column, Row, Text, Widget


def view(app: App[object]) -> Widget:
    """Uma linha no desktop, uma coluna no telefone."""
    campos = [
        Text(content="Nome", key="rotulo-nome"),
        Text(content="E-mail", key="rotulo-email"),
    ]
    if app.media.width >= 768:
        return Row(style=None, children=campos)
    return Column(style=None, children=campos)
```

`app.media` traz `width`, `height`, `device_pixel_ratio`, `text_scale_factor`,
`platform_dark_mode` e `orientation`. Mudança dispara rebuild como qualquer
mutação de estado — a `view` re-roda e o reconciliador emite os patches mínimos.

!!! tip "`height` é o único jeito de limitar uma moldura ao viewport"
    `Style` não tem `100vh`. Um `Scaffold(scroll=True)` só rola de verdade
    quando a coluna em volta dele é limitada, e a única medida disponível para
    limitar é `app.media.height`. Sem ela a página inteira rola e a `app_bar` /
    `bottom_bar` rolam junto — exatamente o que um scaffold existe para evitar.

!!! note "Antes do primeiro report, tudo é zero"
    O default de `MediaQueryData` tem `width` e `height` em `0.0`. O primeiro
    report chega na montagem, então a primeira pintura já é responsiva — mas um
    `view` que divide por `width` precisa tratar o zero.

## Recap

- `view(app) -> Widget` é uma **função pura do estado**.
- Widgets (`Column`, `Row`, `Text`, `Button`) são objetos tipados do core.
- `key` dá **identidade estável** para a reconciliação emitir patches mínimos.
- `Style` é um objeto tipado que vira CSS no cliente.

Agora os botões precisam **fazer algo**. Vamos para
[estado e handlers](state.md). 🚀
