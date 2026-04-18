"""YAML-driven ADF node-mapping table.

The mapping is a simple declarative registry:

.. code-block:: yaml

    version: 1
    nodes:
      panel:
        pandoc: Div
        kind: block
        envelope_class: adf-panel
        attrs: { panelType: string }
      status:
        pandoc: Span
        kind: inline
        envelope_class: adf-status
        attrs: { text: string, color: string, localId: string }

The reader/writer don't interpret every field — several are advisory
(``asciidoc_native``, ``attrs`` schema) and reserved for future post-
processors and validators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from adflux.errors import MappingError

_DEFAULT_MAPPING_PATH = Path(__file__).with_name("mapping.yaml")


@dataclass(slots=True, frozen=True)
class MappingEntry:
    """One ADF node type's mapping metadata."""

    node_type: str
    pandoc: str
    """Pandoc element name, e.g. ``"Div"``, ``"Span"``, ``"Image"``."""
    kind: Literal["block", "inline"]
    envelope_class: str | None = None
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)
    asciidoc_native: str | None = None
    content_kind: Literal["block", "inline", "none"] = "block"
    """Shape of the node's ``content`` array in ADF JSON.

    ``block``  — standard (paragraph, heading, nested blocks).
    ``inline`` — direct inline text runs (taskItem, decisionItem).
    ``none``   — the node has no content array at all (bare extensions).
    """


class MappingTable:
    """Lookup wrapper over a parsed mapping.yaml."""

    def __init__(self, entries: dict[str, MappingEntry], version: int) -> None:
        self._entries = entries
        self.version = version

    def get(self, node_type: str | None) -> MappingEntry | None:
        """Return the :class:`MappingEntry` for ``node_type`` or None."""
        if node_type is None:
            return None
        return self._entries.get(node_type)

    def __contains__(self, node_type: str) -> bool:
        return node_type in self._entries

    def names(self) -> list[str]:
        """Return all mapped ADF node type names."""
        return sorted(self._entries)


def load_mapping(path: Path | str) -> MappingTable:
    """Load and validate a mapping YAML file."""
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MappingError(f"mapping file not found: {p}") from exc
    except yaml.YAMLError as exc:
        raise MappingError(f"mapping YAML parse error: {exc}") from exc
    return _parse_mapping(raw)


def load_default_mapping() -> MappingTable:
    """Load the bundled default mapping table."""
    return load_mapping(_DEFAULT_MAPPING_PATH)


def _parse_mapping(raw: Any) -> MappingTable:
    if not isinstance(raw, dict):
        raise MappingError("mapping root must be a mapping")
    version = raw.get("version")
    if not isinstance(version, int):
        raise MappingError("mapping.version (int) is required")
    nodes = raw.get("nodes")
    if not isinstance(nodes, dict):
        raise MappingError("mapping.nodes (mapping) is required")

    entries: dict[str, MappingEntry] = {}
    for name, spec in nodes.items():
        if not isinstance(spec, dict):
            raise MappingError(f"node {name!r} must be a mapping")
        kind = spec.get("kind")
        if kind not in ("block", "inline"):
            raise MappingError(f"node {name!r}: kind must be 'block' or 'inline'")
        pandoc = spec.get("pandoc")
        if not isinstance(pandoc, str):
            raise MappingError(f"node {name!r}: pandoc (str) is required")
        attrs = spec.get("attrs") or {}
        if not isinstance(attrs, dict):
            raise MappingError(f"node {name!r}: attrs must be a mapping")
        children = spec.get("children") or []
        if not isinstance(children, list):
            raise MappingError(f"node {name!r}: children must be a list")
        content_kind = spec.get("content_kind", "block")
        if content_kind not in ("block", "inline", "none"):
            raise MappingError(f"node {name!r}: content_kind must be 'block', 'inline', or 'none'")
        entries[name] = MappingEntry(
            node_type=name,
            pandoc=pandoc,
            kind=kind,
            envelope_class=spec.get("envelope_class"),
            attrs={str(k): str(v) for k, v in attrs.items()},
            children=[str(c) for c in children],
            asciidoc_native=spec.get("asciidoc_native"),
            content_kind=content_kind,
        )

    return MappingTable(entries, version=version)
