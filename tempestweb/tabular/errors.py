"""Errors a tabular prediction raises, each naming exactly what went wrong.

The whole reason this package exists is that a feature mismatch is otherwise
**silent**. A model trained on ``age`` handed ``{"idade": 30}`` does not fail —
it reads a zero where the age should be and answers a number that looks fine and
is wrong. Nothing downstream can tell.

So every mismatch is a named error carrying both sides: what the model expects,
and what it was given.
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = [
    "TabularError",
    "ManifestError",
    "MissingFeatureError",
    "UnknownFeatureError",
    "PredictionError",
]


class TabularError(ValueError):
    """Base class for every tabular failure."""


class ManifestError(TabularError):
    """The manifest itself is unusable.

    Raised for a manifest with no features, with duplicates, or whose JSON is not
    the shape a manifest has. A broken manifest is a build-time mistake and is
    worth failing loudly on, because everything after it is built on the order it
    declares.
    """


class MissingFeatureError(TabularError):
    """The row does not carry every feature the model was trained on.

    Attributes:
        missing: The declared features the row lacks.
        extra: Features the row carries that the model does not know, listed
            alongside because the pair is usually one typo — ``idade`` present
            and ``age`` missing is one mistake, not two.
    """

    def __init__(self, missing: Iterable[str], extra: Iterable[str] = ()) -> None:
        """Build the error from both halves of the mismatch.

        Args:
            missing: The declared features the row lacks.
            extra: Features the row carries that the model does not know.
        """
        self.missing: tuple[str, ...] = tuple(missing)
        self.extra: tuple[str, ...] = tuple(extra)
        message = f"row is missing {len(self.missing)} feature(s): " + ", ".join(
            self.missing
        )
        if self.extra:
            message += "; it carries instead: " + ", ".join(self.extra)
        super().__init__(message)


class UnknownFeatureError(TabularError):
    """The row carries a feature the model was not trained on.

    Attributes:
        unknown: The features the model does not declare.
    """

    def __init__(self, unknown: Iterable[str]) -> None:
        """Build the error from the unexpected features.

        Args:
            unknown: The features the model does not declare.
        """
        self.unknown: tuple[str, ...] = tuple(unknown)
        super().__init__(
            "row carries feature(s) the model does not declare: "
            + ", ".join(self.unknown)
        )


class PredictionError(TabularError):
    """The model ran but its output could not be read as a prediction."""
