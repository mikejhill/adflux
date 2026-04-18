"""End-to-end integration tests covering the convert pipeline."""

from __future__ import annotations

import json

import pytest

from adflux import convert


def test_md_to_adf_simple():
    md = "# Title\n\nHello **world**.\n"
    adf_text = convert(md, src="md", dst="adf")
    adf = json.loads(adf_text)
    assert adf["type"] == "doc"
    types = [n["type"] for n in adf["content"]]
    assert "heading" in types
    assert "paragraph" in types


def test_adf_to_md_simple():
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": "Title"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hello "},
                    {"type": "text", "text": "world", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": "."},
                ],
            },
        ],
    }
    md = convert(json.dumps(adf), src="adf", dst="md")
    assert "Title" in md
    assert "**world**" in md


def test_md_adf_md_roundtrip_is_stable():
    md_in = "# Hello\n\nA paragraph with *emphasis* and **strength**.\n"
    adf = convert(md_in, src="md", dst="adf")
    md_out = convert(adf, src="adf", dst="md")
    # second pass should be stable
    adf2 = convert(md_out, src="md", dst="adf")
    md_out2 = convert(adf2, src="adf", dst="md")
    assert md_out == md_out2


def test_unsupported_format_raises():
    from adflux.errors import UnsupportedFormatError

    with pytest.raises(UnsupportedFormatError):
        convert("x", src="xyz", dst="md")
