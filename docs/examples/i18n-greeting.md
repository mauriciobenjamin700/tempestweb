# Saudação Internacionalizada — i18n com Locale e t() 🌍

Construa um app de saudação multilíngue que troca entre Inglês, Português e Árabe (RTL) em tempo real — e aprenda a usar `Locale`, `translate()` e interpolação de variáveis no tempestweb.

---

## O que você vai construir

Um app que demonstra o sistema de i18n do tempestweb com:

- 🌐 **Seletor de idioma** via `SegmentedControl` (English / Português / العربية)
- ✏️ **Campo de nome** com placeholder localizado; a saudação é atualizada letra a letra
- 👋 **Título de saudação** em fonte grande — interpola `{name}` em tempo real via `t()`
- 🃏 **Card de curiosidade** com título e corpo totalmente traduzidos
- ↔️ **Alinhamento dinâmico** — textos ficam à direita automaticamente para árabe (RTL)
- ℹ️ **Linha de metadados** mostrando a tag BCP-47 e a direção da localidade ativa

!!! note "Nota — uma `view`, três idiomas"
    O app não tem nenhuma lógica condicional do tipo `if locale == "ar": ...`. Toda string visível passa por `t()`, que usa a localidade ativa para fazer o lookup no catálogo. Trocar o idioma gera um novo render completo, mas o código da `view` não sabe qual idioma está ativo.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leitura recomendada (opcional):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor

---

## Criando o projeto

Crie a pasta e o arquivo do app:

```bash
mkdir -p examples/i18n-greeting
touch examples/i18n-greeting/app.py
```

---

## Passo 1 — O catálogo de traduções

Antes da UI, precisamos definir todas as strings localizadas. O catálogo é um dicionário simples, indexado primeiro pela tag BCP-47 do idioma e depois pela chave da mensagem:

```python
from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "Internationalized Greeting",
        "pick_language": "Language",
        "name_label": "Your name",
        "name_placeholder": "Type your name…",
        "greeting": "Hello, {name}!",
        "greeting_anonymous": "Hello, stranger!",
        "fun_fact_title": "Did you know?",
        "fun_fact": (
            "The word 'hello' as a phone greeting was popularised by "
            "Thomas Edison in 1877. Before that, 'ahoy' was preferred."
        ),
        "locale_info": "Active locale: {tag} — direction: {direction}",
        "ltr": "left-to-right",
        "rtl": "right-to-left",
    },
    "pt": {
        "app_title": "Saudação Internacionalizada",
        "pick_language": "Idioma",
        "name_label": "Seu nome",
        "name_placeholder": "Digite seu nome…",
        "greeting": "Olá, {name}!",
        "greeting_anonymous": "Olá, desconhecido(a)!",
        "fun_fact_title": "Você sabia?",
        "fun_fact": (
            "A palavra olá é considerada um abrasileiramento de halloa, "
            "exclamação náutica inglesa usada para chamar barcos ao longe."
        ),
        "locale_info": "Localidade ativa: {tag} — direção: {direction}",
        "ltr": "esquerda para direita",
        "rtl": "direita para esquerda",
    },
    "ar": {
        "app_title": "تحية دولية",
        "pick_language": "اللغة",
        "name_label": "اسمك",
        "name_placeholder": "اكتب اسمك…",
        "greeting": "مرحباً، {name}!",
        "greeting_anonymous": "مرحباً أيها الغريب!",
        "fun_fact_title": "هل تعلم؟",
        "fun_fact": (
            "كلمة مرحباً مشتقة من الرحب بمعنى الاتساع، "
            "وكأنك تقول للضيف: أهلاً في رحابة هذا المكان."
        ),
        "locale_info": "اللغة النشطة: {tag} — الاتجاه: {direction}",
        "ltr": "من اليسار إلى اليمين",
        "rtl": "من اليمين إلى اليسار",
    },
}
```

!!! tip "Dica — chaves de string como contrato"
    Mantenha os **nomes das chaves** idênticos em todos os idiomas (`"greeting"`, `"fun_fact"`, etc.). É por essas chaves que `t()` faz o lookup — se uma chave faltar em algum idioma, você receberá um `KeyError` imediato no primeiro render naquele idioma, o que facilita encontrar a omissão.

---

## Passo 2 — Definindo as localidades

Cada idioma é representado por um objeto `Locale` com a tag do idioma, a região e o sinalizador RTL:

```python
from tempest_core import Locale

LOCALE_LABELS: list[str] = ["English", "Português", "العربية"]
LOCALES: list[Locale] = [
    Locale(language="en", region="US", rtl=False),
    Locale(language="pt", region="BR", rtl=False),
    Locale(language="ar", region="SA", rtl=True),
]
```

