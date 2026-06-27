# Formulário de Login

Construa um **formulário de autenticação completo** com validação em três camadas,
banner de erro e tela de sucesso — tudo em Python puro, sem HTML nem JavaScript. 🔐

Ao final deste tutorial você terá um app funcional que usa os componentes
`EmailInput`, `PasswordInput`, `Form`, `FormField`, `Banner`, `Card`, `Divider`,
`Button`, `Column` e `Text` para entregar uma experiência de login profissional,
incluindo mensagens de erro inline nos campos e um banner vermelho para credenciais
erradas.

---

## O problema

Todo sistema autenticado precisa de um formulário de login. Mas um bom formulário
vai além do visual: ele precisa **validar os campos antes de submeter**, exibir
**mensagens de erro próximas ao campo** que falhou, bloquear o submit enquanto há
erros, e ainda mostrar um **erro de nível superior** quando o servidor rejeita as
credenciais (e-mail + senha individualmente corretos, mas combinação inválida).

O desafio em Python é orquestrar esse fluxo sem acoplar a lógica de validação ao
render. O tempestweb resolve isso com `Form` + `FormField` + `Validator` —
componentes que separam "qual regra?" (validators) de "quando mostrar o erro?"
(estado) e "como renderizar?" (os widgets filhos).

!!! note "O que você vai exercitar"
    - `EmailInput` e `PasswordInput` — componentes de formulário pré-construídos
      com estilo e semântica corretos.
    - `FormField` — wrapper que associa validators e mensagens de erro a um campo.
    - `Form.validate()` — dispara todos os validators de uma vez e devolve um
      `FormState` com `valid` e `errors`.
    - `Banner(tone="error")` — exibe erros de nível de autenticação acima do form.
    - Troca de tela por flag booleana no estado (`authenticated`).

---

## Pré-requisitos

Certifique-se de ter feito a [Instalação](../installation.md) e lido o
[Tutorial do Counter](../tutorial/index.md). Este exemplo assume que você já
conhece `App`, `set_state`, `make_state` e `view`.

Se quiser entender como os patches são propagados quando o form troca de tela,
leia também [Patches na rede](../tutorial/patches.md).

---

## O app completo

