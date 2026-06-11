"""Form aggregation, typed validators and per-field validation state.

A form gathers its fields' values, runs their typed validators at the boundary
(the same philosophy as :func:`~tempestroid.widgets.events.parse_event` —
validation happens once, in Python, and produces a structured, JSON-serializable
result), and only dispatches a :class:`~tempestroid.widgets.events.SubmitEvent`
when every field is valid.

``FormState`` is the structured result: a flat ``dict[str, str]`` of per-field
errors plus an overall ``valid`` flag. It is intentionally *not* a tree of nested
models, so it serializes to plain JSON (``{"errors": {...}, "valid": bool}``) and
can live directly inside the application's state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, ClassVar, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema

from tempestweb._core.widgets.base import (
    SubmitHandler,
    ValidationHandler,
    Widget,
)
from tempestweb._core.widgets.events import (
    Event,
    SubmitEvent,
    ValidationEvent,
)

__all__ = [
    "Validator",
    "FormState",
    "FormField",
    "Form",
]

#: A typed validation rule: receives a field's raw value and returns an error
#: message string when invalid, or ``None`` when the value passes. Validators run
#: purely in Python (never serialized over the boundary), so they may close over
#: any application logic.
Validator: TypeAlias = Callable[[Any], str | None]

#: A validator annotated with a JSON-schema stand-in. Validators are plain Python
#: callables with no JSON representation; annotating the *item* type (mirroring the
#: handler ``WithJsonSchema`` pattern) lets introspection emit a schema for a
#: ``list`` of them while keeping the element type fully known to the type checker.
_AnnotatedValidator: TypeAlias = Annotated[
    Validator,
    WithJsonSchema(
        {
            "type": "string",
            "title": "Validator",
            "description": "client-side validator; not serialized over the boundary",
        }
    ),
]


class FormState(BaseModel):
    """The structured result of validating a form.

    Frozen so it can be diffed by value and dropped straight into the app state.
    Serializes to plain JSON — ``{"errors": {...}, "valid": bool}`` — with no
    nested models.

    Attributes:
        errors: A mapping of field name to its error message. Only failing fields
            appear; an empty mapping means every field passed.
        valid: ``True`` when no field has an error.
    """

    model_config = ConfigDict(frozen=True)

    errors: dict[str, str] = Field(
        description="A mapping of field name to its error message. Only failing fields "
        "appear; an empty mapping means every field passed.",
        default_factory=dict,
    )
    valid: bool = Field(
        default=True, description="``True`` when no field has an error."
    )


class FormField(Widget):
    """A labelled wrapper around a single input, carrying validation metadata.

    The wrapped input is exposed as a child node (so renderers render it
    recursively and it crosses the boundary as a normal child, never as a prop).
    The ``error`` prop mirrors :attr:`FormState.errors` for this field; the
    enclosing :class:`Form` fills it after running validators.

    Attributes:
        name: The field's name (the key used in :attr:`FormState.errors` and
            :attr:`~tempestroid.widgets.events.SubmitEvent.values`).
        validators: The typed validation rules run against this field's value.
            Pure Python — never serialized over the boundary.
        label: An optional label shown above the input.
        error: The current validation message (``""`` when valid). Mirrored from
            the owning form's :class:`FormState`.
        child: The wrapped input widget rendered inside the field.
        on_validate: Optional handler invoked with a :class:`ValidationEvent` when
            this field is validated.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_validate": ValidationEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    name: str = Field(
        description="The field's name (the key used in :attr:`FormState.errors` and "
        ":attr:`~tempestroid.widgets.events.SubmitEvent.values`).",
    )
    # ``list[Callable]`` reads as ``list[Unknown]`` under pyright strict's
    # reportUnknownVariableType (a known limitation with callable element types);
    # the element type is fully specified by ``_AnnotatedValidator`` and the
    # ``WithJsonSchema`` keeps introspection working. Scoped ignore, not a hole.
    validators: list[_AnnotatedValidator] = Field(  # pyright: ignore[reportUnknownVariableType]
        description=(
            "The typed validation rules run against this field's value. Pure "
            "Python — never serialized over the boundary."
        ),
        default_factory=list,
    )
    label: str = Field(
        default="", description="An optional label shown above the input."
    )
    error: str = Field(
        default="",
        description='The current validation message (``""`` when valid). Mirrored from '
        "the owning form's :class:`FormState`.",
    )
    child: Widget | None = Field(
        default=None, description="The wrapped input widget rendered inside the field."
    )
    on_validate: ValidationHandler | None = Field(
        default=None,
        description="Optional handler invoked with a :class:`ValidationEvent` when "
        "this field is validated.",
    )

    def run_validators(self, value: Any) -> str | None:  # noqa: ANN401 — value is an opaque field value
        """Run this field's validators against ``value``.

        Named ``run_validators`` rather than ``validate`` to avoid shadowing
        Pydantic's deprecated ``BaseModel.validate`` classmethod.

        Args:
            value: The field's raw value.

        Returns:
            The first validator's error message, or ``None`` when every validator
            passes.
        """
        for rule in self.validators:
            error = rule(value)
            if error is not None:
                return error
        return None

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped input, if any.

        Returns:
            A one-element list with the child input, or an empty list.
        """
        return [self.child] if self.child is not None else []


class Form(Widget):
    """A container that aggregates fields, validates them, and gates submit.

    The fields are exposed as child nodes (each a :class:`FormField`), so the
    serialized tree carries them as children — never as a prop holding nested
    models. :meth:`validate` runs every field's validators purely in Python and
    returns a :class:`FormState`; the application uses it to decide whether to
    dispatch the form's :class:`~tempestroid.widgets.events.SubmitEvent`.

    Attributes:
        fields: The form's fields, in display order.
        on_submit: Handler invoked with a :class:`SubmitEvent` when the form is
            submitted with valid values.

    Methods:
        validate: Validate every field against ``values`` and build the
            :class:`FormState` (used to gate submit).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_submit": SubmitEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"fields"})

    # ``FormField`` carries a ``list[Callable]`` (validators) that pyright treats
    # as partially unknown, which propagates here; the type is fully specified.
    fields: list[FormField] = Field(  # pyright: ignore[reportUnknownVariableType]
        description="The form's fields, in display order.",
        default_factory=list,
    )
    on_submit: SubmitHandler | None = Field(
        default=None,
        description="Handler invoked with a :class:`SubmitEvent` when the form is "
        "submitted with valid values.",
    )

    # ``validate`` is the public, contract-mandated entry point (E5). It shadows
    # Pydantic's deprecated ``BaseModel.validate`` classmethod with a different,
    # instance-level signature; the scoped ignore keeps the documented public name
    # without weakening strict typing elsewhere.
    def validate(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, values: dict[str, Any]
    ) -> FormState:
        """Validate every field against ``values`` and build the form state.

        Pure: runs each field's validators against the matching value (an absent
        value validates as the empty string), collects the failures into a flat
        ``dict[str, str]``, and reports overall validity. Performs no side effects
        — the caller decides what to do with the result (e.g. mirror each error
        back onto its field and gate ``SubmitEvent``).

        Args:
            values: A mapping of field name to its raw value at validation time.

        Returns:
            A :class:`FormState` whose ``errors`` holds only the failing fields and
            whose ``valid`` is ``True`` when no field failed.
        """
        errors: dict[str, str] = {}
        for field in self.fields:
            error = field.run_validators(values.get(field.name, ""))
            if error is not None:
                errors[field.name] = error
        return FormState(errors=errors, valid=not errors)

    def child_nodes(self) -> list[Widget]:
        """Return the form's fields in order.

        Returns:
            The ordered :class:`FormField` children (empty when the form has no
            fields).
        """
        return list(self.fields)
