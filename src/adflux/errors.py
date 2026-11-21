"""Exceptions raised by adflux."""

from __future__ import annotations


class AdfluxError(Exception):
    """Base class for every adflux error."""


class AdfError(AdfluxError):
    """The input is not a well-formed ADF document (wrong JSON shape)."""

    def __init__(self, message: str, path: str = "$") -> None:
        super().__init__(f"{path}: {message}" if path else message)
        self.path = path


class AdfValidationError(AdfluxError):
    """The document breaks the ADF JSON Schema."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        lines = [f"{issue.path}: {issue.message}" for issue in issues[:10]]
        more = f" (and {len(issues) - 10} more)" if len(issues) > 10 else ""
        super().__init__("invalid ADF: " + "; ".join(lines) + more)


class MarkdownError(AdfluxError):
    """The Markdown uses adflux syntax incorrectly (for example a bad directive)."""

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(f"line {line + 1}: {message}" if line is not None else message)
        self.line = line


class ValidationIssue:
    """One schema problem: a JSON path into the document and a message."""

    __slots__ = ("message", "path")

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __repr__(self) -> str:
        return f"ValidationIssue({self.path!r}, {self.message!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ValidationIssue) and (self.path, self.message) == (
            other.path,
            other.message,
        )

    def __hash__(self) -> int:
        return hash((self.path, self.message))
