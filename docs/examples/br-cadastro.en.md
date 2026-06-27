# Brazilian Registration Form (PF/PJ)

> 🚀 **What you'll build:** a complete registration form for individuals (Pessoa Física) and companies (Pessoa Jurídica), with automatic CPF, CNPJ, phone, and address masking, real-time BR validators, and a status banner on submit.

---

## Why this example matters

Brazilian applications must handle tax documents, nationally formatted phone numbers, and addresses with postal codes (CEP).
Doing this "by hand" — regex and `str.replace` scattered through the codebase — quickly becomes a source of subtle bugs and duplicated code.

tempestweb ships a set of ready-made components for this use case:

- **`CPFInput` / `CNPJInput`** — masked inputs with check-digit validation;
- **`PhoneInput`** — automatic `(DDD) 9xxxx-xxxx` mask;
- **`AddressInput`** — a grouped address block (CEP, street, number, complement, neighborhood, city, state);
- **`EmailInput`** — email field with basic format validation;
- **`SegmentedControl`** — PF ↔ PJ mode switch with a single click;
- **`Banner`** — success or error visual feedback after submit.

In this tutorial you will learn to:

- Use `SegmentedControl` to switch between two distinct flows within the same form;
- Connect each field to a handler that clears only its own error while typing;
- Write pure validation functions that return a `dict[str, str]` of errors;
- Conditionally show a `Banner` driven by state after submit;
- Compose everything inside a `Card` with `Divider`s to separate sections.

!!! note "Note"
    This example runs **without any changes** in both modes — WASM (Pyodide in the browser) and Server (FastAPI + WebSocket). The same Python `view()` function serves both.

---

## Prerequisites

Install tempestweb and confirm the CLI is available:

```bash
pip install tempestweb
tempestweb --version
```

!!! tip "Tip"
    Already have tempestweb? Make sure you are on the latest version with `pip install -U tempestweb`.

---

## Project structure

```
examples/
└── br-cadastro/
    └── app.py
```

Create the folder and file:

```bash
mkdir -p examples/br-cadastro
touch examples/br-cadastro/app.py
```

---

## Step 1 — Imports and constants

Open `app.py` and write the imports. Notice the clear separation: generic widgets come from `tempest_core.widgets`, composite components (including all BR inputs) come from `tempest_core.components`, and validators come from `tempest_core.validators`.

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import (
    AddressInput,
    Banner,
    Card,
    CNPJInput,
    CPFInput,
    Divider,
    EmailInput,
    PhoneInput,
    SegmentedControl,
)
from tempest_core.style import Color, Edge, FontWeight
from tempest_core.validators import (
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)
from tempest_core.widgets import Button, Column, Input, Text
```

Right below the imports, define the three module-level constants:

```python
#: The error-text color shared by every inline error message.
_ERROR_COLOR: Color = Color.from_hex("#ef4444")

#: Labels displayed by the SegmentedControl.
_MODES: list[str] = ["Pessoa Física", "Pessoa Jurídica"]

#: Sub-field names managed by AddressInput.
_ADDRESS_FIELDS: tuple[str, ...] = (
    "cep",
    "street",
    "number",
    "complement",
    "neighborhood",
    "city",
    "state",
)
```

**Why module-level constants?**
`_ERROR_COLOR` and `_MODES` are referenced in multiple places inside `view()`. Keeping them at the top avoids repeated literals and makes a future color or label change a one-line edit.

---

## Step 2 — Modeling the state

The state is split into two dataclasses: `AddressData` for the address sub-fields and `CadastroState` for everything else.

```python
@dataclass
class AddressData:
    """Holds every sub-field of a Brazilian address.

    Attributes:
        cep: Postal code (CEP), e.g. ``"01310-100"``.
        street: Street or avenue name.
        number: House or building number.
        complement: Apartment, suite, etc.
        neighborhood: Bairro.
        city: City name.
        state: Two-letter state code (UF).
    """

    cep: str = ""
    street: str = ""
    number: str = ""
    complement: str = ""
    neighborhood: str = ""
    city: str = ""
    state: str = ""


