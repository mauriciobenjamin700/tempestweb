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

!!! note "De onde vem o estilo (tempest-core ≥ 0.8.1)"
    O **visual em repouso** de cada `Button`/`Input` — preenchimento, borda, forma
    e cor — agora vem do **sistema de variantes do tempest-core**, resolvido inline
    pelo próprio widget. O `client/theme.js` cuida só do que o inline **não**
    consegue expressar: a *state layer* (`::before`) de hover/foco/clique, o anel
    de foco e o tipo de fonte. Os ajudantes `filled_button`/`tonal_button`/… são
    uma fachada com nomes MD3 sobre as variantes do core. Você continua ganhando o
    visual Material 3 sem escrever **nenhum** CSS.

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

Rode nos três modos — o visual é idêntico:

```bash
tempestweb dev --mode wasm       # Python no browser (Pyodide)
tempestweb dev --mode server     # Python no servidor (FastAPI + WebSocket)
tempestweb dev --mode transpile  # app transcrito para JS nativo (bundle estático)
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
from tempest_core import Color

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
from tempest_core import Color, Edge, Shadow, Style


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

## Rebrand por tokens, do Python

A folha base pinta tudo a partir de custom properties `--tw-*` no `:root`,
e é por elas que um app troca de cara — sem tocar em widget nenhum. O que
faltava era o meio-campo: você monta a paleta em Python e precisa dela na
página.

```python
from tempest_core import Theme, ThemeMode
from tempest_core import Color
from tempestweb.html import theme_css


def head() -> str:
    """Monta o markup de head que retematiza a interface inteira.

    Returns:
        str: Um elemento de estilo com a paleta do app.
    """
    theme = Theme.from_seed(Color(r=39, g=58, b=79), mode=ThemeMode.SYSTEM)
    return f"<style>{theme_css(theme)}</style>"
```

`Theme.from_seed` gera os 39 papéis do Material 3 a partir de uma cor
semente — claro e escuro — e `theme_css` emite os que a folha de fato lê. O
bloco vai no `<head>`, antes de a folha base ser instalada no mount; como
ela declara os mesmos nomes com a mesma especificidade, o seu vence por vir
depois.

!!! tip "Modo escuro sai de graça, e sai honesto"
    Tema em `SYSTEM` emite o esquema claro no `:root` e o escuro dentro de
    `@media (prefers-color-scheme: dark)`: a página segue a configuração de
    quem lê. Tema fixado em `LIGHT` ou `DARK` emite um esquema só e nenhuma
    media query — um tema fixado que ainda virasse com o sistema não estaria
    fixado.

!!! info "Só o que a folha consome"
    `theme_css` emite as variáveis que a folha base lê, não os 39 papéis.
    Variável que ninguém consome parece zelo e é dívida: o próximo leitor
    tem que ir ao CSS descobrir se ela faz algo.

## Declare o tema, e o host o entrega

O trecho acima monta o CSS à mão porque era o único caminho. Hoje há um mais
curto, e ele cobre as duas metades: **declare `THEME` ao lado da sua `view`**.

```python
# app.py
from dataclasses import dataclass

from tempest_core import App, Theme, Widget
from tempest_core import Color


@dataclass
class State:
    """The app's state."""


def make_state() -> State:
    """Build the initial state."""
    return State()


def view(app: App[State]) -> Widget:
    """Build the screen."""
    ...


#: A paleta da marca. O artefato a lê e entrega às duas pontas.
THEME: Theme = Theme.from_seed(seed=Color(r=39, g=58, b=79))
```

O artefato gerado — tanto o do Modo B quanto o do Modo A — passa esse `THEME`
para o app quando o constrói, e isso importa porque **componente resolve cor em
Python**: um botão preenchido carrega o próprio fill como estilo inline. Tema que
não chega na árvore é tema que não pinta, por mais tokens que a página tenha.

As duas pontas que o host cobre:

* **A árvore** — o tema vai para o `App`, então cada componente nasce com a sua
  paleta.
* **A página** — os tokens `--tw-*` que a folha base lê. No Modo B eles são
  escritos no `<head>` na renderização; no Modo A a página é estática e o app só
  existe depois do Pyodide subir, então o CSS é injetado no boot, antes do
  primeiro mount.

!!! warning "`Theme(primary=...)` não é a mesma coisa que `Theme.from_seed(...)`"
    Um `Theme` carrega um **conjunto de tokens** (`tokens`) e alguns campos soltos
    de conveniência (`primary`, `background`, …). **Os componentes leem os
    tokens.** Montar um tema preenchendo só os campos soltos deixa a árvore
    inteira na paleta baseline — foi exatamente esse o bug do exemplo
    `theme-switcher`, cujos botões ficavam roxos enquanto o swatch dizia teal.
    Use `Theme.from_seed`, ou construa o `TokenSet` explicitamente.

!!! note "Tema dinâmico repinta os componentes, não os tokens da página"
    `app.set_theme(...)` reconstrói a árvore, então tudo que resolve cor em Python
    acompanha na hora. Os tokens `--tw-*`, porém, são escritos uma vez — eles
    seguem o `THEME` declarado. Na prática: as cores dos widgets trocam, e os
    estados que só a folha expressa (hover, foco) continuam na paleta declarada.
    Se a troca em runtime é o coração do seu app, declare `THEME` com a paleta que
    ele abre.

## Modo escuro: passe o tema ao widget

Um widget **estilizado** resolve as próprias cores do tema que ele carrega — do
campo `theme` dele, não de um tema ambiente. É por isso que o idioma é uma linha:

```python
Button(label="Salvar", theme=app.theme, on_click=salvar)
```

Passe `app.theme` e a árvore inteira segue o `app.set_theme(...)`; deixe de fora
e o widget resolve a paleta **clara**, mesmo que o app esteja em modo escuro.
Vale igual nos três modos.

```python
from tempest_core import App, Card, Column, Text, Theme, ThemeMode, Widget


