# Ícones (Material + Lucide)

Seu app precisa de um ícone de menu, um cadeado no campo de senha, uma seta de
voltar? O tempestweb traz **dois conjuntos de ícones vendorados** — **Lucide**
(o padrão, herdado do core) e **Material Symbols (Outlined)** — desenhados no
cliente como **SVG inline**. Sem fonte de ícone, sem rede, sem CDN: funciona
**offline** e dentro de um PWA. 🎯

Você escolhe o conjunto numa chamada óbvia, em **Python tipado**:

```python
from tempestweb.icons import material_icon, lucide_icon, MaterialIcons, Icons

material_icon(MaterialIcons.HOME)   # Material Symbols "home"
lucide_icon(Icons.MAIL)             # Lucide "mail"
```

## O mínimo: um ícone na tela

Um `Icon` é um widget como qualquer outro. Coloque-o numa `Column`/`Row` e pronto:

```python
from dataclasses import dataclass

from tempest_core import App, Column, Row, Text, Widget

from tempestweb.icons import MaterialIcons, material_icon


@dataclass
class State:
    pass


def make_state() -> State:
    return State()


def view(app: App[State]) -> Widget:
    return Row(
        children=[
            material_icon(MaterialIcons.HOME),
            Text(content="Início"),
        ],
    )
```

Rode nos três modos — o desenho é idêntico:

```bash
tempestweb dev --mode wasm       # Python no browser (Pyodide)
tempestweb dev --mode server     # Python no servidor (FastAPI + WebSocket)
tempestweb dev --mode transpile  # app transcrito para JS nativo (bundle estático)
```

!!! info "Por que dois conjuntos?"
    **Lucide** é o conjunto padrão do core (`tempest_core.icons.Icons`) — traços
    limpos, estilo "feather". **Material Symbols** combina com o **tema base
    Material 3** que já vem ligado (veja [Tema](theming.md)). Use o que casar com
    o visual do seu app; dá para misturar os dois na mesma tela.

## Escolhendo o ícone com autocomplete

`MaterialIcons` e `Icons` são `StrEnum` — cada membro **é** sua string. Então você
ganha autocomplete do editor sem perder a flexibilidade de passar uma string crua:

```python
from tempestweb.icons import MaterialIcons, material_icon

material_icon(MaterialIcons.SETTINGS)   # com autocomplete
material_icon("settings")               # string crua — idêntico
```

