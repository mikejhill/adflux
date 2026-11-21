"""Validate ADF documents.

Two passes, so problems are reported in words a person (or an agent) can act on:

1. A structural pass driven by the generated spec: unknown node or mark types, children a
   node may not contain, missing or malformed attributes. Each issue names the exact path.
2. The official ADF JSON Schema (vendored, Draft 4) as the final authority. Its ``anyOf``
   errors are hard to read, so they are only reported when the first pass found nothing.
"""

from __future__ import annotations

import json
import re
from functools import cache
from importlib import resources
from typing import Any

from adflux.adf.model import Node, load
from adflux.adf.spec import MARKS, NODES
from adflux.errors import AdfValidationError, ValidationIssue


@cache
def _schema_validator() -> Any:
    from jsonschema import Draft4Validator  # imported lazily: only validation needs it

    schema = json.loads(resources.files("adflux.adf").joinpath("schema/full.json").read_text(encoding="utf-8"))
    return Draft4Validator(schema)


def validation_issues(document: Node | dict[str, Any] | str, *, schema: bool = True) -> list[ValidationIssue]:
    """Return every problem found in ``document`` (empty when it is valid ADF)."""
    root = document if isinstance(document, Node) else load(document)
    issues: list[ValidationIssue] = []
    if root.type != "doc":
        issues.append(ValidationIssue("$", "the root node must be 'doc'"))
    _check(root, "$", issues)
    if not issues and schema:
        validator = _schema_validator()
        data = root.to_json()
        # is_valid stops at the first failure in each anyOf branch; iter_errors explores
        # every branch, which is exponential on deep documents. Only explain failures.
        errors = [] if validator.is_valid(data) else [validator.iter_errors(data)]
        for error in sorted((e for group in errors for e in group), key=lambda e: list(e.path)):
            path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.path)
            issues.append(ValidationIssue(path, _short(error.message)))
    return issues


def validate(document: Node | dict[str, Any] | str, *, schema: bool = True) -> Node:
    """Return the parsed document, or raise :class:`AdfValidationError`."""
    root = document if isinstance(document, Node) else load(document)
    issues = validation_issues(root, schema=schema)
    if issues:
        raise AdfValidationError(issues)
    return root


def _short(message: str) -> str:
    return message if len(message) <= 300 else message[:297] + "..."


def _check(node: Node, path: str, issues: list[ValidationIssue]) -> None:
    spec = NODES.get(node.type)
    if spec is None:
        issues.append(ValidationIssue(path, f"unknown node type {node.type!r}"))
        return
    for name, attr in spec.attrs.items():
        if attr.required and name not in node.attrs:
            issues.append(ValidationIssue(f"{path}.attrs", f"{node.type} needs attribute {name!r}"))
    for name, value in node.attrs.items():
        attr = spec.attrs.get(name)
        where = f"{path}.attrs.{name}"
        if attr is None:
            issues.append(ValidationIssue(where, f"{node.type} has no attribute {name!r}"))
            continue
        problem = _attr_problem(attr.kind, attr.enum, attr.pattern, attr.minimum, attr.maximum, value)
        if problem:
            issues.append(ValidationIssue(where, problem))
    if node.type == "text":
        if not node.text:
            issues.append(ValidationIssue(f"{path}.text", "text nodes need non-empty text"))
    elif node.text is not None:
        issues.append(ValidationIssue(f"{path}.text", f"{node.type} cannot have text"))
    for i, mark in enumerate(node.marks):
        mark_path = f"{path}.marks[{i}]"
        mark_spec = MARKS.get(mark.type)
        if mark_spec is None:
            issues.append(ValidationIssue(mark_path, f"unknown mark {mark.type!r}"))
            continue
        if mark.type not in spec.marks:
            issues.append(ValidationIssue(mark_path, f"{node.type} cannot carry mark {mark.type!r}"))
        for name, attr in mark_spec.attrs.items():
            if attr.required and name not in mark.attrs:
                issues.append(ValidationIssue(mark_path, f"{mark.type} needs attribute {name!r}"))
        for name, value in mark.attrs.items():
            attr = mark_spec.attrs.get(name)
            if attr is None:
                issues.append(ValidationIssue(f"{mark_path}.attrs", f"{mark.type} has no attribute {name!r}"))
                continue
            problem = _attr_problem(attr.kind, attr.enum, attr.pattern, attr.minimum, attr.maximum, value)
            if problem:
                issues.append(ValidationIssue(f"{mark_path}.attrs.{name}", problem))
    if spec.content_required and not node.content:
        issues.append(ValidationIssue(path, f"{node.type} needs content"))
    for i, child in enumerate(node.children):
        child_path = f"{path}.content[{i}]"
        if child.type not in spec.content:
            allowed = ", ".join(sorted(spec.content)) or "nothing"
            issues.append(
                ValidationIssue(child_path, f"{node.type} cannot contain {child.type!r} (allowed: {allowed})")
            )
            continue
        _check(child, child_path, issues)


def _attr_problem(
    kind: str,
    enum: tuple[Any, ...],
    pattern: str | None,
    minimum: float | None,
    maximum: float | None,
    value: Any,
) -> str | None:
    if kind == "string" and not isinstance(value, str):
        return f"expected a string, got {json.dumps(value)}"
    if kind == "number" and (isinstance(value, bool) or not isinstance(value, int | float)):
        return f"expected a number, got {json.dumps(value)}"
    if kind == "boolean" and not isinstance(value, bool):
        return f"expected true or false, got {json.dumps(value)}"
    if kind == "array" and not isinstance(value, list):
        return f"expected an array, got {json.dumps(value)}"
    if kind == "enum" and enum and value not in enum:
        return f"expected one of {', '.join(map(str, enum))}, got {json.dumps(value)}"
    if pattern and isinstance(value, str) and not re.search(pattern, value):
        return f"{value!r} does not match {pattern}"
    if isinstance(value, int | float) and not isinstance(value, bool):
        if minimum is not None and value < minimum:
            return f"must be at least {minimum}"
        if maximum is not None and value > maximum:
            return f"must be at most {maximum}"
    return None