def view(app: App[State]) -> Widget:
    """Desenha um cartão que acompanha o tema do app."""
    theme: Theme = app.theme
    return Column(
        key="body",
        children=[
            Card(
                key="card",
                theme=theme,
                children=[Text(content="Segue o tema", key="label")],
            ),
        ],
    )


def escurecer(app: App[State]) -> None:
    """Troca o tema do app, o que re-resolve todo widget que o recebeu."""
    app.set_theme(Theme(mode=ThemeMode.DARK))
```

!!! note "Widget de layout não tem `theme`"
    `Row`, `Column` e `Text` não carregam cor própria, então o core não lhes dá o
    campo — passar `theme=` levanta `ValidationError` com o nome do campo. A cor
    que eles mostram é a que herdam da caixa estilizada em volta.

!!! tip "Componente propaga como o core propaga"
    Um `EmailInput` **é** o campo: ele repassa o tema para o `Input` que constrói.
    Um `SearchBar` ou um `TextField` **compõe** um campo e sobrepõe o estilo que
    resolveu, então o campo interno mantém a paleta default — e o Modo C reproduz
    essa distinção componente por componente, fixada por matriz de paridade nos
    dois modos.

!!! info "Modo C: as tabelas geradas têm eixo de modo desde a 0.99.0"
    O Modo C não tem Python, então o estilo resolvido de cada widget viaja em
    tabela gerada. Até a 0.98.0 essas tabelas eram geradas com o tema default:
    todo widget e todo componente transpilado renderizava **claro**, e como o
    estilo inline ganha do stylesheet, era a metade com precedência que falhava.
    Agora a tabela carrega os dois modos e o builder escolhe por
    `theme.is_dark()`.

!!! warning "A folha base ainda é clara"
    O que o `Style` inline resolve segue o tema; o que só a **folha base** pinta
    (o fundo do `Input`, o fundo da página, os estados de hover e foco) continua
    na paleta clara, porque os tokens `--tw-*` não têm eixo de modo. Num app
    escuro isso aparece como campo branco dentro de cartão escuro. Rastreado em
    [#148](https://github.com/mauriciobenjamin700/tempestweb/issues/148).

## Indicadores de progresso

`ProgressBar` e `Spinner` não têm tamanho próprio: sem folha de estilo, os dois
renderizam como `div` vazia de altura zero — presentes na árvore, invisíveis na
tela, que é pior que ausentes, porque o app diz que está mostrando progresso e o
usuário não vê nada. O tema base os desenha, e o `color_scheme` escolhe o acento
entre as famílias que o core nomeia (`primary`, `secondary`, `tertiary`, `error`,
`success`, `warning`, `info`, `neutral`).

```python
from tempest_core import App, Column, Widget
from tempest_core import ProgressBar, Spinner


def view(app: App[State]) -> Widget:
    return Column(
        children=[
            ProgressBar(value=0.42, key="leitura"),
            ProgressBar(indeterminate=True, key="na-fila"),
            ProgressBar(value=1.0, color_scheme="success", key="pronto"),
            Spinner(size=24.0, key="girando"),
        ],
    )
```

Uma barra **determinada** é um trilho com um preenchimento em porcentagem, e a
transição do tema faz a largura andar suave a cada valor novo. Uma barra
**indeterminada** não declara valor — nem no CSS nem para o leitor de tela, que
recebe `role="progressbar"` sem `aria-valuenow`, porque um número sobre trabalho
que ninguém está medindo seria lido como fato.

!!! tip "Rebrand igual ao resto"
    O acento sai de `--tw-indicator`, que por sua vez vem do token da família.
    Sobrescreva `--tw-success` (ou qualquer outro) e as barras daquela família
    acompanham, sem tocar em widget nenhum.

!!! info "Movimento é decoração; o estado não é"
    Sob `prefers-reduced-motion: reduce` a animação para e a barra
    indeterminada fica como uma faixa estática — quem pediu menos movimento
    continua vendo que há algo rodando.

!!! warning "No SSR o desenho é inline"
    `render_to_html` não embarca a folha base, só um reset, então lá os dois
    saem com estilo inline autossuficiente: trilho translúcido e preenchimento
    em `currentColor`, ou seja, a barra assume a cor do texto ao redor. É a
    escolha que faz uma página estática mostrar progresso sem depender de
    nenhum CSS seu.

## Recapitulando

- O **tema base Material 3 está sempre ligado** — tipografia, espaçamento e
  controles acentuados saem prontos, sem estilizar widget por widget.
- O **`Style` inline do widget sempre ganha** da folha base (sem `!important`); os
  estados de hover/foco continuam funcionando por cima.
- Retematize a UI inteira sobrepondo os tokens `--tw-*` de um `<style>` na página —
  `theme_css(Theme.from_seed(...))` monta esse bloco, com modo escuro junto.
- `Style(shadow=...)` vira um **`box-shadow` CSS** na web, igual aos renderizadores
  nativos.
- `filled_button` / `tonal_button` / `elevated_button` / `outlined_button` /
  `text_button` são as cinco variantes MD3 em uma linha cada.
- `TextField` / `EmailField` / `PasswordField` herdam o campo outlined do tema.
- `ProgressBar` e `Spinner` só existem na tela porque o tema os desenha; o
  `color_scheme` escolhe o acento e o SSR os emite com estilo inline próprio.
- Tudo renderiza igual no Modo A (WASM) e no Modo B (servidor).
