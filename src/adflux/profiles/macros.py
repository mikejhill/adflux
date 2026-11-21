"""Catalog of Confluence macros: what ADF node each becomes and which parameters it takes.

The catalog is captured from a live site (see ``scripts/build_profile_data.py``). It tells
the converter whether a macro is a leaf (``extension``), wraps rich content
(``bodiedExtension``), sits inline (``inlineExtension``), or is turned by Confluence into a
native ADF node (``info`` -> ``panel``, ``code`` -> ``codeBlock``). Macros missing from the
catalog (apps installed on a site) still convert: their shape follows from how they are
written in Markdown.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any

CONFLUENCE_MACRO_TYPE = "com.atlassian.confluence.macro.core"


@dataclass(frozen=True, slots=True)
class MacroParam:
    """One macro parameter. Values are always strings in ADF (``{"value": "3"}``)."""

    name: str  # "" is the default (unnamed) parameter
    type: str = "string"
    required: bool = False
    multiple: bool = False
    default: str | None = None
    enum: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    hidden: bool = False

    def describe(self) -> dict[str, Any]:
        """Return a JSON-friendly summary for docs and ``adflux macros``."""
        out: dict[str, Any] = {"name": self.name or "(default)", "type": self.type}
        if self.required:
            out["required"] = True
        if self.multiple:
            out["multiple"] = True
        if self.default not in (None, ""):
            out["default"] = self.default
        if self.enum:
            out["choices"] = list(self.enum)
        if self.aliases:
            out["aliases"] = [a for a in self.aliases if a]
        return out


@dataclass(frozen=True, slots=True)
class Macro:
    """A macro definition."""

    name: str
    title: str
    body: str = "NONE"  # NONE | RICH_TEXT | PLAIN_TEXT
    output: str = "BLOCK"  # BLOCK | INLINE
    node: str | None = None  # ADF node Confluence produces, None if unsupported in ADF
    hidden: bool = False
    aliases: tuple[str, ...] = ()
    params: tuple[MacroParam, ...] = field(default_factory=tuple)
    docs: str | None = None

    @property
    def native(self) -> bool:
        """Return whether Confluence stores this macro as a native ADF node."""
        return self.node not in (None, "extension", "bodiedExtension", "inlineExtension")

    def param(self, name: str) -> MacroParam | None:
        """Return the parameter called (or aliased) ``name``."""
        for p in self.params:
            if p.name == name or name in p.aliases:
                return p
        return None

    def describe(self) -> dict[str, Any]:
        """Return a JSON-friendly summary."""
        out: dict[str, Any] = {
            "name": self.name,
            "title": self.title,
            "adf": self.node or "unsupported",
            "body": {"NONE": "none", "RICH_TEXT": "rich", "PLAIN_TEXT": "plain"}[self.body],
            "params": [p.describe() for p in self.params if not p.hidden],
        }
        if self.aliases:
            out["aliases"] = list(self.aliases)
        if self.docs:
            out["docs"] = self.docs
        return out


class MacroCatalog:
    """Macros by name and alias."""

    def __init__(self, macros: list[Macro], extension_type: str = CONFLUENCE_MACRO_TYPE) -> None:
        self.extension_type = extension_type
        self._macros = {m.name: m for m in macros}
        self._aliases = {alias: m for m in macros for alias in m.aliases}

    def get(self, name: str) -> Macro | None:
        """Return the macro named (or aliased) ``name``."""
        return self._macros.get(name) or self._aliases.get(name)

    def __iter__(self):
        return iter(self._macros.values())

    def __len__(self) -> int:
        return len(self._macros)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.get(name) is not None


@cache
def confluence_catalog() -> MacroCatalog:
    """Return the built-in Confluence Cloud macro catalog."""
    raw = json.loads(
        resources.files("adflux.profiles").joinpath("data/confluence_macros.json").read_text(encoding="utf-8")
    )
    macros = []
    for name, item in raw.items():
        params = tuple(
            MacroParam(
                p["name"],
                p.get("type", "string"),
                p.get("required", False),
                p.get("multiple", False),
                p.get("default"),
                tuple(p.get("enum") or ()),
                tuple(p.get("aliases") or ()),
                p.get("hidden", False),
            )
            for p in item["params"]
        )
        macros.append(
            Macro(
                name,
                item["title"],
                item["body"],
                item["output"],
                item["node"],
                item["hidden"],
                tuple(item["aliases"]),
                params,
                item.get("docs"),
            )
        )
    return MacroCatalog(macros)


def empty_catalog() -> MacroCatalog:
    """Return a catalog with no macros (Jira)."""
    return MacroCatalog([])
