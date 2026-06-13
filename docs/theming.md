# Tema (Material 3)

Seus widgets já nascem bonitos. Um `Button` cru vira um **botão Material 3
preenchido** — pílula, cor primária, _state layer_ no hover, elevação. Um `Input`
vira um **campo outlined** com foco animado. Você não escreve **nenhum** CSS para
isso. ✨

Esse é o **tema base sempre-ligado** que chegou na 0.6.0: uma folha de estilo
Material 3 (`client/theme.js`) injetada **uma vez**, no _mount_, que dá tipografia,
espaçamento e controles acentuados sensatos a todo app — mesmo o que você nunca
estilizou. E quando você quer fugir do padrão, o `Style` inline do widget **sempre
ganha**.

## O mínimo: confie no tema base

Não há nada a configurar. Escreva o app normalmente; o tema base entra sozinho.

```python
from dataclasses import dataclass

from tempest_core import App, Button, Column, Input, Text, Widget


@dataclass
class State:
    name: str = ""


def make_state() -> State:
    return State()


def view(app: App[State]) -> Widget:
    def set_name(event) -> None:
        app.set_state(lambda s: setattr(s, "name", event.value))

    return Column(
        children=[
            Text(content="Como você se chama?"),
            Input(value=app.state.name, on_change=set_name, key="name"),
            Button(label=f"Olá, {app.state.name or 'mundo'}!", key="hello"),
        ],
    )
```

Rode nos dois modos — o visual é idêntico:

```bash
tempestweb run --mode wasm     # Python no browser (Pyodide)
tempestweb run --mode server   # Python no servidor (FastAPI + WebSocket)
```

O que você acabou de ganhar de graça:

- **Tipografia** — a família `Roboto`/`system-ui` em vez do Times New Roman do
  navegador, em `Text`, `Button` e `Input`.
- **Botão** — pílula preenchida com cor primária, _state layer_ translúcido no
  hover/foco/clique e elevação animada.
- **Campo** — `Input` outlined arredondado, cuja borda engrossa e recolore para a
  cor primária no foco.
- **Checkbox** — caixa dimensionada e acentuada com a cor primária.

!!! info "Por que uma folha de estilo, e não `Style` inline?"
    CSS inline não consegue expressar `:hover`, `:focus-visible`, `:active` ou
    `:disabled` — justamente os estados que fazem um controle parecer moderno. Eles
    moram na folha base, chaveados pelo atributo `data-tw-type` que o renderizador
    DOM carimba em cada elemento.

## Sobrescrevendo o tema: o `Style` inline ganha

A folha base é um **piso, não uma jaula**. Como ela não usa `!important` e o `Style`
do widget vira `style=""` inline no elemento, suas declarações vencem a cascata. Os
estados de interação (hover/foco) continuam funcionando por cima.

```python
from tempest_core import Button, Style
from tempest_core.style import Color

# A pílula, a tipografia e o state layer continuam — só a cor muda.
Button(
    label="Comprar agora",
    style=Style(background=Color.from_hex("#0b57d0")),
    key="buy",
)
```

!!! tip "Rebrand global por tokens"
    Os tokens do tema são _custom properties_ CSS em `:root` (`--tw-primary`,
    `--tw-surface`, `--tw-outline`, …). Para retematizar a UI inteira sem tocar em
    nenhum widget, sobreponha-os de um `<style>` próprio na sua página host:

    ```css
    :root { --tw-primary: #0b57d0; }
    ```

## Elevação com `Style(shadow=...)`

Na 0.6.0, um `Shadow` no `Style` de um widget vira um **`box-shadow` CSS de
verdade** na web — a mesma elevação que os renderizadores nativos (Qt/Compose)
desenham. O mapeamento é direto: `offset_x offset_y blur color`.

```python
from tempest_core import Column, Text, Widget
from tempest_core.style import Color, Edge, Shadow, Style


def card(content: str) -> Widget:
    return Column(
        children=[Text(content=content)],
        style=Style(
            background=Color.from_hex("#ffffff"),
            radius=12.0,
            padding=Edge.all(16.0),
            shadow=Shadow(
                color=Color(r=0, g=0, b=0, a=0.3),
                blur=3.0,
                offset_x=0.0,
                offset_y=1.0,
            ),
        ),
        key="card",
    )
```

Isso emite `box-shadow: 0px 1px 3px rgba(0, 0, 0, 0.3)`. Um `Shadow` sem `color`
explícito cai num preto translúcido neutro, então uma elevação ainda aparece sem
você escolher um tom.