!!! info "Nota — `Locale.tag`"
    `Locale` expõe a propriedade `.tag` que retorna a tag BCP-47 completa (`"en-US"`, `"pt-BR"`, `"ar-SA"`). O `TRANSLATIONS` usa só o código de idioma (`"en"`, `"pt"`, `"ar"`) como chave de primeiro nível — a função `t()` extrai `locale.language` internamente para fazer o lookup.

---

## Passo 3 — Definindo o estado

O estado do app é mínimo: só o índice da localidade selecionada e o nome digitado.

```python
from dataclasses import dataclass, field


@dataclass
class GreetingState:
    """State for the internationalized greeting app.

    Attributes:
        locale_index: Index into :data:`LOCALES` / :data:`LOCALE_LABELS`.
        name: The visitor's name as typed into the input field.
    """

    locale_index: int = 0
    name: str = field(default="")


def make_state() -> GreetingState:
    """Build the initial state — English locale, empty name.

    Returns:
        A fresh :class:`GreetingState`.
    """
    return GreetingState()
```

!!! tip "Dica — índice vs. objeto"
    Armazenar `locale_index: int` em vez do objeto `Locale` inteiro mantém o estado serializable por padrão (um inteiro é JSON-safe). O objeto `Locale` é derivado dentro de `view()` com `LOCALES[app.state.locale_index]`.

---

## Passo 4 — Os handlers de evento

Dentro de `view()`, dois handlers respondem às interações do usuário:

```python
from tempest_core import App, Widget
from tempest_core.widgets.events import TextChangeEvent


def view(app: App[GreetingState]) -> Widget:
    """Render the greeting UI from the current state."""
    locale: Locale = LOCALES[app.state.locale_index]

    def on_locale_selected(index: int) -> None:
        """Switch the active locale.

        Args:
            index: Zero-based index of the chosen segment in
                :data:`LOCALE_LABELS`.
        """
        app.set_state(lambda s: setattr(s, "locale_index", index))

    def on_name_change(event: TextChangeEvent) -> None:
        """Update the visitor name from the input field.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "name", event.value))
```

Repare que os handlers são definidos **dentro** de `view()`. Eles capturam `app` por closure — um padrão idiomático do tempestweb para manter a função `view` pura (sem globais mutáveis).

---

## Passo 5 — Derivando strings com `t()`

Com a localidade e os handlers definidos, calculamos as strings derivadas antes de montar os widgets:

```python
from tempest_core import t


def view(app: App[GreetingState]) -> Widget:
    locale: Locale = LOCALES[app.state.locale_index]

    # ... (handlers — ver Passo 4)

    greeting: str = (
        t("greeting", locale, TRANSLATIONS, name=app.state.name)
        if app.state.name.strip()
        else t("greeting_anonymous", locale, TRANSLATIONS)
    )
    direction_key: str = "rtl" if locale.rtl else "ltr"
    locale_info: str = t(
        "locale_info",
        locale,
        TRANSLATIONS,
        tag=locale.tag,
        direction=t(direction_key, locale, TRANSLATIONS),
    )
```

A assinatura completa de `t()` é:

```
t(key, locale, catalogue, **kwargs) -> str
```

Os `**kwargs` são passados diretamente para `str.format_map()`. Isso significa que `"Hello, {name}!"` + `name="Alice"` → `"Hello, Alice!"` — sem nenhum motor de template, só Python puro.

!!! tip "Dica — `t()` dentro de `t()`"
    Veja que `locale_info` usa `t(direction_key, ...)` **dentro** da chamada de `t("locale_info", ...)`. Isso é perfeitamente válido — o resultado do `t()` interno é uma string Python comum, que então é passada como `direction=` para o externo. Essa composição permite ter textos completamente localizados, inclusive as partes variáveis.

---

## Passo 6 — Construindo a árvore de widgets

Agora montamos a UI. O alinhamento de texto espelha a direção da localidade:

