"""Tests for the ADF JSON -> panflute Doc reader."""

from __future__ import annotations

import json

import panflute as pf

from adflux.formats.adf.reader import read_adf
from adflux.ir.envelope import is_envelope, unpack_envelope
from adflux.profiles import resolve_profile

PROFILE = resolve_profile("strict-adf")


def _read(adf: dict) -> pf.Doc:
    return read_adf(json.dumps(adf), PROFILE, {})


def test_empty_doc():
    doc = _read({"type": "doc", "version": 1, "content": []})
    assert isinstance(doc, pf.Doc)
    assert list(doc.content) == []


def test_paragraph_with_text():
    doc = _read(
        {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "hello world"}]}
            ],
        }
    )
    (para,) = list(doc.content)
    assert isinstance(para, pf.Para)
    assert pf.stringify(para).strip() == "hello world"


def test_heading_level():
    doc = _read(
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "h"}],
                }
            ],
        }
    )
    (h,) = list(doc.content)
    assert isinstance(h, pf.Header)
    assert h.level == 3


def test_code_block_preserves_language_and_text():
    doc = _read(
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "codeBlock",
                    "attrs": {"language": "python"},
                    "content": [{"type": "text", "text": "x = 1"}],
                }
            ],
        }
    )
    (cb,) = list(doc.content)
    assert isinstance(cb, pf.CodeBlock)
    assert cb.text == "x = 1"
    assert cb.classes == ["python"]


def test_strong_and_em_marks():
    doc = _read(
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "bold", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": " "},
                        {"type": "text", "text": "italic", "marks": [{"type": "em"}]},
                    ],
                }
            ],
        }
    )
    para = next(iter(doc.content))
    assert any(isinstance(e, pf.Strong) for e in para.content)
    assert any(isinstance(e, pf.Emph) for e in para.content)


def test_panel_becomes_envelope():
    doc = _read(
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "panel",
                    "attrs": {"panelType": "info"},
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}],
                }
            ],
        }
    )
    (div,) = list(doc.content)
    assert is_envelope(div)
    env = unpack_envelope(div)
    assert env.node_type == "panel"
    assert env.attrs["panelType"] == "info"


def test_unknown_node_becomes_raw_envelope():
    doc = _read(
        {
            "type": "doc",
            "version": 1,
            "content": [{"type": "futureUnknown", "attrs": {"x": 1}, "content": []}],
        }
    )
    (div,) = list(doc.content)
    assert is_envelope(div)
    env = unpack_envelope(div)
    # raw-envelope fallback: stores the whole original node
    assert env.node_type == "futureUnknown"


def test_hard_break_inline():
    doc = _read(
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "a"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": "b"},
                    ],
                }
            ],
        }
    )
    para = next(iter(doc.content))
    assert any(isinstance(e, pf.LineBreak) for e in para.content)


def test_link_mark():
    doc = _read(
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "click",
                            "marks": [{"type": "link", "attrs": {"href": "https://example.com"}}],
                        }
                    ],
                }
            ],
        }
    )
    para = next(iter(doc.content))
    link = next(e for e in para.content if isinstance(e, pf.Link))
    assert link.url == "https://example.com"
