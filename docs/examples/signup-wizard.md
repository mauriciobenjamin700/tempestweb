# Wizard de Cadastro em Múltiplos Passos

🚀 Construa um formulário de registro em três etapas — Conta, Perfil e Revisão —
onde cada etapa valida seus próprios campos antes de avançar.

---

## O que você vai construir

Um wizard de cadastro com três telas encadeadas:

| Etapa | Nome          | Campos                                         |
|-------|---------------|------------------------------------------------|
| 1     | Conta         | E-mail, senha, confirmação de senha            |
| 2     | Perfil        | Nome de exibição, função (dropdown), bio       |
| 3     | Revisão       | Resumo somente-leitura + aceite dos termos     |

Um índice `step` no estado decide qual etapa está visível. O botão **Próximo** só
avança quando todos os `FormField` da etapa passam nos `Validator`s encadeados.
O botão **Voltar** sempre recua sem re-validar. Ao confirmar na etapa 3, uma
mensagem de sucesso substitui o wizard.

---

## Por que um wizard?

Formulários longos assustam. Dividir o cadastro em passos menores cria uma
experiência progressiva: o usuário preenche apenas o que é necessário naquele
momento e recebe feedback imediato sobre erros antes de prosseguir.

O padrão que você vai aprender aqui — estado de índice + `Form.validate()` como
portão — é reutilizável em qualquer fluxo de múltiplas etapas.

---

## Arquivo completo

