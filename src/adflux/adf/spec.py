"""Typed view of the schema-generated node and mark table (:mod:`adflux.adf._spec`)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from adflux.adf._spec import SCHEMA_SOURCE, SPEC

__all__ = ["MARKS", "NODES", "SCHEMA_SOURCE", "AttrSpec", "MarkSpec", "NodeSpec"]


@dataclass(frozen=True, slots=True)
class AttrSpec:
    """One attribute: its JSON kind and constraints."""

    name: str
    kind: str  # string | number | boolean | enum | array | object | any
    required: bool = False
    enum: tuple[Any, ...] = ()
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None

    def coerce(self, raw: str) -> Any:
        """Turn a Markdown attribute string into the JSON value the schema expects."""
        if self.kind == "number":
            try:
                number = float(raw)
            except ValueError:
                raise ValueError(f"{self.name} must be a number, got {raw!r}") from None
            return int(number) if number.is_integer() else number
        if self.kind == "boolean":
            lowered = raw.lower()
            if lowered in ("true", "yes", "1", ""):
                return True
            if lowered in ("false", "no", "0"):
                return False
            raise ValueError(f"{self.name} must be true or false, got {raw!r}")
        if self.kind in ("array", "object", "any"):
            stripped = raw.strip()
            if stripped[:1] in ("[", "{") or stripped in ("null", "true", "false"):
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    pass
            if self.kind == "any":
                return raw
            raise ValueError(f"{self.name} must be JSON ({self.kind}), got {raw!r}")
        if self.kind == "enum" and self.enum and raw not in self.enum:
            # Enums of non-strings (rare) are matched by their JSON spelling.
            for option in self.enum:
                if json.dumps(option) == raw:
                    return option
            choices = ", ".join(map(str, self.enum))
            raise ValueError(f"{self.name} must be one of {choices}, got {raw!r}")
        if self.pattern and not re.search(self.pattern, raw):
            raise ValueError(f"{self.name} does not match {self.pattern}: {raw!r}")
        return raw

    def format(self, value: Any) -> str:
        """Return the Markdown attribute spelling of ``value`` (inverse of :meth:`coerce`)."""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float) and not isinstance(value, bool):
            return str(int(value)) if float(value).is_integer() else repr(value)
        if isinstance(value, str) and self.kind in ("string", "enum"):
            return value
        if isinstance(value, str) and self.kind == "any" and not _looks_json(value):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _looks_json(value: str) -> bool:
    stripped = value.strip()
    return stripped[:1] in ("[", "{") or stripped in ("null", "true", "false")


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """What the schema allows for one node type."""

    name: str
    attrs: dict[str, AttrSpec]
    content: frozenset[str]
    marks: frozenset[str]
    group: str  # "block" | "inline"
    leaf: bool
    content_required: bool

    @property
    def inline(self) -> bool:
        """Return whether the node is inline content."""
        return self.group == "inline"

    def attr(self, name: str) -> AttrSpec:
        """Return the spec of ``name``, or a permissive one for attributes the schema lacks."""
        return self.attrs.get(name) or AttrSpec(name, "any")


@dataclass(frozen=True, slots=True)
class MarkSpec:
    """What the schema allows for one mark type."""

    name: str
    attrs: dict[str, AttrSpec]

    def attr(self, name: str) -> AttrSpec:
        """Return the spec of ``name``, or a permissive one."""
        return self.attrs.get(name) or AttrSpec(name, "any")


def _attrs(raw: dict[str, Any], required: list[str]) -> dict[str, AttrSpec]:
    return {
        name: AttrSpec(
            name,
            spec["kind"],
            name in required,
            tuple(spec.get("enum", ())),
            spec.get("pattern"),
            spec.get("minimum"),
            spec.get("maximum"),
        )
        for name, spec in raw.items()
    }


NODES: dict[str, NodeSpec] = {
    name: NodeSpec(
        name,
        _attrs(entry["attrs"], entry["required"]),
        frozenset(entry["content"]),
        frozenset(entry["marks"]),
        entry["group"],
        not entry["content"] and not entry.get("text"),
        bool(entry.get("content_required")),
    )
    for name, entry in SPEC["nodes"].items()
}

MARKS: dict[str, MarkSpec] = {
    name: MarkSpec(name, _attrs(entry["attrs"], entry["required"])) for name, entry in SPEC["marks"].items()
}


def node_spec(name: str) -> NodeSpec:
    """Return the spec of ``name``; unknown types get a permissive block spec."""
    return NODES.get(name) or NodeSpec(name, {}, frozenset(), frozenset(), "block", False, False)


def mark_spec(name: str) -> MarkSpec:
    """Return the spec of ``name``; unknown marks get a permissive spec."""
    return MARKS.get(name) or MarkSpec(name, {})
