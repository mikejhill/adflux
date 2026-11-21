"""Canonical form of ADF trees.

Two documents that render the same can differ in incidental ways: adjacent text nodes with
the same marks, mark order, empty text, generated ``localId`` values, attributes a server
fills in. :func:`normalize` removes the first three (it never changes meaning);
:func:`canonical` additionally drops server noise so tests and diffs compare what matters.
"""

from __future__ import annotations

import copy
from typing import Any

from adflux.adf.model import Mark, Node

# Mark order used by the Atlassian editor (``marks-in-order`` in @atlaskit/adf-schema).
MARK_ORDER = [
    "link",
    "em",
    "strong",
    "textColor",
    "backgroundColor",
    "strike",
    "subsup",
    "underline",
    "code",
    "typeAheadQuery",
    "alignment",
    "annotation",
    "confluenceInlineComment",
    "breakout",
    "indentation",
    "dataConsumer",
    "fragment",
    "border",
    "fontSize",
]
_RANK = {name: i for i, name in enumerate(MARK_ORDER)}


def sort_marks(marks: list[Mark]) -> list[Mark]:
    """Return ``marks`` in the editor's canonical order (stable for unknown marks)."""
    return sorted(marks, key=lambda m: _RANK.get(m.type, len(_RANK)))


def normalize(node: Node) -> Node:
    """Merge adjacent same-mark text, drop empty text, and order marks (in place)."""
    node.marks = sort_marks(node.marks)
    if node.content is None:
        return node
    merged: list[Node] = []
    for child in node.content:
        normalize(child)
        if child.type == "text":
            if not child.text:
                continue
            last = merged[-1] if merged else None
            if (
                last is not None
                and last.type == "text"
                and [m.key() for m in last.marks] == [m.key() for m in child.marks]
                and not last.extra
                and not child.extra
            ):
                last.text = (last.text or "") + child.text
                continue
        merged.append(child)
    node.content = merged
    return node


# Marks Markdown writes as ``*``/``**``/``~~`` delimiters, which cannot open or close
# next to whitespace.
DELIMITED_MARKS = frozenset({"strong", "em", "strike"})


def expel_whitespace(node: Node) -> Node:
    """Move spaces at the edges of strong/em/strike runs outside the run (in place).

    ``**bold **`` is not emphasis in CommonMark, so the Markdown writer applies this
    first; renderers show the space either way.
    """
    if node.content is None:
        return node
    for child in node.content:
        expel_whitespace(child)
    out: list[Node] = []
    items = node.content
    for index, child in enumerate(items):
        delimited = [m for m in child.marks if m.type in DELIMITED_MARKS]
        if child.type != "text" or not child.text or not delimited or child.has_mark("code"):
            out.append(child)
            continue
        text = child.text
        core = text.strip(" ")
        if core == text:
            out.append(child)
            continue
        lead = text[: len(text) - len(text.lstrip(" "))]
        trail = text[len(text.rstrip(" ")) :] if core else ""
        if not core:
            lead = text
        prev_keys = {m.key() for m in items[index - 1].marks} if index > 0 else set()
        next_keys = {m.key() for m in items[index + 1].marks} if index + 1 < len(items) else set()

        def edge(spaces: str, neighbour: set[Any], child: Node = child) -> Node:
            kept = [m for m in child.marks if m.type not in DELIMITED_MARKS or m.key() in neighbour]
            return Node("text", text=spaces, marks=copy.deepcopy(kept))

        if lead:
            out.append(edge(lead, prev_keys if core else prev_keys & next_keys))
        if core:
            out.append(Node("text", text=core, marks=child.marks, extra=child.extra))
        if trail:
            out.append(edge(trail, next_keys))
    node.content = out
    return normalize(node) if node.type != "text" else node


# Attributes servers add on save that carry no meaning for the author.
SERVER_ATTRS: dict[str, dict[str, Any]] = {
    "mention": {"accessLevel": "", "userType": None},
    "status": {"style": None},
    "orderedList": {"order": 1},
    "tableCell": {"colspan": 1, "rowspan": 1},
    "tableHeader": {"colspan": 1, "rowspan": 1},
    "table": {"isNumberColumnEnabled": False, "layout": "default", "localId": None},
}
LOCAL_ID_REQUIRED = frozenset({"taskList", "taskItem", "blockTaskItem", "decisionList", "decisionItem"})


def canonical(node: Node | dict[str, Any], *, keep_local_ids: bool = False) -> dict[str, Any]:
    """Return a comparison form: normalized JSON without server-filled noise.

    Drops ``localId`` (unless ``keep_local_ids``), extension ``macroMetadata``, server
    defaults listed in :data:`SERVER_ATTRS`, and empty ``attrs``.
    """
    tree = Node.from_json(node) if isinstance(node, dict) else copy.deepcopy(node)
    normalize(tree)
    return _strip(tree, keep_local_ids).to_json()


def _strip(node: Node, keep_local_ids: bool) -> Node:
    attrs = dict(node.attrs)
    if not keep_local_ids:
        attrs.pop("localId", None)
    for key, default in SERVER_ATTRS.get(node.type, {}).items():
        if key == "localId":
            continue  # handled above, so keep_local_ids is honoured
        if key in attrs and (default is None or attrs[key] == default):
            del attrs[key]
    if node.type in ("extension", "bodiedExtension", "inlineExtension"):
        params = attrs.get("parameters")
        if isinstance(params, dict) and "macroMetadata" in params:
            attrs["parameters"] = {k: v for k, v in params.items() if k != "macroMetadata"}
    node.attrs = attrs
    for child in node.children:
        _strip(child, keep_local_ids)
    return node