@dataclass
class CadastroState:
    """Top-level application state for the BR registration form.

    Attributes:
        mode: Index into :data:`_MODES`; ``0`` = PF, ``1`` = PJ.
        cpf: CPF value (PF mode).
        cnpj: CNPJ value (PJ mode).
        company_name: Company/trade name (PJ mode).
        phone: Brazilian phone number.
        email: Contact e-mail.
        address: Nested address fields shared by both modes.
        errors: Per-field validation messages from the last submit attempt.
        submitted: Whether the last submit succeeded (all fields valid).
    """

    mode: int = 0
    cpf: str = ""
    cnpj: str = ""
    company_name: str = ""
    phone: str = ""
    email: str = ""
    address: AddressData = field(default_factory=AddressData)
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False


def make_state() -> CadastroState:
    """Build the initial, blank registration state.

    Returns:
        A fresh :class:`CadastroState` ready for the first render.
    """
    return CadastroState()
```

!!! info "Why `field(default_factory=...)`?"
    Python dataclasses **do not allow** mutable values (lists, dicts) as literal defaults — you would get a `ValueError` at class definition time. `field(default_factory=AddressData)` and `field(default_factory=dict)` create a new object per instance, preventing the classic shared-state bug between instances.

**Key point:** `errors` uses the same keys as the fields (`"cpf"`, `"phone"`, `"cep"` etc.). This lets each `Input` look up its own error with `s.errors.get("cpf", "")` without any extra mapping.

---

## Step 3 — Pure validation functions

Validation functions live **outside** `view()`. They take the state and return an error dict — no side effects, easy to unit-test in isolation.

```python
def _validate_pf(s: CadastroState) -> dict[str, str]:
    """Validate all PF (individual) fields and return per-field error messages.

    Args:
        s: The current registration state.

    Returns:
        A mapping of field name → PT-BR error string for every failing field.
        An empty dict means all fields are valid.
    """
    errs: dict[str, str] = {}
    cpf_err = validate_cpf(s.cpf)
    if cpf_err:
        errs["cpf"] = cpf_err
    phone_err = validate_phone(s.phone)
    if phone_err:
        errs["phone"] = phone_err
    email_err = validate_email(s.email)
    if email_err:
        errs["email"] = email_err
    if not s.address.cep.strip():
        errs["cep"] = "CEP é obrigatório"
    if not s.address.street.strip():
        errs["street"] = "Rua é obrigatória"
    if not s.address.city.strip():
        errs["city"] = "Cidade é obrigatória"
    if not s.address.state.strip():
        errs["state"] = "UF é obrigatória"
    return errs


def _validate_pj(s: CadastroState) -> dict[str, str]:
    """Validate all PJ (company) fields and return per-field error messages.

    Args:
        s: The current registration state.

    Returns:
        A mapping of field name → PT-BR error string for every failing field.
        An empty dict means all fields are valid.
    """
    errs: dict[str, str] = {}
    cnpj_err = validate_cnpj(s.cnpj)
    if cnpj_err:
        errs["cnpj"] = cnpj_err
    if not s.company_name.strip():
        errs["company_name"] = "Razão social é obrigatória"
    phone_err = validate_phone(s.phone)
    if phone_err:
        errs["phone"] = phone_err
    email_err = validate_email(s.email)
    if email_err:
        errs["email"] = email_err
    if not s.address.cep.strip():
        errs["cep"] = "CEP é obrigatório"
    if not s.address.street.strip():
        errs["street"] = "Rua é obrigatória"
    if not s.address.city.strip():
        errs["city"] = "Cidade é obrigatória"
    if not s.address.state.strip():
        errs["state"] = "UF é obrigatória"
    return errs
```

!!! tip "Tip — core validators"
    `validate_cpf`, `validate_cnpj`, `validate_phone`, and `validate_email` already implement the official check-digit algorithms and return a PT-BR error string (or `""` when valid). You don't need to reimplement anything.

---

## Step 4 — The `view()` function

All rendering logic lives in `view(app)`. Let's build it in parts.

### 4a — Mode switch (SegmentedControl)

```python
def view(app: App[CadastroState]) -> Widget:
    """Render the Brazilian registration form from the current state."""
    s = app.state
    is_pj = s.mode == 1

    # -- mode switch ----------------------------------------------------------
    def on_mode_select(index: int) -> None:
        """Switch between PF and PJ mode, clearing previous errors."""

        def mutate(st: CadastroState) -> None:
            st.mode = index
            st.errors = {}
            st.submitted = False

        app.set_state(mutate)

    mode_control = SegmentedControl(
        options=_MODES,
        selected=s.mode,
        on_select=on_mode_select,
        key="mode-control",
    )
