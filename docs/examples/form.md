# Formulário — `Form` + `FormField` + validadores tipados 📝

**Modos: A/B** — usa widgets de formulário e o formato Python de evento (`event.value`).

Um formulário de cadastro que **valida antes de enviar**: dois campos (e-mail e
senha) agregados por um `Form`, cada um envolto num `FormField` com regras de
validação que rodam **puramente em Python**. Erros voltam espelhados em cada
campo. 🚀

!!! note "Por que uma camada de formulário?"
    Você poderia validar à mão em cada handler, mas o `Form` centraliza a
    agregação: um `Form.validate(values)` roda todos os validadores de uma vez e
    devolve um `FormState` com `valid` e um dicionário de `errors` por campo.

---

## O que este exemplo mostra

- **`Form`** agregando dois **`FormField`**, cada um envolvendo um `Input`.
- **`Validator` tipados** — funções `value -> str | None` (mensagem de erro ou
  `None`). O exemplo define `_require` e `_min_length`.
- **`Form.validate(values)`** devolvendo um `FormState` (`valid`, `errors`).
- **Erros espelhados no estado** — cada `FormField` recebe seu erro de volta via
  `error=app.state.errors.get(name, "")`.

---

## Rodando ▶

```bash
tempestweb dev --mode wasm     --path examples/form   # Python no browser (Pyodide)
tempestweb dev --mode server   --path examples/form   # Python no servidor (FastAPI + WS)
```

---

## O código

```python
"""Sign-up form — exercises the form aggregation widgets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    Form,
    FormField,
    FormState,
    Input,
    Text,
    Validator,
)
from tempest_core.widgets.events import TextChangeEvent


@dataclass
class FormDataState:
    """State for the sign-up form app.

    Attributes:
        email: The current value of the email field.
        password: The current value of the password field.
        errors: The per-field validation errors from the last submit attempt.
        submitted: Whether a valid submit has happened.
    """

    email: str = ""
    password: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False


def make_state() -> FormDataState:
    """Build the initial, empty form state.

    Returns:
        A fresh :class:`FormDataState`.
    """
    return FormDataState()


def _require(message: str) -> Validator:
    """Build a validator rejecting empty/blank values.

    Args:
        message: The error message shown when the value is blank.

    Returns:
        A validator returning ``message`` for a blank value, else ``None``.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401 — opaque field value
        return message if not str(value).strip() else None

    return rule


def _min_length(length: int, message: str) -> Validator:
    """Build a validator enforcing a minimum length.

    Args:
        length: The minimum acceptable number of characters.
        message: The error message shown when the value is too short.

    Returns:
        A validator returning ``message`` for a too-short value, else ``None``.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401 — opaque field value
        return message if len(str(value)) < length else None

    return rule


def view(app: App[FormDataState]) -> Widget:
    """Render the sign-up form from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def edit_email(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "email", event.value))

    def edit_password(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "password", event.value))

    form = Form(
        key="signup",
        fields=[
            FormField(
                name="email",
                label="Email",
                validators=[_require("Email is required")],
                error=app.state.errors.get("email", ""),
                child=Input(
                    value=app.state.email,
                    placeholder="you@example.com",
                    on_change=edit_email,
                    key="email-input",
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
                child=Input(
                    value=app.state.password,
                    placeholder="••••••••",
                    secure=True,
                    on_change=edit_password,
                    key="password-input",
                ),
            ),
        ],
    )

    def submit() -> None:
        result: FormState = form.validate(
            {"email": app.state.email, "password": app.state.password}
        )

        def mutate(s: FormDataState) -> None:
            s.errors = dict(result.errors)
            s.submitted = result.valid

        app.set_state(mutate)

    status = "Welcome!" if app.state.submitted else "Please sign up"
    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content=status, key="status"),
            form,
            Button(label="Sign up", on_click=submit, key="submit"),
        ],
    )
```

---

## Peça por peça

### Validadores são funções

```python
def _require(message: str) -> Validator:
    def rule(value: Any) -> str | None:
        return message if not str(value).strip() else None
    return rule
```

Um `Validator` é só uma função `value -> str | None`: devolve a **mensagem de
erro** quando inválido, ou `None` quando ok. `_require` e `_min_length` são
fábricas que capturam a mensagem — o campo de senha empilha os dois.

### O `Form` agrega os campos

Cada `FormField` declara `name`, `label`, uma lista de `validators`, o `error`
atual (vindo do estado) e o widget filho (`child=Input(...)`). O `Form` só junta
tudo — a validação acontece na hora do submit.

### Validar no submit

```python
def submit() -> None:
    result: FormState = form.validate(
        {"email": app.state.email, "password": app.state.password}
    )
    def mutate(s: FormDataState) -> None:
        s.errors = dict(result.errors)
        s.submitted = result.valid
    app.set_state(mutate)
```

`form.validate(values)` roda todos os validadores e devolve um `FormState`. Guardamos
`result.errors` no estado — e como cada `FormField` lê `error=...errors.get(name)`,
o próximo render **espelha o erro** embaixo do campo certo.

!!! tip "Uma direção só"
    O fluxo é sempre: estado → `view` → validação → `set_state` → novo render.
    Nenhum widget guarda estado escondido; a fonte da verdade é o `FormDataState`.

---

## Recapitulando

Neste exemplo você viu:

- ✅ **`Validator`** como funções `value -> str | None`, montadas por fábricas
- ✅ Um **`Form`** agregando dois **`FormField`** com validadores empilhados
- ✅ **`Form.validate`** devolvendo `FormState(valid, errors)`
- ✅ Erros **espelhados no estado** e renderizados sob cada campo
- ✅ O padrão rodando inalterado nos **Modos A/B**

---

## Próximos passos

- 💡 O [Formulário de login](login-form.md) adiciona `EmailInput`/`PasswordInput` e um `Banner`
- 💡 O [Wizard de cadastro](signup-wizard.md) encadeia validação em múltiplos passos
- 💡 O [Cadastro brasileiro](br-cadastro.md) usa validadores BR (CPF/CNPJ) em tempo real
