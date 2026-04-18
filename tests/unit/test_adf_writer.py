"""Tests for the panflute Doc -> ADF JSON writer."""

from __future__ import annotations

import json

import panflute as pf

from adflux.formats.adf.writer import write_adf
from adflux.ir.envelope import pack_envelope
from adflux.profiles import resolve_profile

PROFILE = resolve_profile("strict-adf")


def _write(doc: pf.Doc) -> dict:
    return json.loads(write_adf(doc, PROFILE, {}))


def test_empty_doc_shape():
    adf = _write(pf.Doc())
    assert adf == {"type": "doc", "version": 1, "content": []}


def test_paragraph():
    doc = pf.Doc(pf.Para(pf.Str("hello"), pf.Space(), pf.Str("world")))
    adf = _write(doc)
    (para,) = adf["content"]
    assert para["type"] == "paragraph"
    (text_node,) = para["content"]
    assert text_node == {"type": "text", "text": "hello world"}


def test_heading():
    doc = pf.Doc(pf.Header(pf.Str("Title"), level=2))
    adf = _write(doc)
    (h,) = adf["content"]
    assert h["type"] == "heading"
    assert h["attrs"] == {"level": 2}


def test_strong_mark_serialized():
    doc = pf.Doc(pf.Para(pf.Strong(pf.Str("bold"))))
    adf = _write(doc)
    (para,) = adf["content"]
    (text,) = para["content"]
    assert text["text"] == "bold"
    assert text["marks"] == [{"type": "strong"}]


def test_code_block():
    doc = pf.Doc(pf.CodeBlock("x = 1", classes=["python"]))
    adf = _write(doc)
    (cb,) = adf["content"]
    assert cb["type"] == "codeBlock"
    assert cb["attrs"] == {"language": "python"}
    assert cb["content"] == [{"type": "text", "text": "x = 1"}]


def test_envelope_panel_round_trips():
    panel_div = pack_envelope(
        "panel",
        kind="block",
        attrs={"panelType": "warning"},
        children=[pf.Para(pf.Str("hi"))],
    )
    doc = pf.Doc(panel_div)
    adf = _write(doc)
    (panel,) = adf["content"]
    assert panel["type"] == "panel"
    assert panel["attrs"] == {"panelType": "warning"}
    assert panel["content"][0]["type"] == "paragraph"


def test_link_round_trips():
    link = pf.Link(pf.Str("click"), url="https://example.com")
    doc = pf.Doc(pf.Para(link))
    adf = _write(doc)
    (para,) = adf["content"]
    (text,) = para["content"]
    assert text["text"] == "click"
    assert text["marks"][0]["type"] == "link"
    assert text["marks"][0]["attrs"]["href"] == "https://example.com"


def test_horizontal_rule():
    doc = pf.Doc(pf.HorizontalRule())
    adf = _write(doc)
    assert adf["content"] == [{"type": "rule"}]