```

`SegmentedControl` renders two horizontal buttons. When the user clicks, `on_mode_select` receives the index (0 or 1), clears accumulated errors, and sets `submitted = False` — preventing a stale error banner from the previous mode from showing up in the new one.

!!! note "Note — functional mutation"
    `app.set_state(mutate)` takes a **function** that modifies the state. This guarantees updates are atomic and the reconciler always gets the freshest snapshot before recalculating the diff. Learn more in [Tutorial — State](../tutorial/state.md).

### 4b — Document field (CPF or CNPJ)

The document block is conditional: PJ mode shows `CNPJInput` + company name field; PF mode shows only `CPFInput`.

```python
    # -- document field (CPF or CNPJ) -----------------------------------------
    doc_widgets: list[Widget] = []

    if is_pj:

        def on_cnpj(value: str) -> None:
            """Update CNPJ and clear its error when the value changes."""

            def mutate(st: CadastroState) -> None:
                st.cnpj = value
                st.errors.pop("cnpj", None)
                st.submitted = False

            app.set_state(mutate)

        def on_company_name(value: str) -> None:
            """Update the company name and clear its error."""

            def mutate(st: CadastroState) -> None:
                st.company_name = value
                st.errors.pop("company_name", None)
                st.submitted = False

            app.set_state(mutate)

        doc_widgets.append(
            CNPJInput(
                value=s.cnpj,
                label="CNPJ",
                placeholder="00.000.000/0000-00",
                error=s.errors.get("cnpj", ""),
                on_change=on_cnpj,
                key="cnpj-input",
            )
        )
        doc_widgets.append(
            Input(
                value=s.company_name,
                placeholder="Razão social",
                on_change=lambda ev: on_company_name(ev.value),
                key="company-name-input",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
                    radius=8.0,
                ),
            )
        )
        if "company_name" in s.errors:
            doc_widgets.append(
                Text(
                    content=s.errors["company_name"],
                    style=Style(font_size=12.0, color=_ERROR_COLOR),
                    key="company-name-error",
                )
            )
    else:

        def on_cpf(value: str) -> None:
            """Update CPF and clear its error when the value changes."""

            def mutate(st: CadastroState) -> None:
                st.cpf = value
                st.errors.pop("cpf", None)
                st.submitted = False

            app.set_state(mutate)

        doc_widgets.append(
            CPFInput(
                value=s.cpf,
                label="CPF",
                placeholder="000.000.000-00",
                error=s.errors.get("cpf", ""),
                on_change=on_cpf,
                key="cpf-input",
            )
        )
```

💡 The `st.errors.pop("field", None)` pattern clears the error **for that specific field** as soon as the user starts correcting it, without wiping errors for other fields that haven't been touched yet.

### 4c — Shared fields (phone and email)

```python
    # -- shared fields (phone + email) ----------------------------------------
    def on_phone(value: str) -> None:
        """Update the phone number and clear its error."""

        def mutate(st: CadastroState) -> None:
            st.phone = value
            st.errors.pop("phone", None)
            st.submitted = False

        app.set_state(mutate)

    def on_email(value: str) -> None:
        """Update the e-mail address and clear its error."""

        def mutate(st: CadastroState) -> None:
            st.email = value
            st.errors.pop("email", None)
            st.submitted = False

        app.set_state(mutate)

    phone_widget = PhoneInput(
        value=s.phone,
        label="Telefone",
        placeholder="(00) 00000-0000",
        error=s.errors.get("phone", ""),
        on_change=on_phone,
        key="phone-input",
    )

    email_widget = EmailInput(
        value=s.email,
        label="E-mail",
        placeholder="contato@empresa.com.br",
        error=s.errors.get("email", ""),
        on_change=on_email,
        key="email-input",
    )