```python
from tempest_core import Style
from tempest_core.components import Card, Divider, SegmentedControl
from tempest_core.style import Edge, FontWeight, TextAlign
from tempest_core.widgets import Column, Input, Text


def view(app: App[GreetingState]) -> Widget:
    locale: Locale = LOCALES[app.state.locale_index]

    # ... (handlers e strings derivadas — ver Passos 4 e 5)

    text_align: TextAlign = TextAlign.RIGHT if locale.rtl else TextAlign.LEFT

    return Column(
        key="root",
        style=Style(gap=20.0, padding=Edge.all(24.0)),
        children=[
            # Título
            Text(
                key="title",
                content=t("app_title", locale, TRANSLATIONS),
                style=Style(
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Divider(key="title-div"),
            # Seletor de idioma
            Column(
                key="lang-col",
                style=Style(gap=8.0),
                children=[
                    Text(
                        key="lang-label",
                        content=t("pick_language", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, font_weight=FontWeight.BOLD),
                    ),
                    SegmentedControl(
                        key="lang-picker",
                        options=LOCALE_LABELS,
                        selected=app.state.locale_index,
                        on_select=on_locale_selected,
                    ),
                ],
            ),
            # Campo de nome
            Column(
                key="name-col",
                style=Style(gap=8.0),
                children=[
                    Text(
                        key="name-label",
                        content=t("name_label", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, font_weight=FontWeight.BOLD),
                    ),
                    Input(
                        key="name-input",
                        value=app.state.name,
                        placeholder=t("name_placeholder", locale, TRANSLATIONS),
                        on_change=on_name_change,
                    ),
                ],
            ),
            # Título de saudação
            Text(
                key="greeting",
                content=greeting,
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    text_align=text_align,
                ),
            ),
            # Card de curiosidade
            Card(
                key="fun-fact-card",
                children=[
                    Text(
                        key="fact-title",
                        content=t("fun_fact_title", locale, TRANSLATIONS),
                        style=Style(
                            font_size=15.0,
                            font_weight=FontWeight.BOLD,
                            text_align=text_align,
                        ),
                    ),
                    Text(
                        key="fact-body",
                        content=t("fun_fact", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, text_align=text_align),
                    ),
                ],
            ),
            # Metadados da localidade ativa
            Text(
                key="locale-info",
                content=locale_info,
                style=Style(font_size=12.0, text_align=TextAlign.CENTER),
            ),
        ],
    )
```

!!! tip "Dica — `text_align` derivado do `locale.rtl`"
    `text_align: TextAlign = TextAlign.RIGHT if locale.rtl else TextAlign.LEFT` é calculado uma vez e reutilizado em todos os widgets que precisam respeitar a direção. Sem nenhuma lógica condicional espalhada — basta passar `text_align` onde necessário.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Internationalized greeting — demonstrates :mod:`tempest_core.i18n`.

This example is a non-trivial showcase of the i18n helpers:

* :class:`~tempest_core.i18n.Locale` — language, region, RTL flag.
* :func:`~tempest_core.i18n.translate` (alias :data:`~tempest_core.i18n.t`)
  — key look-up with ``str.format`` interpolation.

The user can:

1. Pick a language via a :class:`~tempest_core.components.SegmentedControl`
   (English, Português, العربية).
2. Type their name into an :class:`~tempest_core.widgets.Input`; the greeting
   headline interpolates it in real time.
3. See a "fun fact" card whose text also re-renders through ``t()``.

Both mode A (WASM/Pyodide) and mode B (server + WebSocket) run this exact
``view`` unchanged — the app never names a transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Locale, Style, Widget, t
from tempest_core.components import Card, Divider, SegmentedControl
from tempest_core.style import Edge, FontWeight, TextAlign
from tempest_core.widgets import Column, Input, Text
from tempest_core.widgets.events import TextChangeEvent

# ---------------------------------------------------------------------------
# Translation catalogue
# ---------------------------------------------------------------------------

#: All localised strings keyed by BCP-47 language tag then message key.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "Internationalized Greeting",
        "pick_language": "Language",
        "name_label": "Your name",
        "name_placeholder": "Type your name…",
        "greeting": "Hello, {name}!",
        "greeting_anonymous": "Hello, stranger!",
        "fun_fact_title": "Did you know?",
        "fun_fact": (
            "The word 'hello' as a phone greeting was popularised by "
            "Thomas Edison in 1877. Before that, 'ahoy' was preferred."
        ),
        "locale_info": "Active locale: {tag} — direction: {direction}",
        "ltr": "left-to-right",
        "rtl": "right-to-left",
    },
    "pt": {
        "app_title": "Saudação Internacionalizada",
        "pick_language": "Idioma",
        "name_label": "Seu nome",
        "name_placeholder": "Digite seu nome…",
        "greeting": "Olá, {name}!",
        "greeting_anonymous": "Olá, desconhecido(a)!",
        "fun_fact_title": "Você sabia?",
        "fun_fact": (
            "A palavra olá é considerada um abrasileiramento de halloa, "
            "exclamação náutica inglesa usada para chamar barcos ao longe."
        ),
        "locale_info": "Localidade ativa: {tag} — direção: {direction}",
        "ltr": "esquerda para direita",
        "rtl": "direita para esquerda",
    },
    "ar": {
        "app_title": "تحية دولية",
        "pick_language": "اللغة",
        "name_label": "اسمك",
        "name_placeholder": "اكتب اسمك…",
        "greeting": "مرحباً، {name}!",
        "greeting_anonymous": "مرحباً أيها الغريب!",
        "fun_fact_title": "هل تعلم؟",
        "fun_fact": (
            "كلمة مرحباً مشتقة من الرحب بمعنى الاتساع، "
            "وكأنك تقول للضيف: أهلاً في رحابة هذا المكان."
        ),
        "locale_info": "اللغة النشطة: {tag} — الاتجاه: {direction}",
        "ltr": "من اليسار إلى اليمين",
        "rtl": "من اليمين إلى اليسار",
    },
}