Salve o arquivo abaixo em `examples/signup-wizard/app.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    Dropdown,
    Form,
    FormField,
    FormState,
    Input,
    Row,
    Text,
    TextArea,
    Validator,
)
from tempest_core.widgets.events import SelectEvent, TextChangeEvent

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

TOTAL_STEPS: int = 3

ROLE_OPTIONS: list[str] = [
    "Developer",
    "Designer",
    "Product Manager",
    "Data Scientist",
    "Other",
]


@dataclass
class WizardState:
    """Mutable state for the multi-step signup wizard."""

    step: int = 0
    email: str = ""
    password: str = ""
    confirm_password: str = ""
    display_name: str = ""
    role: str = ""
    bio: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False
    accept_terms: bool = False


def make_state() -> WizardState:
    """Build the initial wizard state at step 0 with all fields blank."""
    return WizardState()


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _require(message: str) -> Validator:
    def rule(value: Any) -> str | None:
        return message if not str(value).strip() else None
    return rule


def _email_format() -> Validator:
    _pattern: re.Pattern[str] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def rule(value: Any) -> str | None:
        return None if _pattern.match(str(value)) else "Enter a valid email address"

    return rule


def _min_length(length: int) -> Validator:
    def rule(value: Any) -> str | None:
        return (
            None
            if len(str(value)) >= length
            else f"Must be at least {length} characters"
        )
    return rule


def _has_digit() -> Validator:
    def rule(value: Any) -> str | None:
        return None if any(c.isdigit() for c in str(value)) else "Must contain a digit"
    return rule


def _has_upper() -> Validator:
    def rule(value: Any) -> str | None:
        return (
            None
            if any(c.isupper() for c in str(value))
            else "Must contain an uppercase letter"
        )
    return rule


def _passwords_match(get_password: Any) -> Validator:
    def rule(value: Any) -> str | None:
        return None if str(value) == str(get_password()) else "Passwords do not match"
    return rule


def _role_chosen() -> Validator:
    def rule(value: Any) -> str | None:
        return None if str(value).strip() else "Please select a role"
    return rule


def _max_length(length: int) -> Validator:
    def rule(value: Any) -> str | None:
        return (
            None
            if len(str(value)) <= length
            else f"Must be at most {length} characters"
        )
    return rule


def _terms_accepted() -> Validator:
    def rule(value: Any) -> str | None:
        v = str(value).lower()
        if v in ("true", "1", "yes"):
            return None
        return "You must accept the terms to continue"
    return rule


# ---------------------------------------------------------------------------
# Step indicator helper
# ---------------------------------------------------------------------------


def _step_indicator(current: int, total: int) -> Widget:
    """Render a simple text step indicator."""
    return Text(
        content=f"Step {current + 1} of {total}",
        key="step-indicator",
    )


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------


def view(app: App[WizardState]) -> Widget:
    """Render the multi-step signup wizard from the current state."""
    state: WizardState = app.state

    # Handlers for step 1
    def on_email_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "email", event.value))

    def on_password_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "password", event.value))

    def on_confirm_password_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "confirm_password", event.value))

    # Handlers for step 2
    def on_display_name_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "display_name", event.value))

    def on_role_select(event: SelectEvent) -> None:
        app.set_state(lambda s: setattr(s, "role", event.value))

    def on_bio_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "bio", event.value))

    # Handler for step 3
    def on_terms_change(event: TextChangeEvent) -> None:
        accepted: bool = event.value.strip().lower() == "true"
        app.set_state(lambda s: setattr(s, "accept_terms", accepted))

    # Assemble forms
    form1: Form = Form(
        key="form-step1",
        fields=[
            FormField(
                name="email",
                label="Email address",
                validators=[_require("Email is required"), _email_format()],
                error=state.errors.get("email", ""),
                child=Input(
                    key="input-email",
                    value=state.email,
                    placeholder="you@example.com",
                    on_change=on_email_change,
                ),
            ),
            FormField(
                name="password",
                label="Password",
                validators=[
                    _require("Password is required"),
                    _min_length(8),
                    _has_digit(),
                    _has_upper(),
                ],
                error=state.errors.get("password", ""),
                child=Input(
                    key="input-password",
                    value=state.password,
                    placeholder="Min 8 chars, 1 digit, 1 uppercase",
                    secure=True,
                    on_change=on_password_change,
                ),
            ),
            FormField(
                name="confirm_password",
                label="Confirm password",
                validators=[
                    _require("Please confirm your password"),
                    _passwords_match(lambda: state.password),
                ],
                error=state.errors.get("confirm_password", ""),
                child=Input(
                    key="input-confirm-password",
                    value=state.confirm_password,
                    placeholder="Repeat password",
                    secure=True,
                    on_change=on_confirm_password_change,
                ),
            ),
        ],
    )

    form2: Form = Form(
        key="form-step2",
        fields=[
            FormField(
                name="display_name",
                label="Display name",
                validators=[
                    _require("Display name is required"),
                    _min_length(2),
                    _max_length(50),
                ],
                error=state.errors.get("display_name", ""),
                child=Input(
                    key="input-display-name",
                    value=state.display_name,
                    placeholder="How others will see you",
                    max_length=50,
                    on_change=on_display_name_change,
                ),
            ),
            FormField(
                name="role",
                label="Role",
                validators=[_role_chosen()],
                error=state.errors.get("role", ""),
                child=Dropdown(
                    key="dropdown-role",
                    options=ROLE_OPTIONS,
                    value=state.role if state.role else None,
                    placeholder="Select your role…",
                    on_select=on_role_select,
                ),
            ),
            FormField(
                name="bio",
                label="Short bio (optional)",
                validators=[_max_length(200)],
                error=state.errors.get("bio", ""),
                child=TextArea(
                    key="textarea-bio",
                    value=state.bio,
                    placeholder="Tell us a little about yourself",
                    rows=3,
                    max_length=200,
                    on_change=on_bio_change,
                ),
            ),
        ],
    )

    form3: Form = Form(
        key="form-step3",
        fields=[
            FormField(
                name="accept_terms",
                label="Accept terms of service",
                validators=[_terms_accepted()],
                error=state.errors.get("accept_terms", ""),
                child=Input(
                    key="input-terms",
                    value="true" if state.accept_terms else "false",
                    placeholder="Type 'true' to accept",
                    on_change=on_terms_change,
                ),
            ),
        ],
    )

    # Navigation
    def go_back() -> None:
        def mutate(s: WizardState) -> None:
            s.step = max(0, s.step - 1)
            s.errors = {}
        app.set_state(mutate)

    def go_next() -> None:
        current: int = state.step
        if current == 0:
            values: dict[str, str] = {
                "email": state.email,
                "password": state.password,
                "confirm_password": state.confirm_password,
            }
            result: FormState = form1.validate(values)
        elif current == 1:
            values = {
                "display_name": state.display_name,
                "role": state.role,
                "bio": state.bio,
            }
            result = form2.validate(values)
        else:
            result = FormState(valid=True)

        def mutate(s: WizardState) -> None:
            s.errors = dict(result.errors)
            if result.valid:
                s.step = min(TOTAL_STEPS - 1, s.step + 1)

        app.set_state(mutate)

    def submit() -> None:
        result: FormState = form3.validate(
            {"accept_terms": "true" if state.accept_terms else "false"}
        )

        def mutate(s: WizardState) -> None:
            s.errors = dict(result.errors)
            s.submitted = result.valid

        app.set_state(mutate)

    # Build active step body
    if state.submitted:
        body: Widget = Column(
            key="success-body",
            style=Style(gap=8.0),
            children=[
                Text(content="Account created!", key="success-title"),
                Text(content=f"Welcome, {state.display_name}!", key="success-welcome"),
                Text(
                    content=f"A confirmation email is on its way to {state.email}.",
                    key="success-email",
                ),
            ],
        )
    elif state.step == 0:
        body = Column(
            key="step1-body",
            style=Style(gap=12.0),
            children=[
                Text(content="Step 1: Account credentials", key="step1-title"),
                form1,
                Row(
                    key="step1-nav",
                    style=Style(gap=8.0),
                    children=[
                        Button(key="btn-next-1", label="Next →", on_click=go_next),
                    ],
                ),
            ],
        )
    elif state.step == 1:
        body = Column(
            key="step2-body",
            style=Style(gap=12.0),
            children=[
                Text(content="Step 2: Your profile", key="step2-title"),
                form2,
                Row(
                    key="step2-nav",
                    style=Style(gap=8.0),
                    children=[
                        Button(key="btn-back-2", label="← Back", on_click=go_back),
                        Button(key="btn-next-2", label="Next →", on_click=go_next),
                    ],
                ),
            ],
        )
    else:
        body = Column(
            key="step3-body",
            style=Style(gap=12.0),
            children=[
                Text(content="Step 3: Review & submit", key="step3-title"),
                Text(content=f"Email: {state.email}", key="review-email"),
                Text(content=f"Name: {state.display_name}", key="review-name"),
                Text(content=f"Role: {state.role}", key="review-role"),
                form3,
                Row(
                    key="step3-nav",
                    style=Style(gap=8.0),
                    children=[
                        Button(key="btn-back-3", label="← Back", on_click=go_back),
                        Button(
                            key="btn-submit",
                            label="Create account",
                            on_click=submit,
                        ),
                    ],
                ),
            ],
        )

    return Column(
        key="wizard-root",
        style=Style(gap=16.0, padding=Edge.all(20)),
        children=[
            _step_indicator(state.step, TOTAL_STEPS),
            body,
        ],
    )
```

