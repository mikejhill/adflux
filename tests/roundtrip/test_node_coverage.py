"""Per-node ADF round-trip coverage.

For every ADF node type declared in ``mapping.yaml`` (plus the structural
nodes the reader/writer handle directly), this test builds a minimal ADF
document containing that node and asserts that ``ADF -> IR -> ADF`` is a
no-op (modulo canonical ordering of keys).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from adflux.formats.adf.mapping import load_default_mapping
from adflux.formats.adf.reader import read_adf
from adflux.formats.adf.writer import write_adf
from adflux.options import Options

OPTIONS = Options({"envelopes": "keep", "jira-strict": "false"})


def _roundtrip(adf: dict[str, Any]) -> dict[str, Any]:
    doc = read_adf(json.dumps(adf), OPTIONS)
    return json.loads(write_adf(doc, OPTIONS))


def _wrap(*nodes: dict[str, Any]) -> dict[str, Any]:
    return {"type": "doc", "version": 1, "content": list(nodes)}


def _para(text: str = "x") -> dict[str, Any]:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


# Minimal valid ADF node examples for every type we advertise support for.
# Keep structures realistic but as small as possible.
_NODE_EXAMPLES: dict[str, dict[str, Any]] = {
    # --- structural (hard-coded in reader/writer) ---
    "paragraph": _para("hello"),
    "heading": {
        "type": "heading",
        "attrs": {"level": 2},
        "content": [{"type": "text", "text": "Title"}],
    },
    "codeBlock": {
        "type": "codeBlock",
        "attrs": {"language": "python"},
        "content": [{"type": "text", "text": "x=1"}],
    },
    "blockquote": {"type": "blockquote", "content": [_para("quoted")]},
    "bulletList": {
        "type": "bulletList",
        "content": [{"type": "listItem", "content": [_para("a")]}],
    },
    "orderedList": {
        "type": "orderedList",
        "content": [{"type": "listItem", "content": [_para("a")]}],
    },
    "rule": {"type": "rule"},
    # --- mapping-driven ---
    "panel": {
        "type": "panel",
        "attrs": {"panelType": "info"},
        "content": [_para("note")],
    },
    "expand": {"type": "expand", "attrs": {"title": "More"}, "content": [_para("x")]},
    "nestedExpand": {
        "type": "nestedExpand",
        "attrs": {"title": "Sub"},
        "content": [_para("y")],
    },
    "layoutSection": {
        "type": "layoutSection",
        "content": [
            {
                "type": "layoutColumn",
                "attrs": {"width": "50"},
                "content": [_para("left")],
            },
            {
                "type": "layoutColumn",
                "attrs": {"width": "50"},
                "content": [_para("right")],
            },
        ],
    },
    "taskList": {
        "type": "taskList",
        "attrs": {"localId": "t1"},
        "content": [
            {
                "type": "taskItem",
                "attrs": {"state": "TODO", "localId": "t1-1"},
                "content": [{"type": "text", "text": "do it"}],
            }
        ],
    },
    "decisionList": {
        "type": "decisionList",
        "attrs": {"localId": "d1"},
        "content": [
            {
                "type": "decisionItem",
                "attrs": {"state": "DECIDED", "localId": "d1-1"},
                "content": [{"type": "text", "text": "ship it"}],
            }
        ],
    },
    "extension": {
        "type": "extension",
        "attrs": {
            "extensionKey": "my-macro",
            "extensionType": "com.atlassian.confluence.macro.core",
        },
    },
    "bodiedExtension": {
        "type": "bodiedExtension",
        "attrs": {
            "extensionKey": "my-bodied",
            "extensionType": "com.atlassian.confluence.macro.core",
        },
        "content": [_para("body")],
    },
    "mediaSingle": {
        "type": "mediaSingle",
        "attrs": {"layout": "center"},
        "content": [
            {
                "type": "media",
                "attrs": {"type": "file", "id": "abc-123", "collection": "x"},
            }
        ],
    },
    "mediaGroup": {
        "type": "mediaGroup",
        "content": [
            {
                "type": "media",
                "attrs": {"type": "file", "id": "abc-124", "collection": "x"},
            }
        ],
    },
    "blockCard": {
        "type": "blockCard",
        "attrs": {"url": "https://example.com/card"},
    },
    "embedCard": {
        "type": "embedCard",
        "attrs": {"url": "https://example.com/embed", "layout": "center"},
    },
}


@pytest.mark.parametrize(("name", "node"), list(_NODE_EXAMPLES.items()), ids=list(_NODE_EXAMPLES))
def test_per_node_roundtrip(name: str, node: dict[str, Any]) -> None:
    src = _wrap(node)
    got = _roundtrip(src)
    assert got["content"] == src["content"], f"node {name!r} did not round-trip"


def test_mapping_covers_all_advertised_nodes():
    """Every mapping.yaml entry is exercised by at least one round-trip test."""
    mapping = load_default_mapping()
    uncovered = [n for n in mapping.names() if n not in _NODE_EXAMPLES]
    # Accept children-only nodes (media, layoutColumn, taskItem, decisionItem,
    # listItem, inline-only mentions/status/etc) being exercised indirectly.
    children_only = {
        "media",
        "layoutColumn",
        "taskItem",
        "decisionItem",
        "mention",
        "emoji",
        "status",
        "date",
        "placeholder",
        "inlineCard",
        "inlineExtension",
        "mediaInline",
    }
    missing = [n for n in uncovered if n not in children_only]
    assert not missing, f"mapping entries lack fixtures: {missing}"


# --- Inline envelope coverage: every inline mapping node in a paragraph. ---

_INLINE_EXAMPLES: dict[str, dict[str, Any]] = {
    "mention": {
        "type": "mention",
        "attrs": {"id": "user-1", "text": "@alice"},
    },
    "emoji": {
        "type": "emoji",
        "attrs": {"shortName": ":smile:", "id": "1f600", "text": "😀"},
    },
    "status": {
        "type": "status",
        "attrs": {"text": "In Progress", "color": "yellow", "localId": "s1"},
    },
    "date": {"type": "date", "attrs": {"timestamp": "1700000000000"}},
    "placeholder": {"type": "placeholder", "attrs": {"text": "type here"}},
    "inlineCard": {"type": "inlineCard", "attrs": {"url": "https://example.com"}},
    "inlineExtension": {
        "type": "inlineExtension",
        "attrs": {
            "extensionKey": "inline-macro",
            "extensionType": "com.atlassian.confluence.macro.core",
        },
    },
}


@pytest.mark.parametrize(
    ("name", "inline"),
    list(_INLINE_EXAMPLES.items()),
    ids=list(_INLINE_EXAMPLES),
)
def test_inline_node_roundtrip(name: str, inline: dict[str, Any]) -> None:
    src = _wrap({"type": "paragraph", "content": [inline]})
    got = _roundtrip(src)
    (para,) = got["content"]
    assert para["type"] == "paragraph"
    assert para["content"] == [inline], f"inline {name!r} did not round-trip"