Este é o código exato de
[`examples/login-form/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/login-form/app.py).
Copie, rode, e depois leia a explicação seção por seção.

```python
"""Login form — demonstrates auth-oriented form validation with brform components.

The form uses :class:`~tempest_core.components.EmailInput` and
:class:`~tempest_core.components.PasswordInput` (the pre-built BR-form
components) together with :class:`~tempest_core.widgets.Form` /
:class:`~tempest_core.widgets.FormField` validators to gate submission on
both field validity and a fake credential check. The result flips an
``authenticated`` flag in state, rendering a success screen or a red error
banner for wrong credentials.

Run in either mode — the ``view`` function is transport-agnostic::

    tempestweb dev --mode wasm    # Python in the browser (Pyodide)
    tempestweb dev --mode server  # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tempest_core import App, Style, Widget
from tempest_core.components import (
    Banner,
    Card,
    Divider,
    EmailInput,
    PasswordInput,
)
from tempest_core.style import AlignItems, Color, Edge, FontWeight, TextAlign
from tempest_core.widgets import (
    Button,
    Column,
    Form,
    FormField,
    FormState,
    Text,
    Validator,
)

# ---------------------------------------------------------------------------
# Fake credential store — real apps would call an async API instead.
# ---------------------------------------------------------------------------

_VALID_CREDENTIALS: dict[str, str] = {
    "admin@example.com": "secret1234",
    "user@example.com": "password99",
}

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class LoginState:
    """All mutable state for the login screen.

    Attributes:
        email: The current value of the email field.
        password: The current value of the password field.
        errors: Per-field validation errors keyed by field name.
        auth_error: A top-level authentication error message (wrong credentials).
        authenticated: Whether the user has successfully authenticated.
        loading: Whether a credential check is in progress.
    """

    email: str = ""
    password: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    auth_error: str = ""
    authenticated: bool = False
    loading: bool = False


def make_state() -> LoginState:
    """Build the initial, unauthenticated login state.

    Returns:
        A fresh :class:`LoginState` with all fields blank and no errors.
    """
    return LoginState()


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _require(message: str) -> Validator:
    """Return a validator that rejects blank/whitespace-only values.

    Args:
        message: The error message returned when the value is blank.

    Returns:
        A :data:`~tempest_core.widgets.Validator` callable.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return message if not str(value).strip() else None

    return rule


def _valid_email(message: str) -> Validator:
    """Return a validator that rejects strings that are not valid e-mail addresses.

    Args:
        message: The error message returned when the address is syntactically invalid.

    Returns:
        A :data:`~tempest_core.widgets.Validator` callable.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        text = str(value).strip()
        return None if _EMAIL_RE.fullmatch(text) else message

    return rule


def _min_length(length: int, message: str) -> Validator:
    """Return a validator that rejects values shorter than ``length`` characters.

    Args:
        length: The minimum character count (inclusive).
        message: The error message returned when the value is too short.

    Returns:
        A :data:`~tempest_core.widgets.Validator` callable.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return message if len(str(value)) < length else None

    return rule


# ---------------------------------------------------------------------------
# Helpers for the two screens
# ---------------------------------------------------------------------------


def _success_screen() -> Widget:
    """Render the post-authentication success screen.

    Returns:
        A :class:`~tempest_core.widgets.Column` with a success card.
    """
    return Column(
        key="success-screen",
        style=Style(
            gap=20.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            Text(
                content="Welcome back!",
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#16a34a"),
                    text_align=TextAlign.CENTER,
                ),
                key="welcome-heading",
            ),
            Card(
                key="success-card",
                children=[
                    Text(
                        content="You are now authenticated.",
                        style=Style(
                            font_size=15.0,
                            text_align=TextAlign.CENTER,
                        ),
                        key="success-body",
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[LoginState]) -> Widget:
    """Render the login form from the current application state.

    Builds a :class:`~tempest_core.widgets.Form` that:

    * Validates the email field (required + syntactically valid).
    * Validates the password field (required + minimum 8 characters).
    * On a valid form, checks the credentials against a fake store and either
      sets :attr:`LoginState.authenticated` to ``True`` or writes an error
      banner message.
    * Shows a green success screen once authenticated.

    Args:
        app: The application handle providing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    if app.state.authenticated:
        return _success_screen()

    # ---- handlers ----------------------------------------------------------

    def on_email_change(value: str) -> None:
        """Update the email field and clear the auth error.

        Args:
            value: The new value typed by the user.
        """

        def _set(s: LoginState) -> None:
            s.email = value
            s.auth_error = ""

        app.set_state(_set)

    def on_password_change(value: str) -> None:
        """Update the password field and clear the auth error.

        Args:
            value: The new value typed by the user.
        """

        def _set(s: LoginState) -> None:
            s.password = value
            s.auth_error = ""

        app.set_state(_set)

    # ---- form --------------------------------------------------------------

    form = Form(
        key="login-form",
        fields=[
            FormField(
                name="email",
                label="E-mail",
                validators=[
                    _require("E-mail is required"),
                    _valid_email("Enter a valid e-mail address"),
                ],
                error=app.state.errors.get("email", ""),
                child=EmailInput(
                    value=app.state.email,
                    label="E-mail",
                    placeholder="you@example.com",
                    error=app.state.errors.get("email", ""),
                    on_change=on_email_change,
                    key="email-brfield",
                ),
            ),
            FormField(
                name="password",
                label="Password",
                validators=[
                    _require("Password is required"),
                    _min_length(8, "Password must be at least 8 characters"),
                ],
                error=app.state.errors.get("password", ""),
                child=PasswordInput(
                    value=app.state.password,
                    label="Password",
                    placeholder="Enter your password",
                    error=app.state.errors.get("password", ""),
                    on_change=on_password_change,
                    key="password-brfield",
                ),
            ),
        ],
    )

    # ---- submit handler ----------------------------------------------------

    def submit() -> None:
        """Validate fields and, if valid, check credentials.

        Runs the :class:`~tempest_core.widgets.Form` validators first. If
        the form is invalid the per-field errors are reflected into state so the
        components re-render with their red error messages. If the form is valid
        the credentials are checked against the fake store; a mismatch writes an
        ``auth_error`` banner rather than a field error.
        """
        result: FormState = form.validate(
            {"email": app.state.email, "password": app.state.password}
        )

        if not result.valid:

            def apply_errors(s: LoginState) -> None:
                s.errors = dict(result.errors)
                s.auth_error = ""

            app.set_state(apply_errors)
            return

        # Credential check (synchronous stub — real apps use async I/O).
        expected = _VALID_CREDENTIALS.get(app.state.email.strip())
        if expected is None or expected != app.state.password:

            def set_auth_error(s: LoginState) -> None:
                s.auth_error = "Invalid e-mail or password. Please try again."
                s.errors = {}

            app.set_state(set_auth_error)
            return

        def authenticate(s: LoginState) -> None:
            s.authenticated = True
            s.errors = {}
            s.auth_error = ""

        app.set_state(authenticate)

    # ---- tree --------------------------------------------------------------

    children: list[Widget] = []

    # Auth-level error banner (wrong credentials, shown above the form).
    if app.state.auth_error:
        children.append(
            Banner(
                message=app.state.auth_error,
                tone="error",
                key="auth-error-banner",
            )
        )

    children += [
        Text(
            content="Sign in to your account",
            style=Style(
                font_size=22.0,
                font_weight=FontWeight.BOLD,
                text_align=TextAlign.CENTER,
            ),
            key="login-heading",
        ),
        Divider(key="heading-divider"),
        form,
        Button(
            label="Sign in",
            on_click=submit,
            key="submit-btn",
        ),
    ]

    return Column(
        key="login-screen",
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=children,
    )
```

---

## Explicando peça por peça

### 1. O estado: cinco campos, duas responsabilidades

```python
@dataclass
class LoginState:
    email: str = ""
    password: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    auth_error: str = ""
    authenticated: bool = False
    loading: bool = False
```

O estado tem dois "planos" de erro separados:

- **`errors`** — erros de validação de campo (`{"email": "...", "password": "..."}`),
  produzidos pelos validators do `Form` antes de qualquer requisição.
- **`auth_error`** — erro de nível de autenticação, produzido quando as credenciais
  são válidas individualmente mas incorretas como par.

Essa separação é importante: quando o submit falha na validação de campo, o
`auth_error` é zerado; quando falha na checagem de credenciais, o `errors` é
zerado. Os dois tipos de erro nunca coexistem.

!!! tip "Dica"
    `field(default_factory=dict)` é o padrão correto para campos mutáveis em
    dataclasses. Sem o `default_factory`, todos os objetos `LoginState` compartilhariam
    o mesmo dicionário — um bug silencioso muito comum.

---

### 2. Os três validators

O app define três funções fábrica de validators — cada uma devolve um `Validator`
(um `Callable[[Any], str | None]`):

```python
def _require(message: str) -> Validator:
    def rule(value: Any) -> str | None:
        return message if not str(value).strip() else None
    return rule


def _valid_email(message: str) -> Validator:
    def rule(value: Any) -> str | None:
        text = str(value).strip()
        return None if _EMAIL_RE.fullmatch(text) else message
    return rule


def _min_length(length: int, message: str) -> Validator:
    def rule(value: Any) -> str | None:
        return message if len(str(value)) < length else None
    return rule
```

Cada validator devolve `None` quando a regra passa, ou a string de mensagem de
erro quando falha. Esse contrato é simples de testar isoladamente:

- `_require("Campo obrigatório")("")` → `"Campo obrigatório"`
- `_require("Campo obrigatório")("admin@example.com")` → `None`
- `_valid_email("E-mail inválido")("nao-e-email")` → `"E-mail inválido"`
- `_min_length(8, "Mínimo 8 caracteres")("abc")` → `"Mínimo 8 caracteres"`

!!! info "Por que fábricas e não validators fixos?"
    As fábricas (`_require(msg)`, `_min_length(n, msg)`) permitem customizar a
    mensagem e o limite sem herança nem configuração global. O `FormField` recebe
    uma lista simples de callables.

---

### 3. `Form`, `FormField` e os componentes de campo

```python
form = Form(
    key="login-form",
    fields=[
        FormField(
            name="email",
            label="E-mail",
            validators=[
                _require("E-mail is required"),
                _valid_email("Enter a valid e-mail address"),
            ],
            error=app.state.errors.get("email", ""),
            child=EmailInput(
                value=app.state.email,
                label="E-mail",
                placeholder="you@example.com",
                error=app.state.errors.get("email", ""),
                on_change=on_email_change,
                key="email-brfield",
            ),
        ),
        FormField(
            name="password",
            label="Password",
            validators=[
                _require("Password is required"),
                _min_length(8, "Password must be at least 8 characters"),
            ],
            error=app.state.errors.get("password", ""),
            child=PasswordInput(
                value=app.state.password,
                label="Password",
                placeholder="Enter your password",
                error=app.state.errors.get("password", ""),
                on_change=on_password_change,
                key="password-brfield",
            ),
        ),
    ],
)
```

Repare na **dupla responsabilidade do `error`**:

- `FormField(error=...)` — usado pelo Form internamente para rastrear o estado
  de erro do campo na árvore de IR.
- `EmailInput(error=...)` / `PasswordInput(error=...)` — usado pelo componente
  visual para renderizar o texto vermelho abaixo do campo.

Ambos leem `app.state.errors.get("email", "")`, então ficam perfeitamente
sincronizados.

!!! warning "Aviso"
    O `EmailInput` e o `PasswordInput` são componentes de formulário pré-construídos
    (`_core.components`), não widgets básicos. Eles encapsulam o `type="email"` e
    `type="password"` do DOM, o ícone de visibilidade da senha e o estilo de erro
    padrão. Use-os em vez do `Input` bruto sempre que o contexto for autenticação.

---

### 4. Os handlers de campo

```python
def on_email_change(value: str) -> None:
    def _set(s: LoginState) -> None:
        s.email = value
        s.auth_error = ""

    app.set_state(_set)
```

Cada handler faz duas coisas ao mesmo tempo:

1. **Atualiza o campo** com o novo valor digitado.
2. **Limpa o `auth_error`** — assim, se o usuário começar a corrigir o e-mail
   depois de uma tentativa de login com credenciais erradas, o banner vermelho
   desaparece imediatamente, dando feedback de que o app registrou a correção.

!!! tip "Dica"
    Essa limpeza do `auth_error` on-the-fly é um detalhe de UX que faz grande
    diferença: o usuário não fica olhando para uma mensagem de erro que já não
    se aplica ao que está digitando.

---

### 5. O handler de submit: validação em três camadas

```python
def submit() -> None:
    result: FormState = form.validate(
        {"email": app.state.email, "password": app.state.password}
    )

    if not result.valid:
        def apply_errors(s: LoginState) -> None:
            s.errors = dict(result.errors)
            s.auth_error = ""
        app.set_state(apply_errors)
        return

    # Credential check
    expected = _VALID_CREDENTIALS.get(app.state.email.strip())
    if expected is None or expected != app.state.password:
        def set_auth_error(s: LoginState) -> None:
            s.auth_error = "Invalid e-mail or password. Please try again."
            s.errors = {}
        app.set_state(set_auth_error)
        return

    def authenticate(s: LoginState) -> None:
        s.authenticated = True
        s.errors = {}
        s.auth_error = ""
    app.set_state(authenticate)
```

O submit percorre três camadas sequenciais:

| Camada | O que verifica | Onde aparece o erro |
|--------|---------------|---------------------|
| **1. Obrigatoriedade** | Campo vazio | Inline no `EmailInput` / `PasswordInput` |
| **2. Formato** | E-mail válido / senha ≥ 8 chars | Inline no campo |
| **3. Credenciais** | Par e-mail + senha no "banco" | `Banner(tone="error")` acima do form |

Somente quando as três camadas passam o estado é atualizado para
`authenticated = True` e a tela de sucesso é renderizada.

!!! note "Nota"
    `form.validate({"email": ..., "password": ...})` executa os validators de
    **todos** os `FormField` de uma vez e devolve um `FormState` com:
    - `result.valid` — `True` se todos os campos passaram.
    - `result.errors` — dicionário `{field_name: error_message}` dos campos que falharam.

---

### 6. O banner de erro de autenticação

```python
children: list[Widget] = []

if app.state.auth_error:
    children.append(
        Banner(
            message=app.state.auth_error,
            tone="error",
            key="auth-error-banner",
        )
    )
```

O `Banner` só entra na árvore quando há `auth_error`. Quando o campo está vazio
(estado inicial ou após o usuário começar a digitar de novo), o banner simplesmente
não existe no IR — sem `visible=False`, sem opacidade zero. O reconciliador
detecta a adição/remoção do nó e emite os patches corretos.

!!! info "Por que `tone=\"error\"` e não uma cor direta?"
    O `Banner` abstrai o significado semântico do alerta. `tone="error"` mapeia
    para vermelho no tema padrão, mas o tema pode ser customizado sem tocar em
    nenhum `app.py`. Tons disponíveis: `"info"`, `"success"`, `"warning"`,
    `"error"`.

---

### 7. A tela de sucesso por troca de árvore

```python
def view(app: App[LoginState]) -> Widget:
    if app.state.authenticated:
        return _success_screen()
    ...
```

Quando `authenticated` vira `True`, a `view` retorna **uma árvore completamente
diferente** — não esconde campos, não sobrepõe camadas. O reconciliador compara
a árvore anterior (form) com a nova (success screen) e emite apenas os patches
mínimos necessários para a transição.

```python
def _success_screen() -> Widget:
    return Column(
        key="success-screen",
        style=Style(
            gap=20.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            Text(
                content="Welcome back!",
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#16a34a"),
                    text_align=TextAlign.CENTER,
                ),
                key="welcome-heading",
            ),
            Card(
                key="success-card",
                children=[
                    Text(
                        content="You are now authenticated.",
                        style=Style(
                            font_size=15.0,
                            text_align=TextAlign.CENTER,
                        ),
                        key="success-body",
                    ),
                ],
            ),
        ],
    )
```

O `Card` é um componente de contêiner com sombra e borda arredondada — útil para
agrupar conteúdo relacionado visualmente. Aqui ele age como um "cartão de
boas-vindas" na tela de sucesso.

!!! check "Troca de tela sem router"
    Neste app simples, a "navegação" é apenas uma flag booleana no estado.
    Para apps com múltiplas telas use o sistema de navegação do tempestweb —
    veja [Navegação](../tutorial/index.md).

---

## Rodando o app 🚀

Salve o arquivo em `examples/login-form/app.py` e escolha o modo:

=== "Modo WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm examples/login-form/app.py
    ```

    O Pyodide carrega o Python completo no browser. Todos os validators e
    handlers rodam localmente no tab — sem WebSocket, sem servidor.

=== "Modo Server (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/login-form/app.py
    ```

    Um servidor FastAPI sobe localmente. O cliente JS envia os eventos de
    digitação e recebe patches do reconciliador via WebSocket.

!!! check "Mesmo código, dois modos"
    O `app.py` não referencia nem `wasm` nem `server` em lugar algum. A camada
    de transporte fica completamente encapsulada no tempestweb — você escolhe
    apenas na hora de rodar.

Abra o browser em `http://localhost:8000`. Experimente os cenários:

1. **Submit vazio** → erros inline em ambos os campos.
2. **E-mail inválido** → erro inline só no campo de e-mail.
3. **Senha com menos de 8 caracteres** → erro inline só no campo de senha.
4. **Credenciais erradas** (`teste@exemplo.com` / `qualquercoisa`) → banner
   vermelho acima do form.
5. **Credenciais corretas** (`admin@example.com` / `secret1234`) → tela de
   sucesso verde. ✅

---

## Recapitulando

Neste exemplo você aprendeu:

- ✅ **`EmailInput` e `PasswordInput`** — componentes pré-construídos com semântica,
  estilo e prop `error` integrados.
- ✅ **`Form` + `FormField` + `Validator`** — a tríade que separa regras de validação
  do render e do estado.
- ✅ **Dois planos de erro** — `errors` (campo a campo, validators) e `auth_error`
  (nível de autenticação, lógica de negócio).
- ✅ **`form.validate()`** — executa todos os validators de uma vez e devolve
  `FormState.valid` + `FormState.errors`.
- ✅ **`Banner(tone="error")`** — erro semântico acima do form, presente na árvore
  apenas quando necessário.
- ✅ **Troca de árvore por flag booleana** — `authenticated = True` faz a `view`
  retornar uma árvore completamente diferente, sem visibilidade condicional.
- ✅ **Limpeza de erros on-the-fly** — os handlers de campo limpam o `auth_error`
  ao digitar, evitando mensagens obsoletas.

---

## Próximos passos

- Leia o [Tutorial do Counter](../tutorial/index.md) se ainda não o fez — ele
  explica `set_state` e o ciclo de rebuild com mais detalhes.
- Veja o exemplo de [Conversor de Temperatura](./temperature-converter.md) para
  aprofundar two-way binding com campos controlados.
- Explore o exemplo de [Stopwatch](./stopwatch.md) para ver como o estado evolui
  em resposta a eventos de timer.
- Consulte [Patches na rede](../tutorial/patches.md) para entender quais operações
  o reconciliador emite durante a transição form → tela de sucesso.
