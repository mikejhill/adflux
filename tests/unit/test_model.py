import json

import pytest

from adflux.adf.model import Node, dump, load
from adflux.adf.normalize import canonical, expel_whitespace, normalize
from adflux.errors import AdfError


def test_load_variants():
    doc = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "x"}]}]}
    assert load(doc).to_json() == doc
    assert load(json.dumps(doc)).to_json() == doc
    assert load(json.dumps(doc).encode()).to_json() == doc
    envelope = {"representation": "atlas_doc_format", "value": json.dumps(doc)}
    assert load(envelope).to_json() == doc
    wrapped = load({"type": "paragraph", "content": []})
    assert wrapped.type == "doc" and wrapped.children[0].type == "paragraph"


def test_unknown_keys_survive():
    doc = {"type": "doc", "version": 1, "content": [{"type": "futureNode", "attrs": {"a": 1}, "newKey": [1, 2]}]}
    assert json.loads(dump(load(doc))) == doc


def test_load_errors():
    with pytest.raises(AdfError):
        load("not json")
    with pytest.raises(AdfError):
        load({"content": []})


def test_normalize_merges_and_orders():
    node = Node.from_json(
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "a", "marks": [{"type": "strong"}, {"type": "em"}]},
                {"type": "text", "text": "b", "marks": [{"type": "em"}, {"type": "strong"}]},
                {"type": "text", "text": ""},
            ],
        }
    )
    normalize(node)
    assert node.to_json() == {
        "type": "paragraph",
        "content": [{"type": "text", "text": "ab", "marks": [{"type": "em"}, {"type": "strong"}]}],
    }


def test_canonical_drops_server_noise():
    a = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "table",
                "attrs": {"localId": "x", "layout": "default"},
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "attrs": {"colspan": 1, "rowspan": 1},
                                "content": [{"type": "paragraph"}],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    b = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "table",
                "content": [
                    {"type": "tableRow", "content": [{"type": "tableCell", "content": [{"type": "paragraph"}]}]}
                ],
            }
        ],
    }
    assert canonical(a) == canonical(b)


def test_expel_whitespace():
    node = Node.from_json(
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "a "},
                {"type": "text", "text": " b ", "marks": [{"type": "strong"}, {"type": "underline"}]},
                {"type": "text", "text": "c"},
            ],
        }
    )
    expel_whitespace(node)
    assert node.to_json()["content"] == [
        {"type": "text", "text": "a "},
        {"type": "text", "text": " ", "marks": [{"type": "underline"}]},
        {"type": "text", "text": "b", "marks": [{"type": "strong"}, {"type": "underline"}]},
        {"type": "text", "text": " ", "marks": [{"type": "underline"}]},
        {"type": "text", "text": "c"},
    ]