!!! tip "Qualquer nome do conjunto serve"
    A enum lista os ícones **mais comuns** (HOME, SEARCH, CLOSE, MENU…), mas
    qualquer nome válido do Material Symbols funciona como string crua **desde que
    o glifo esteja vendorado no cliente** (`client/icons/material.js`). Para um
    glifo fora do conjunto, veja [Ícone customizado](#icone-customizado-svg-cru)
    abaixo.

## Tamanho e cor

`size` é a aresta do ícone em pixels lógicos. Omita para o ícone **escalar com a
fonte** ao redor. A cor vem do `Style.color` — o glifo é desenhado em
`currentColor`:

```python
from tempest_core import Style
from tempest_core import Color

from tempestweb.icons import MaterialIcons, material_icon

# Ícone de 20px tingido de vermelho
material_icon(
    MaterialIcons.FAVORITE,
    size=20.0,
    style=Style(color=Color(r=220, g=40, b=40)),
)

# Sem size → acompanha o tamanho da fonte do contêiner
material_icon(MaterialIcons.STAR)
```

## Ícones dentro dos campos

Os widgets de entrada do core têm _slots_ de ícone: `Input`, `Dropdown` e
`Autocomplete` aceitam `leading_icon` e `trailing_icon`; `IconButton` e `MenuItem`
aceitam `icon`. O nome vai **cru** — sem prefixo ele resolve no **Lucide**, para
compatibilidade com o `Icon` do core:

!!! info "O `label` do `IconButton` é o nome acessível"
    Um `IconButton` renderiza como `<button>` de verdade, com o glifo do `icon`
    dentro e o `label` em `aria-label` — não como texto visível. Então
    `IconButton(icon=Icons.MENU, label="menu", …)` desenha `☰` e é anunciado como
    "menu", em vez de escrever a palavra. Um `semantics.label` explícito ganha do
    `label`. Vale nos três modos e no HTML estático.

```python hl_lines="7 8"
from tempest_core import Input


def email_input(value: str) -> Input:
    """Build an e-mail input with a leading mail glyph."""
    return Input(
        key="email",
        value=value,
        placeholder="you@example.com",
        leading_icon="mail",              # Lucide
        trailing_icon="material:check",   # Material, pelo prefixo
        on_change=lambda event: None,
    )
```

!!! warning "Os campos prontos não expõem o slot"
    `EmailField` e `PasswordField` (de `tempestweb.components`) embrulham um
    `Input` mas **não** publicam `leading_icon`/`trailing_icon` — passar o kwarg
    levanta `ValidationError` com o nome do campo, porque o core recusa kwarg que
    não declara. Precisa de ícone no campo? Use o `Input` do core direto, como
    acima.

!!! note "A gramática do nome"
    Por baixo, o conjunto é codificado como um **prefixo** no nome do `Icon`:
    `"material:home"`, `"lucide:mail"`. As funções `material_icon`/`lucide_icon`
    põem o prefixo por você. Um nome **sem** prefixo (`"mail"`) resolve no Lucide —
    é por isso que os _slots_ de ícone só pedem o nome cru.

## Ícone customizado (SVG cru) { #icone-customizado-svg-cru }

Precisa de um glifo que **não** está vendorado? Tem duas saídas.

**1. `custom_icon` — manda o path pela rede, sem registrar nada.** O `d` do SVG
viaja no próprio nome do ícone, então o cliente não precisa de registro prévio. É
desenhado **traçado** numa grade `0 0 24 24` em `currentColor` (a convenção do
Lucide):

```python
from tempestweb.icons import custom_icon

# Um "raio" desenhado à mão na grade 24x24
custom_icon("M13 2 L4 14 H12 L11 22 L20 10 H13 Z", size=24.0)
```

**2. Registrar nos dois lados — para um glifo reutilizado.** Registre em Python
(`register_icon`) **e** no cliente (`registerIcon` em `client/icons/index.js`),
aí passe o nome cru:

```python
from tempest_core import Icon

from tempestweb.icons import register_icon

register_icon("rocket", "M13 2 L4 14 H12 L11 22 L20 10 H13 Z")
Icon(name="rocket")
```

```javascript
import { registerIcon } from "./icons/index.js";

registerIcon("rocket", "M13 2 L4 14 H12 L11 22 L20 10 H13 Z");
```

!!! tip "Quando usar cada um"
    `custom_icon` é ótimo para um **glifo único e pontual** (sem tocar o cliente).
    O registro nos dois lados vale a pena quando o **mesmo** glifo aparece em
    vários lugares — o path viaja uma vez (no JS vendorado) em vez de em cada
    patch.

## Offline e PWA

Como tudo é SVG inline a partir de path vendorado em `client/icons/{lucide,material}.js`,
os ícones **não fazem rede**. O `tempestweb build` inclui esses assets no artefato,
então um app instalado (PWA) desenha todos os ícones **offline**, sem fonte de
ícone nem requisição externa. Nada a configurar. ✅

## Recap

- **Dois conjuntos vendorados:** `lucide_icon(...)` (padrão) e
  `material_icon(...)` (combina com o tema Material 3).
- `MaterialIcons`/`Icons` são `StrEnum` → autocomplete + string crua.
- `size` escala o ícone (omita p/ acompanhar a fonte); `Style.color` o tinge.
- Slots dos campos usam **nome cru** (= Lucide).
- Glifo fora do conjunto: `custom_icon(path)` (pontual) ou `register_icon` +
  `registerIcon` (reutilizado).
- Tudo é **SVG inline** — sem rede, **offline/PWA safe**.