!!! note "Os mesmos níveis de elevação do MD3"
    A folha base define `--tw-elevation-1` e `--tw-elevation-2` (umbra + penumbra)
    e os aplica ao botão preenchido no hover/clique. Quando você quer um cartão ou
    botão com elevação própria, use `Style(shadow=...)` — o número que vimos acima
    (`blur=3, offset_y=1`) é exatamente o repouso do `elevated_button`.

## Variantes de botão Material 3

Você não precisa lembrar de quais cores compõem um botão _tonal_ ou _outlined_. O
`tempestweb.components` traz as cinco variantes MD3 como helpers de uma linha:

```python
from tempest_core import App, Row, Widget
from tempestweb.components import (
    elevated_button,
    filled_button,
    outlined_button,
    text_button,
    tonal_button,
)


def view(app: App[State]) -> Widget:
    def save() -> None:
        app.set_state(lambda s: s)

    return Row(
        children=[
            filled_button("Salvar", on_click=save, key="save"),
            tonal_button("Duplicar", key="dup"),
            elevated_button("Exportar", key="export"),
            outlined_button("Editar", key="edit"),
            text_button("Cancelar", key="cancel"),
        ],
    )
```

| Helper | Ênfase | Como é construído |
|---|---|---|
| `filled_button` | Alta (padrão) | Botão cru — o tema base dá o look preenchido inteiro |
| `tonal_button` | Média | Fundo _secondary container_ + texto on-container, plano |
| `elevated_button` | Média | Superfície clara + texto primário + sombra de repouso |
| `outlined_button` | Média | Contorno + rótulo primário, fundo transparente |
| `text_button` | Baixa | Só o rótulo primário, sem fundo nem contorno |

!!! info "Como as variantes se distinguem do preenchido"
    O `filled_button` é um `Button` **sem** `Style` inline, então o tema base
    fornece tudo. As outras variantes recebem um `Style` pequeno (fundo / cor /
    borda / sombra). Definir um `background` inline é também o sinal que a folha
    base usa para **tirar a variante** da elevação automática do botão preenchido —
    por isso tonal/outlined/text ficam planos enquanto o `elevated_button` carrega
    a própria sombra.

## Campos temáticos

Os campos nativos do tempestweb — `TextField`, `EmailField`, `PasswordField` — usam
um `Input` cru **sem** `Style` inline de propósito, exatamente para que a folha base
os renderize como campos claros e outlined, consistentes com o resto da UI. Um
rótulo discreto fica acima e uma linha de erro vermelha aparece quando você passa
`error`.

```python
from tempest_core import App, Column, Widget
from tempestweb.components import EmailField, PasswordField, validate_email


def view(app: App[State]) -> Widget:
    def set_email(value: str) -> None:
        app.set_state(lambda s: setattr(s, "email", value))

    def set_password(value: str) -> None:
        app.set_state(lambda s: setattr(s, "password", value))

    return Column(
        children=[
            EmailField(
                value=app.state.email,
                on_change=set_email,
                error=validate_email(app.state.email) or "",
                key="email",
            ),
            PasswordField(
                value=app.state.password,
                on_change=set_password,
                key="password",
            ),
        ],
    )
```

!!! tip "Mais sobre campos e formulários"
    Os campos e os formulários prontos (`LoginForm`, `SignupForm`, os campos BR)
    têm página própria em [Componentes prontos](components.md). Aqui o foco é só
    como o tema os deixa bonitos sem você estilizar nada.

## Recapitulando

- O **tema base Material 3 está sempre ligado** — tipografia, espaçamento e
  controles acentuados saem prontos, sem estilizar widget por widget.
- O **`Style` inline do widget sempre ganha** da folha base (sem `!important`); os
  estados de hover/foco continuam funcionando por cima.
- Retematize a UI inteira sobrepondo os tokens `--tw-*` de um `<style>` na página.
- `Style(shadow=...)` vira um **`box-shadow` CSS** na web, igual aos renderizadores
  nativos.
- `filled_button` / `tonal_button` / `elevated_button` / `outlined_button` /
  `text_button` são as cinco variantes MD3 em uma linha cada.
- `TextField` / `EmailField` / `PasswordField` herdam o campo outlined do tema.
- Tudo renderiza igual no Modo A (WASM) e no Modo B (servidor).
