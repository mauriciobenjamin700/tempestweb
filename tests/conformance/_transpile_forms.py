"""Regenerate the Mode C form-validation fixture from the real core.

``Form.validate(values)`` is the first *widget method* Mode C ports. The client
carries each widget's **builder** — the function returning the IR node — and none
of the Python methods the class also has, so the call used to be refused (and,
where the compiler could not tell the receiver was a ``Form``, compiled into a
page that threw ``form1.validate is not a function`` on the first click).

What makes the port possible is that ``validators`` never cross a wire in Mode C:
the builder passes the array straight onto the node, so the live functions are
right there when validation runs. The rule itself is small — first failing
validator per field wins, an absent value validates as ``""``, ``valid`` is "no
field failed" — and this matrix pins it against the core rather than by eye.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_forms
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import (
    Form,
    FormField,
    Input,
    validate_cpf,
    validate_email,
    validate_phone,
)

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
FORMS_FIXTURE: Path = FIXTURES_DIR / "transpile_form_samples.json"


def _required(value: Any) -> str | None:  # noqa: ANN401 — an opaque field value
    """Reject an empty value, the way an app's own rule does.

    Args:
        value: The field's raw value.

    Returns:
        The error message when the value is empty, else ``None``.
    """
    return "obrigatório" if not str(value).strip() else None


def _too_short(value: Any) -> str | None:  # noqa: ANN401 — an opaque field value
    """Reject a value under eight characters.

    Args:
        value: The field's raw value.

    Returns:
        The error message when the value is too short, else ``None``.
    """
    return "mínimo 8 caracteres" if len(str(value)) < 8 else None


#: Scenario name -> (the form, the values handed to ``validate``). The JS test
#: rebuilds each with the same validators, so a divergence in the rule shows up
#: as a different ``errors``/``valid`` pair.
def _cases() -> dict[str, tuple[Form, dict[str, str]]]:
    """Return the sample validations keyed by a scenario name.

    Returns:
        A scenario name -> (form, values) map covering an all-valid pass, one
        failure, several failures, a field whose *second* validator fails, a
        value missing from the mapping, a field with no validators at all, and a
        form with no fields.
    """
    email = FormField(name="email", validators=[_required, validate_email])
    password = FormField(name="password", validators=[_required, _too_short])
    cpf = FormField(name="cpf", validators=[validate_cpf])
    phone = FormField(name="phone", validators=[validate_phone])
    free = FormField(name="notes", child=Input(value="", key="notes-input"))

    def form(*fields: FormField) -> Form:
        return Form(fields=list(fields), key="signup")

    return {
        "form_all_valid": (
            form(email, password),
            {"email": "a@b.co", "password": "hunter2!!"},
        ),
        "form_one_failure": (
            form(email, password),
            {"email": "nope", "password": "hunter2!!"},
        ),
        "form_every_field_fails": (form(email, password), {}),
        "form_second_validator_fails": (
            form(password),
            {"password": "short"},
        ),
        "form_missing_value_is_empty_string": (
            form(email),
            {"password": "hunter2!!"},
        ),
        "form_field_without_validators": (form(free), {"notes": ""}),
        "form_no_fields": (form(), {"email": "whatever"}),
        "form_br_validators": (
            form(cpf, phone),
            {"cpf": "529.982.247-25", "phone": "(11) 99999-1234"},
        ),
        "form_br_validators_invalid": (
            form(cpf, phone),
            {"cpf": "111.111.111-11", "phone": "123"},
        ),
    }


def build_samples() -> dict[str, Any]:
    """Build each scenario's validation result.

    Returns:
        A scenario -> ``{"values", "result"}`` map, where ``result`` is the
        serialized ``FormState``.
    """
    samples: dict[str, Any] = {}
    for name, (form, values) in _cases().items():
        state = form.validate(values)
        samples[name] = {
            "values": values,
            "result": state.model_dump(mode="json"),
        }
    return samples


def render_fixture_text() -> str:
    """Render the form-validation fixture as canonical JSON text."""
    return (
        json.dumps(build_samples(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def write_fixture() -> Path:
    """Write the form-validation fixture to disk and return its path."""
    FORMS_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return FORMS_FIXTURE


def main() -> None:
    """Regenerate the form-validation fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
