"""In-memory ADF tree.

The intermediate representation of adflux *is* the ADF document: a tree of :class:`Node`
objects carrying :class:`Mark` lists, exactly like ProseMirror, whose document model ADF
serializes. Every reader produces this tree and every writer consumes it, so a feature
added to the tree is available to every format.

Unknown properties are kept in ``extra`` so documents that use ADF additions newer than the
vendored schema still survive a read/write cycle unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from adflux.errors import AdfError

KNOWN_KEYS = frozenset({"type", "attrs", "content", "marks", "text", "version"})


@dataclass(slots=True)
class Mark:
    """A mark (``strong``, ``link``...) with its attributes."""

    type: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Return the ADF JSON object."""
        out: dict[str, Any] = {"type": self.type}
        if self.attrs:
            out["attrs"] = dict(self.attrs)
        return out

    @classmethod
    def from_json(cls, value: Any, path: str = "$") -> Mark:
        """Build a mark from ADF JSON."""
        if not isinstance(value, Mapping) or not isinstance(value.get("type"), str):
            raise AdfError("a mark must be an object with a string 'type'", path)
        attrs = value.get("attrs") or {}
        if not isinstance(attrs, Mapping):
            raise AdfError("'attrs' must be an object", f"{path}.attrs")
        return cls(value["type"], dict(attrs))

    def key(self) -> str:
        """Return a hashable identity (type plus attributes) for comparisons."""
        return self.type + json.dumps(self.attrs, sort_keys=True)


@dataclass(slots=True)
class Node:
    """An ADF node. ``content`` is ``None`` for leaf nodes that have no content array."""

    type: str
    attrs: dict[str, Any] = field(default_factory=dict)
    content: list[Node] | None = None
    marks: list[Mark] = field(default_factory=list)
    text: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def children(self) -> list[Node]:
        """Return the content list, empty for leaves."""
        return self.content or []

    def append(self, child: Node) -> Node:
        """Append ``child`` to the content (creating it) and return it."""
        if self.content is None:
            self.content = []
        self.content.append(child)
        return child

    def walk(self) -> Iterator[Node]:
        """Yield this node and every descendant, depth first."""
        yield self
        for child in self.children:
            yield from child.walk()

    def text_content(self) -> str:
        """Return the concatenated text of this subtree."""
        if self.text is not None:
            return self.text
        return "".join(child.text_content() for child in self.children)

    def has_mark(self, mark_type: str) -> bool:
        """Return whether the node carries a mark of ``mark_type``."""
        return any(m.type == mark_type for m in self.marks)

    def get_mark(self, mark_type: str) -> Mark | None:
        """Return the first mark of ``mark_type``, if any."""
        return next((m for m in self.marks if m.type == mark_type), None)

    def to_json(self) -> dict[str, Any]:
        """Return the ADF JSON object, with keys in the order Atlassian uses."""
        out: dict[str, Any] = {"type": self.type}
        if self.type == "doc":
            out["version"] = self.extra.get("version", 1)
        if self.attrs:
            out["attrs"] = dict(self.attrs)
        if self.content is not None:
            out["content"] = [child.to_json() for child in self.content]
        if self.text is not None:
            out["text"] = self.text
        if self.marks:
            out["marks"] = [m.to_json() for m in self.marks]
        for key, value in self.extra.items():
            if key != "version":
                out[key] = value
        return out

    @classmethod
    def from_json(cls, value: Any, path: str = "$") -> Node:
        """Build a node tree from ADF JSON, keeping unknown properties."""
        if not isinstance(value, Mapping):
            raise AdfError("a node must be a JSON object", path)
        kind = value.get("type")
        if not isinstance(kind, str) or not kind:
            raise AdfError("a node needs a string 'type'", path)
        attrs = value.get("attrs")
        if attrs is not None and not isinstance(attrs, Mapping):
            raise AdfError("'attrs' must be an object", f"{path}.attrs")
        raw_content = value.get("content")
        content: list[Node] | None = None
        if raw_content is not None:
            if not isinstance(raw_content, list):
                raise AdfError("'content' must be an array", f"{path}.content")
            content = [cls.from_json(child, f"{path}.content[{i}]") for i, child in enumerate(raw_content)]
        raw_marks = value.get("marks") or []
        if not isinstance(raw_marks, list):
            raise AdfError("'marks' must be an array", f"{path}.marks")
        marks = [Mark.from_json(m, f"{path}.marks[{i}]") for i, m in enumerate(raw_marks)]
        text_value = value.get("text")
        if text_value is not None and not isinstance(text_value, str):
            raise AdfError("'text' must be a string", f"{path}.text")
        extra = {k: v for k, v in value.items() if k not in KNOWN_KEYS}
        if kind == "doc" and "version" in value:
            extra["version"] = value["version"]
        return cls(kind, dict(attrs or {}), content, marks, text_value, extra)


class Doc(Node):
    """Typing alias: a :class:`Node` whose type is ``doc``."""

    __slots__ = ()


def node(
    kind: str,
    content: list[Node] | None = None,
    /,
    **attrs: Any,
) -> Node:
    """Build a node: ``node("heading", [text("Hi")], level=1)``."""
    return Node(kind, {k: v for k, v in attrs.items() if v is not None}, content)


def text(value: str, *marks: Mark) -> Node:
    """Build a text node with ``marks``."""
    return Node("text", text=value, marks=list(marks))


def mark(kind: str, **attrs: Any) -> Mark:
    """Build a mark: ``mark("link", href="https://...")``."""
    return Mark(kind, {k: v for k, v in attrs.items() if v is not None})


def load(value: str | bytes | Mapping[str, Any]) -> Node:
    """Parse ADF from a JSON string, bytes, or an already decoded mapping.

    A bare node that is not ``doc`` is wrapped in a document, and Confluence's
    ``{"value": "<json>", "representation": "atlas_doc_format"}`` envelope is unwrapped.
    """
    data: Any = value
    if isinstance(value, bytes | str):
        try:
            data = json.loads(value)
        except json.JSONDecodeError as error:
            raise AdfError(f"not valid JSON: {error.msg} (line {error.lineno})", "") from None
    if isinstance(data, Mapping) and "representation" in data and isinstance(data.get("value"), str):
        return load(data["value"])
    root = Node.from_json(data)
    if root.type != "doc":
        root = Node("doc", content=[root], extra={"version": 1})
    return root


def dump(doc: Node, *, indent: int | None = None) -> str:
    """Serialize a document to an ADF JSON string."""
    return json.dumps(doc.to_json(), ensure_ascii=False, indent=indent)
