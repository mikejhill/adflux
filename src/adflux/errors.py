"""Typed exception hierarchy for adflux.

All public exceptions inherit from :class:`AdfluxError` to allow callers to
catch the whole library's errors with a single ``except`` clause.
"""

from __future__ import annotations


class AdfluxError(Exception):
    """Base class for all adflux errors."""


class UnsupportedFormatError(AdfluxError):
    """Raised when a requested source or target format is not registered."""

    def __init__(self, fmt: str, *, role: str = "format") -> None:
        super().__init__(f"Unsupported {role}: {fmt!r}")
        self.fmt = fmt
        self.role = role


class InvalidADFError(AdfluxError):
    """Raised when an ADF document fails JSON-schema validation.

    Attributes:
        pointer: JSON pointer into the offending node, if available.
        validator_errors: Underlying ``jsonschema`` errors.
    """

    def __init__(
        self,
        message: str,
        *,
        pointer: str | None = None,
        validator_errors: list[object] | None = None,
    ) -> None:
        super().__init__(message)
        self.pointer = pointer
        self.validator_errors = validator_errors or []


class MappingError(AdfluxError):
    """Raised when the ADF YAML mapping table is malformed or incomplete."""


class UnrepresentableNodeError(AdfluxError):
    """Raised (in ``fail-loud`` profile) when a node cannot be represented in the target."""

    def __init__(self, node_type: str, target_format: str) -> None:
        super().__init__(
            f"Node type {node_type!r} has no representation in target format {target_format!r}"
        )
        self.node_type = node_type
        self.target_format = target_format