```

`PhoneInput` and `EmailInput` work exactly like `CPFInput`/`CNPJInput`: they accept `value`, `label`, `placeholder`, `error`, and `on_change`. The pattern is intentionally identical — consistency by design.

### 4d — Address block

```python
    # -- address block --------------------------------------------------------
    addr = s.address

    def on_address(field_name: str, value: str) -> None:
        """Update one address sub-field and clear its error."""

        def mutate(st: CadastroState) -> None:
            setattr(st.address, field_name, value)
            st.errors.pop(field_name, None)
            st.submitted = False

        app.set_state(mutate)

    address_widget = AddressInput(
        cep=addr.cep,
        street=addr.street,
        number=addr.number,
        complement=addr.complement,
        neighborhood=addr.neighborhood,
        city=addr.city,
        state=addr.state,
        label="Endereço",
        on_change=on_address,
        key="address-input",
    )
```

`AddressInput` exposes a single `on_change(field_name, value)` callback for all its sub-fields. The `setattr(st.address, field_name, value)` call uses the field name as a dynamic key — that's why `_ADDRESS_FIELDS` documents the valid names.

### 4e — Submit and status banner

```python
    # -- submit ---------------------------------------------------------------
    def on_submit() -> None:
        """Validate all fields and update state accordingly."""
        errors = _validate_pj(s) if is_pj else _validate_pf(s)

        def mutate(st: CadastroState) -> None:
            st.errors = errors
            st.submitted = len(errors) == 0

        app.set_state(mutate)

    submit_btn = Button(label="Cadastrar", on_click=on_submit, key="submit-btn")

    # -- status banner --------------------------------------------------------
    banner_widgets: list[Widget] = []
    if s.submitted:
        banner_widgets.append(
            Banner(
                message="Cadastro realizado com sucesso!",
                tone="success",
                key="success-banner",
            )
        )
    elif s.errors:
        error_count = len(s.errors)
        banner_widgets.append(
            Banner(
                message=f"{error_count} campo(s) com erro — corrija e tente novamente.",
                tone="error",
                key="error-banner",
            )
        )
```

`Banner` accepts `tone="success"` (green) or `tone="error"` (red). The `elif s.errors` condition only shows the error banner **after a submit attempt** — while the user fills out the form for the first time, no banner is displayed.

!!! warning "Warning — closure capture of `s`"
    Notice that `on_submit` captures `s` (the current snapshot) and `is_pj` from the outer `view()` scope. This is correct: when `on_submit` is called, it reads `s` and `is_pj` from the most recent render, which is exactly what we want.

### 4f — Final assembly

```python
    # -- page title -----------------------------------------------------------
    title = Text(
        content="Cadastro — " + _MODES[s.mode],
        style=Style(font_size=20.0, font_weight=FontWeight.BOLD),
        key="page-title",
    )

    # -- assemble -------------------------------------------------------------
    form_children: list[Widget] = [
        mode_control,
        Divider(key="mode-divider"),
        *doc_widgets,
        phone_widget,
        email_widget,
        address_widget,
        Divider(key="submit-divider"),
        submit_btn,
        *banner_widgets,
    ]

    return Column(
        style=Style(gap=12.0, padding=Edge.all(20.0)),
        children=[
            title,
            Card(
                children=form_children,
                key="cadastro-card",
            ),
        ],
    )