---

## Executando o exemplo

Abra um terminal na raiz do projeto e escolha o modo:

=== "Modo A — WASM (Pyodide)"

    ```bash
    tempestweb dev --mode wasm --path examples/signup-wizard
    ```

    Python roda diretamente no browser via Pyodide. Nenhum servidor de backend é
    necessário.

=== "Modo B — Servidor (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server --path examples/signup-wizard
    ```

    Python roda no servidor; um cliente JS fino se conecta por WebSocket e aplica
    os patches ao DOM.

!!! note "Mesma `view` nos dois modos"
    A função `view` e toda a lógica de validação são **idênticas** nos dois modos.
    A única diferença é onde o Python é executado — no browser ou no servidor.

---

## Entendendo o código passo a passo

### 1. O estado do wizard

```python
@dataclass
class WizardState:
    step: int = 0
    email: str = ""
    password: str = ""
    confirm_password: str = ""
    display_name: str = ""
    role: str = ""
    bio: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False
    accept_terms: bool = False
```

`step` é o índice da etapa atual (0, 1 ou 2). `errors` é um dicionário que mapeia
o nome do campo ao texto do erro exibido abaixo dele. `submitted` vira `True`
após o formulário final passar na validação.

!!! tip "dica — dataclass vs. dict"
    Usar um `@dataclass` torna o estado auto-documentado e oferece autocomplete no
    editor. O tempestweb aceita qualquer objeto mutável — mas dataclass é a
    escolha recomendada.

---

### 2. Validators compostos

Cada campo recebe uma lista de `Validator`s. Um `Validator` é simplesmente uma
função `(Any) -> str | None` — retorna uma string de erro ou `None` quando tudo
está bem.

```python
def _min_length(length: int) -> Validator:
    def rule(value: Any) -> str | None:
        return (
            None
            if len(str(value)) >= length
            else f"Must be at least {length} characters"
        )
    return rule
