"""Errors raised by the Mode C transpiler."""

from __future__ import annotations

import ast

__all__: list[str] = ["TranspileError"]


class TranspileError(Exception):
    """A Python construct fell outside the transpilable subset.

    Carries the source location so the message reads like a compiler diagnostic
    (``file:line: <what> is not supported``), in the spirit of ``mypy --strict``.
    """

    def __init__(
        self, message: str, node: ast.AST | None, filename: str = "<source>"
    ) -> None:
        """Initialize the error.

        Args:
            message: What is unsupported and, ideally, why.
            node: The offending AST node (its ``lineno`` locates the
                diagnostic), or ``None`` when the diagnostic is about the module
                as a whole and no node carries the blame — the line then reads
                ``0``, which is still better than losing the message.
            filename: The source file name, for the ``file:line`` prefix.
        """
        line: int = getattr(node, "lineno", 0)
        self.filename: str = filename
        self.lineno: int = line
        super().__init__(f"{filename}:{line}: {message}")