```

The `*doc_widgets` splat inserts zero, one, or two widgets dynamically — no extra `if` needed in the final assembly. `Card` groups all the fields with spacing and a visual border; the outer `Column` adds page-level padding.

---

## The complete file

Here is the complete `app.py`, ready to copy:

```python
"""Brazilian registration form — CPF/CNPJ, phone, address with masked inputs.

Demonstrates the full complement of BR-specific form components from
:mod:`tempest_core.components.brforms` paired with the real-time
validators from :mod:`tempest_core.validators`.

Two registration modes are offered via a segmented control:

* **Pessoa Física (PF)** — individual: CPF + phone + address.
* **Pessoa Jurídica (PJ)** — company: CNPJ + company name + phone + address.

Each field validates on change; a summary banner is shown only when the form
is submitted (and passes all checks), or when errors are present after a
submit attempt.

Run in either mode — the app never names the transport::

    tempestweb dev --mode wasm
    tempestweb dev --mode server
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import (
    AddressInput,
    Banner,
    Card,
    CNPJInput,
    CPFInput,
    Divider,
    EmailInput,
    PhoneInput,
    SegmentedControl,
)
from tempest_core.style import Color, Edge, FontWeight
from tempest_core.validators import (
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)
from tempest_core.widgets import Button, Column, Input, Text

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

#: The error-text color shared by every inline error message.
_ERROR_COLOR: Color = Color.from_hex("#ef4444")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

#: Registered modes exposed by the segmented control.
_MODES: list[str] = ["Pessoa Física", "Pessoa Jurídica"]

#: Address field names reported by :class:`~tempest_core.components.AddressInput`.
_ADDRESS_FIELDS: tuple[str, ...] = (
    "cep",
    "street",
    "number",
    "complement",
    "neighborhood",
    "city",
    "state",
)


@dataclass
class AddressData:
    """Holds every sub-field of a Brazilian address.

    Attributes:
        cep: Postal code (CEP), e.g. ``"01310-100"``.
        street: Street or avenue name.
        number: House or building number.
        complement: Apartment, suite, etc.
        neighborhood: Bairro.
        city: City name.
        state: Two-letter state code (UF).
    """

    cep: str = ""
    street: str = ""
    number: str = ""
    complement: str = ""
    neighborhood: str = ""
    city: str = ""
    state: str = ""


@dataclass
class CadastroState:
    """Top-level application state for the BR registration form.

    Attributes:
        mode: Index into :data:`_MODES`; ``0`` = PF, ``1`` = PJ.
        cpf: CPF value (PF mode).
        cnpj: CNPJ value (PJ mode).
        company_name: Company/trade name (PJ mode).
        phone: Brazilian phone number.
        email: Contact e-mail.
        address: Nested address fields shared by both modes.
        errors: Per-field validation messages from the last submit attempt.
        submitted: Whether the last submit succeeded (all fields valid).
    """

    mode: int = 0
    cpf: str = ""
    cnpj: str = ""
    company_name: str = ""
    phone: str = ""
    email: str = ""
    address: AddressData = field(default_factory=AddressData)
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False


def make_state() -> CadastroState:
    """Build the initial, blank registration state.

    Returns:
        A fresh :class:`CadastroState` ready for the first render.
    """
    return CadastroState()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_pf(s: CadastroState) -> dict[str, str]:
    """Validate all PF (individual) fields and return per-field error messages.

    Args:
        s: The current registration state.

    Returns:
        A mapping of field name → PT-BR error string for every failing field.
        An empty dict means all fields are valid.
    """
    errs: dict[str, str] = {}
    cpf_err = validate_cpf(s.cpf)
    if cpf_err:
        errs["cpf"] = cpf_err
    phone_err = validate_phone(s.phone)
    if phone_err:
        errs["phone"] = phone_err
    email_err = validate_email(s.email)
    if email_err:
        errs["email"] = email_err
    if not s.address.cep.strip():
        errs["cep"] = "CEP é obrigatório"
    if not s.address.street.strip():
        errs["street"] = "Rua é obrigatória"
    if not s.address.city.strip():
        errs["city"] = "Cidade é obrigatória"
    if not s.address.state.strip():
        errs["state"] = "UF é obrigatória"
    return errs


def _validate_pj(s: CadastroState) -> dict[str, str]:
    """Validate all PJ (company) fields and return per-field error messages.

    Args:
        s: The current registration state.

    Returns:
        A mapping of field name → PT-BR error string for every failing field.
        An empty dict means all fields are valid.
    """
    errs: dict[str, str] = {}
    cnpj_err = validate_cnpj(s.cnpj)
    if cnpj_err:
        errs["cnpj"] = cnpj_err
    if not s.company_name.strip():
        errs["company_name"] = "Razão social é obrigatória"
    phone_err = validate_phone(s.phone)
    if phone_err:
        errs["phone"] = phone_err
    email_err = validate_email(s.email)
    if email_err:
        errs["email"] = email_err
    if not s.address.cep.strip():
        errs["cep"] = "CEP é obrigatório"
    if not s.address.street.strip():
        errs["street"] = "Rua é obrigatória"
    if not s.address.city.strip():
        errs["city"] = "Cidade é obrigatória"
    if not s.address.state.strip():
        errs["state"] = "UF é obrigatória"
    return errs


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[CadastroState]) -> Widget:
    """Render the Brazilian registration form from the current state."""
    s = app.state
    is_pj = s.mode == 1

    # -- mode switch ----------------------------------------------------------
    def on_mode_select(index: int) -> None:
        """Switch between PF and PJ mode, clearing previous errors."""

        def mutate(st: CadastroState) -> None:
            st.mode = index
            st.errors = {}
            st.submitted = False

        app.set_state(mutate)

    mode_control = SegmentedControl(
        options=_MODES,
        selected=s.mode,
        on_select=on_mode_select,
        key="mode-control",
    )

    # -- document field (CPF or CNPJ) -----------------------------------------
    doc_widgets: list[Widget] = []

    if is_pj:

        def on_cnpj(value: str) -> None:
            """Update CNPJ and clear its error when the value changes."""

            def mutate(st: CadastroState) -> None:
                st.cnpj = value
                st.errors.pop("cnpj", None)
                st.submitted = False

            app.set_state(mutate)

        def on_company_name(value: str) -> None:
            """Update the company name and clear its error."""

            def mutate(st: CadastroState) -> None:
                st.company_name = value
                st.errors.pop("company_name", None)
                st.submitted = False

            app.set_state(mutate)

        doc_widgets.append(
            CNPJInput(
                value=s.cnpj,
                label="CNPJ",
                placeholder="00.000.000/0000-00",
                error=s.errors.get("cnpj", ""),
                on_change=on_cnpj,
                key="cnpj-input",
            )
        )
        doc_widgets.append(
            Input(
                value=s.company_name,
                placeholder="Razão social",
                on_change=lambda ev: on_company_name(ev.value),
                key="company-name-input",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
                    radius=8.0,
                ),
            )
        )
        if "company_name" in s.errors:
            doc_widgets.append(
                Text(
                    content=s.errors["company_name"],
                    style=Style(font_size=12.0, color=_ERROR_COLOR),
                    key="company-name-error",
                )
            )
    else:

        def on_cpf(value: str) -> None:
            """Update CPF and clear its error when the value changes."""

            def mutate(st: CadastroState) -> None:
                st.cpf = value
                st.errors.pop("cpf", None)
                st.submitted = False

            app.set_state(mutate)

        doc_widgets.append(
            CPFInput(
                value=s.cpf,
                label="CPF",
                placeholder="000.000.000-00",
                error=s.errors.get("cpf", ""),
                on_change=on_cpf,
                key="cpf-input",
            )
        )

    # -- shared fields (phone + email) ----------------------------------------
    def on_phone(value: str) -> None:
        """Update the phone number and clear its error."""

        def mutate(st: CadastroState) -> None:
            st.phone = value
            st.errors.pop("phone", None)
            st.submitted = False

        app.set_state(mutate)

    def on_email(value: str) -> None:
        """Update the e-mail address and clear its error."""

        def mutate(st: CadastroState) -> None:
            st.email = value
            st.errors.pop("email", None)
            st.submitted = False

        app.set_state(mutate)

    phone_widget = PhoneInput(
        value=s.phone,
        label="Telefone",
        placeholder="(00) 00000-0000",
        error=s.errors.get("phone", ""),
        on_change=on_phone,
        key="phone-input",
    )

    email_widget = EmailInput(
        value=s.email,
        label="E-mail",
        placeholder="contato@empresa.com.br",
        error=s.errors.get("email", ""),
        on_change=on_email,
        key="email-input",
    )

    # -- address block --------------------------------------------------------
    addr = s.address

    def on_address(field_name: str, value: str) -> None:
        """Update one address sub-field and clear its error."""

        def mutate(st: CadastroState) -> None:
            setattr(st.address, field_name, value)
            st.errors.pop(field_name, None)
            st.submitted = False

        app.set_state(mutate)

    address_widget = AddressInput(
        cep=addr.cep,
        street=addr.street,
        number=addr.number,
        complement=addr.complement,
        neighborhood=addr.neighborhood,
        city=addr.city,
        state=addr.state,
        label="Endereço",
        on_change=on_address,
        key="address-input",
    )

    # -- submit ---------------------------------------------------------------
    def on_submit() -> None:
        """Validate all fields and update state accordingly."""
        errors = _validate_pj(s) if is_pj else _validate_pf(s)

        def mutate(st: CadastroState) -> None:
            st.errors = errors
            st.submitted = len(errors) == 0

        app.set_state(mutate)

    submit_btn = Button(label="Cadastrar", on_click=on_submit, key="submit-btn")

    # -- status banner --------------------------------------------------------
    banner_widgets: list[Widget] = []
    if s.submitted:
        banner_widgets.append(
            Banner(
                message="Cadastro realizado com sucesso!",
                tone="success",
                key="success-banner",
            )
        )
    elif s.errors:
        error_count = len(s.errors)
        banner_widgets.append(
            Banner(
                message=f"{error_count} campo(s) com erro — corrija e tente novamente.",
                tone="error",
                key="error-banner",
            )
        )

    # -- page title -----------------------------------------------------------
    title = Text(
        content="Cadastro — " + _MODES[s.mode],
        style=Style(font_size=20.0, font_weight=FontWeight.BOLD),
        key="page-title",
    )

    # -- assemble -------------------------------------------------------------
    form_children: list[Widget] = [
        mode_control,
        Divider(key="mode-divider"),
        *doc_widgets,
        phone_widget,
        email_widget,
        address_widget,
        Divider(key="submit-divider"),
        submit_btn,
        *banner_widgets,
    ]

    return Column(
        style=Style(gap=12.0, padding=Edge.all(20.0)),
        children=[
            title,
            Card(
                children=form_children,
                key="cadastro-card",
            ),
        ],
    )
```

---

## Step 5 — Running the app

### WASM mode (Pyodide in the browser)

```bash
tempestweb dev --mode wasm examples/br-cadastro/app.py
```

The CLI starts a local server, opens your browser, and loads Pyodide. All Python logic runs **inside the browser** — no round-trips to a server.

### Server mode (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/br-cadastro/app.py
```

Python runs on the server. The browser receives UI patches over WebSocket. The end-user experience is identical.

!!! check "Verification"
    Once the app is open in your browser:

    1. Click **Cadastrar** with all fields empty — the error banner should appear with the count of invalid fields.
    2. Fill in an invalid CPF (e.g. `111.111.111-11`) — the inline error message should appear below the field after submitting.
    3. Switch to **Pessoa Jurídica** — the CPF field disappears and CNPJ + company name appear; previous errors are cleared.
    4. Fill in all fields correctly and click **Cadastrar** — the green success banner should appear.

---

## Recap

In this tutorial you built a complete BR registration form. Here's what you learned:

- ✅ **`SegmentedControl`** switches between distinct flows (PF/PJ), clearing stale state in `on_select`.
- ✅ **`CPFInput` / `CNPJInput` / `PhoneInput` / `EmailInput`** share the same interface: `value`, `label`, `placeholder`, `error`, `on_change` — easy to combine.
- ✅ **`AddressInput`** delegates to a single `on_change(field_name, value)` callback, making the handler generic via `setattr`.
- ✅ **Pure validation** outside `view()` returns `dict[str, str]` — unit-testable in isolation, no side effects.
- ✅ The `st.errors.pop("field", None)` pattern clears errors **per field** as the user types, without affecting others.
- ✅ **`Banner`** with `tone="success"` or `tone="error"` provides submit feedback without any extra widget.
- ✅ **`*doc_widgets` (splat)** injects conditional widgets into the final assembly without additional `if` statements.

---

## Next steps

- Explore other form examples: [Temperature Converter](./temperature-converter.en.md) shows real-time validation without an explicit submit.
- See [Data Table](./data-table.en.md) to display registered entries after persistence.
- Learn the fundamentals in [Tutorial — Introduction](../tutorial/index.en.md) and [Tutorial — State](../tutorial/state.en.md).