```

Você pode encadear quantos quiser no mesmo `FormField`:

```python
FormField(
    name="password",
    label="Password",
    validators=[
        _require("Password is required"),
        _min_length(8),
        _has_digit(),
        _has_upper(),
    ],
    ...
)
```

O `Form` executa os validators na ordem e para no primeiro erro de cada campo.

!!! tip "dica — validators com closure"
    `_passwords_match` recebe um callable `get_password` em vez de um valor
    estático. Isso evita uma closure estale sobre uma variável mutável: sempre
    lê a senha atual ao ser invocado.

    ```python
    _passwords_match(lambda: state.password)
    ```

---

### 3. Construindo os formulários dentro de `view`

Os três `Form`s são construídos dentro de `view` a cada render. Isso garante que
os handlers de evento e os valores do estado estejam sempre frescos:

```python
form1: Form = Form(
    key="form-step1",
    fields=[
        FormField(
            name="email",
            label="Email address",
            validators=[_require("Email is required"), _email_format()],
            error=state.errors.get("email", ""),
            child=Input(
                key="input-email",
                value=state.email,
                placeholder="you@example.com",
                on_change=on_email_change,
            ),
        ),
        ...
    ],
)
```

O campo `error` passa a mensagem de erro atual (vinda de `state.errors`) para o
`FormField`, que a exibe abaixo do input.

---

### 4. O portão `go_next`

Este é o coração do wizard. `go_next` chama `form.validate(values)`, que retorna
um `FormState` com `valid: bool` e `errors: dict[str, str]`:

```python
def go_next() -> None:
    current: int = state.step
    if current == 0:
        values: dict[str, str] = {
            "email": state.email,
            "password": state.password,
            "confirm_password": state.confirm_password,
        }
        result: FormState = form1.validate(values)
    elif current == 1:
        values = {
            "display_name": state.display_name,
            "role": state.role,
            "bio": state.bio,
        }
        result = form2.validate(values)
    else:
        result = FormState(valid=True)

    def mutate(s: WizardState) -> None:
        s.errors = dict(result.errors)
        if result.valid:
            s.step = min(TOTAL_STEPS - 1, s.step + 1)

    app.set_state(mutate)
```

Se `result.valid` for `False`, apenas os erros são gravados no estado — o passo
**não** avança. O reconciliador re-renderiza com os erros visíveis abaixo de
cada campo.

!!! warning "aviso — valide antes de avançar"
    Nunca incremente `step` diretamente sem chamar `validate()`. O estado de erros
    ficaria desatualizado e campos inválidos passariam despercebidos.

---

### 5. Navegação por índice de estado

O bloco `if/elif/else` escolhe qual corpo renderizar:

```python
elif state.step == 0:
    body = Column(
        key="step1-body",
        ...
        children=[
            Text(content="Step 1: Account credentials", key="step1-title"),
            form1,
            Row(
                key="step1-nav",
                style=Style(gap=8.0),
                children=[
                    Button(key="btn-next-1", label="Next →", on_click=go_next),
                ],
            ),
        ],
    )
```

!!! info "info — keys estáveis"
    Cada widget precisa de um `key` único e **estável** entre renders. Isso permite
    ao reconciliador aplicar patches mínimos ao DOM em vez de recriar toda a
    árvore.

---

### 6. O indicador de progresso

```python
def _step_indicator(current: int, total: int) -> Widget:
    return Text(
        content=f"Step {current + 1} of {total}",
        key="step-indicator",
    )
```

Sempre renderizado na raiz, acima do corpo, mostra ao usuário onde ele está.

---

### 7. Tela de sucesso

Quando `state.submitted` é `True`, o wizard é substituído por uma mensagem de
confirmação:

```python
if state.submitted:
    body = Column(
        key="success-body",
        style=Style(gap=8.0),
        children=[
            Text(content="Account created!", key="success-title"),
            Text(content=f"Welcome, {state.display_name}!", key="success-welcome"),
            Text(
                content=f"A confirmation email is on its way to {state.email}.",
                key="success-email",
            ),
        ],
    )
```

---

## Fluxo completo de dados

```
Usuário digita → on_*_change → app.set_state → re-render
Usuário clica "Próximo" → go_next → form.validate → set_state(errors + step)
Usuário clica "Voltar" → go_back → set_state(step-1, errors={})
Usuário clica "Criar conta" → submit → form3.validate → set_state(submitted=True)
```

---

## Verificando a qualidade do código

Antes de commitar, rode as quatro verificações:

```bash
ruff check examples/signup-wizard/app.py
ruff format --check examples/signup-wizard/app.py
mypy examples/signup-wizard/app.py
pytest -q
```

✅ Todos os quatro passam sem erros.

---

## Recapitulando

Neste tutorial você aprendeu a:

- Gerenciar uma etapa ativa com um índice `step` no estado.
- Criar `Validator`s reutilizáveis como funções de ordem superior.
- Encadear múltiplos validators num único `FormField`.
- Usar `Form.validate()` como portão antes de avançar a etapa.
- Propagar erros do `FormState` de volta para o estado do app.
- Substituir o wizard por uma tela de sucesso após o submit.

---

## Próximos passos

- 💡 Veja o tutorial completo de estado em [../tutorial/index.md](../tutorial/index.md).
- 🔗 Explore o exemplo de [abas de perfil](tabs-profile.md) para outra forma de
  navegação por índice.
- 🔗 Veja o exemplo de [conversor de temperatura](temperature-converter.md) para
  uma introdução mais simples ao ciclo estado → view → evento.
