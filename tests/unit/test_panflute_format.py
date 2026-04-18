"""Tests for the panflute (Pandoc JSON) reader/writer format."""

from __future__ import annotations

import json

import panflute as pf

from adflux import convert, list_formats
from adflux.formats.panflute_fmt import _panflute_reader, _panflute_writer
from adflux.options import Options

OPTIONS = Options({"envelopes": "keep", "jira-strict": "false"})


def test_panflute_registered_as_format():
    fmts = list_formats()
    assert "panflute" in fmts
    assert "pf" in fmts


def test_panflute_roundtrip():
    doc = pf.Doc(pf.Para(pf.Str("hello"), pf.Space(), pf.Str("world")))
    json_text = _panflute_writer(doc, OPTIONS)
    parsed = json.loads(json_text)
    assert "pandoc-api-version" in parsed

    doc2 = _panflute_reader(json_text, OPTIONS)
    assert isinstance(doc2, pf.Doc)
    (para,) = list(doc2.content)
    assert isinstance(para, pf.Para)
    assert pf.stringify(para).strip() == "hello world"


def test_md_to_panflute_via_convert():
    result = convert("# Hello\n\nworld\n", src="md", dst="panflute")
    parsed = json.loads(result)
    assert "pandoc-api-version" in parsed
    assert "blocks" in parsed


def test_panflute_to_md_via_convert():
    doc = pf.Doc(pf.Para(pf.Str("test")))
    json_text = _panflute_writer(doc, OPTIONS)
    result = convert(json_text, src="pf", dst="md")
    assert "test" in result


def test_panflute_to_adf_via_convert():
    doc = pf.Doc(pf.Para(pf.Str("hello")))
    json_text = _panflute_writer(doc, OPTIONS)
    result = convert(json_text, src="panflute", dst="adf")
    parsed = json.loads(result)
    assert parsed["type"] == "doc"
    assert parsed["content"][0]["type"] == "paragraph"