# ---------------------------------------------------------------------------
# Available locales (parallel lists — index is the shared key)
# ---------------------------------------------------------------------------

LOCALE_LABELS: list[str] = ["English", "Português", "العربية"]
LOCALES: list[Locale] = [
    Locale(language="en", region="US", rtl=False),
    Locale(language="pt", region="BR", rtl=False),
    Locale(language="ar", region="SA", rtl=True),
]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class GreetingState:
    """State for the internationalized greeting app.

    Attributes:
        locale_index: Index into :data:`LOCALES` / :data:`LOCALE_LABELS`.
        name: The visitor's name as typed into the input field.
    """

    locale_index: int = 0
    name: str = field(default="")


def make_state() -> GreetingState:
    """Build the initial state — English locale, empty name.

    Returns:
        A fresh :class:`GreetingState`.
    """
    return GreetingState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[GreetingState]) -> Widget:
    """Render the greeting UI from the current state.

    Reads the active :class:`~tempest_core.i18n.Locale` from ``app.state``
    and translates every visible string via
    :func:`~tempest_core.i18n.translate` so that switching the language
    selector re-renders the entire tree in the new locale without any
    conditional logic scattered through the widget tree.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    locale: Locale = LOCALES[app.state.locale_index]

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_locale_selected(index: int) -> None:
        """Switch the active locale.

        Args:
            index: Zero-based index of the chosen segment in
                :data:`LOCALE_LABELS`.
        """
        app.set_state(lambda s: setattr(s, "locale_index", index))

    def on_name_change(event: TextChangeEvent) -> None:
        """Update the visitor name from the input field.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "name", event.value))

    # ------------------------------------------------------------------
    # Derived strings — all go through translate()
    # ------------------------------------------------------------------

    greeting: str = (
        t("greeting", locale, TRANSLATIONS, name=app.state.name)
        if app.state.name.strip()
        else t("greeting_anonymous", locale, TRANSLATIONS)
    )
    direction_key: str = "rtl" if locale.rtl else "ltr"
    locale_info: str = t(
        "locale_info",
        locale,
        TRANSLATIONS,
        tag=locale.tag,
        direction=t(direction_key, locale, TRANSLATIONS),
    )

    # ------------------------------------------------------------------
    # Layout — text-align mirrors the locale direction
    # ------------------------------------------------------------------

    text_align: TextAlign = TextAlign.RIGHT if locale.rtl else TextAlign.LEFT

    return Column(
        key="root",
        style=Style(gap=20.0, padding=Edge.all(24.0)),
        children=[
            # Title
            Text(
                key="title",
                content=t("app_title", locale, TRANSLATIONS),
                style=Style(
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Divider(key="title-div"),
            # Language picker
            Column(
                key="lang-col",
                style=Style(gap=8.0),
                children=[
                    Text(
                        key="lang-label",
                        content=t("pick_language", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, font_weight=FontWeight.BOLD),
                    ),
                    SegmentedControl(
                        key="lang-picker",
                        options=LOCALE_LABELS,
                        selected=app.state.locale_index,
                        on_select=on_locale_selected,
                    ),
                ],
            ),
            # Name input
            Column(
                key="name-col",
                style=Style(gap=8.0),
                children=[
                    Text(
                        key="name-label",
                        content=t("name_label", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, font_weight=FontWeight.BOLD),
                    ),
                    Input(
                        key="name-input",
                        value=app.state.name,
                        placeholder=t("name_placeholder", locale, TRANSLATIONS),
                        on_change=on_name_change,
                    ),
                ],
            ),
            # Greeting headline
            Text(
                key="greeting",
                content=greeting,
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    text_align=text_align,
                ),
            ),
            # Fun-fact card
            Card(
                key="fun-fact-card",
                children=[
                    Text(
                        key="fact-title",
                        content=t("fun_fact_title", locale, TRANSLATIONS),
                        style=Style(
                            font_size=15.0,
                            font_weight=FontWeight.BOLD,
                            text_align=text_align,
                        ),
                    ),
                    Text(
                        key="fact-body",
                        content=t("fun_fact", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, text_align=text_align),
                    ),
                ],
            ),
            # Active-locale metadata
            Text(
                key="locale-info",
                content=locale_info,
                style=Style(font_size=12.0, text_align=TextAlign.CENTER),
            ),
        ],
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/i18n-greeting/app.py
```

O Python roda **dentro do browser** via Pyodide. Sem servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/i18n-greeting/app.py
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica ao DOM.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Título centralizado em inglês: **"Internationalized Greeting"**
    2. `SegmentedControl` com três opções: **English / Português / العربية**
    3. Campo de texto com placeholder **"Type your name…"**
    4. Saudação grande: **"Hello, stranger!"** (enquanto o nome estiver vazio)
    5. Clique em **Português** → toda a UI re-renderiza em PT-BR instantaneamente
    6. Digite um nome → a saudação interpola em tempo real: **"Olá, Alice!"**
    7. Clique em **العربية** → textos alinham à direita, saudação em árabe
    8. A linha inferior mostra `ar-SA` e a direção no idioma ativo

---

## Verificação automatizada ✅

Rode os quatro checks antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes
pytest -q
```

Todos devem passar em verde. O exemplo foi projetado para ser `mypy --strict` clean — toda variável e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O ciclo de atualização ao trocar idioma

```
Clique em "Português" no SegmentedControl
      │
      ▼
on_locale_selected(index=1)
      │
      ▼
app.set_state(lambda s: setattr(s, "locale_index", 1))
      │
      ▼
tempestweb aplica o mutador → novo estado (locale_index=1)
      │
      ▼
view(app) chamada novamente
      │
      ▼
locale = LOCALES[1]  →  Locale(language="pt", region="BR", rtl=False)
      │
      ▼
t("app_title", locale, TRANSLATIONS)  →  "Saudação Internacionalizada"
t("greeting_anonymous", locale, TRANSLATIONS)  →  "Olá, desconhecido(a)!"
… (todas as strings re-calculadas)
      │
      ▼
reconciliador calcula diff → patches mínimos
      │
      ▼
DOM atualizado
```

### Interpolação: `t()` com `**kwargs`

A função `t()` faz basicamente:

```python
catalogue[locale.language][key].format_map(kwargs)
```

Então `t("greeting", locale, TRANSLATIONS, name="Alice")` resolve `"Olá, {name}!"` → `"Olá, Alice!"` com Python puro, zero dependências.

### Suporte RTL sem CSS

O tempestweb não tem cascata de CSS. O alinhamento de texto é um atributo do `Style` — `TextAlign.RIGHT` ou `TextAlign.LEFT`. A variável `text_align` é calculada uma vez a partir de `locale.rtl` e passada para cada widget que precisa respeitar a direção. Simples e explícito.

### Catálogo como dado, não como framework

O `TRANSLATIONS` é um `dict` Python comum. Você pode carregá-lo de um arquivo JSON, de um banco de dados, ou de um pacote de tradução externo — o `t()` só exige um objeto compatível com `catalogue[language][key]`. Para apps maiores, considere carregar por idioma sob demanda.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Criar um **catálogo de traduções** como `dict[str, dict[str, str]]`
- ✅ Usar `Locale` para encapsular idioma, região e direção RTL
- ✅ Chamar `t(key, locale, catalogue, **kwargs)` para lookups com interpolação
- ✅ Compor chamadas de `t()` — `t()` dentro de `t()` para partes variáveis localizadas
- ✅ Derivar `text_align` do `locale.rtl` e aplicá-lo uniformemente na árvore
- ✅ Manter a `view` livre de lógica condicional de idioma — apenas dados e `t()`

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um **quarto idioma** (ex.: Japonês `ja-JP`, LTR) — basta acrescentar entradas em `TRANSLATIONS` e `LOCALES`
- 💡 Carregue o catálogo de um **arquivo JSON externo** com `json.load()` para separar strings do código
- 💡 Explore o exemplo [settings-panel](./settings-panel.md) para ver como o `SegmentedControl` é usado em persistência de preferências
- 💡 Leia [Modos de execução](../tutorial/modes.md) para entender como o Modo B envia patches RTL para o cliente JS sem nenhuma mudança no Python
