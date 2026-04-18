"""Tests for fidelity profile behavior on lossy-target writes."""

from __future__ import annotations

import json

import pytest

from adflux import convert
from adflux.errors import UnrepresentableNodeError

UGLY_ADF = {
    "version": 1,
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]},
        {
            "type": "panel",
            "attrs": {"panelType": "info"},
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Info body"}]},
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Before "},
                {
                    "type": "status",
                    "attrs": {"text": "DONE", "color": "green", "localId": "x"},
                },
                {"type": "text", "text": " after"},
            ],
        },
    ],
}


def _to_json_str(doc: dict) -> str:
    return json.dumps(doc)


def test_pretty_md_drops_envelopes():
    out = convert(_to_json_str(UGLY_ADF), src="adf", dst="markdown", profile="pretty-md")
    # Panel's body paragraph should still be present; "Info body" text survives.
    assert "Info body" in out
    # "Before" and "after" bracketing the dropped inline status should remain.
    assert "Before" in out and "after" in out
    # No envelope markers should leak through.
    assert "adf-" not in out


def test_fail_loud_raises():
    with pytest.raises(UnrepresentableNodeError):
        convert(_to_json_str(UGLY_ADF), src="adf", dst="markdown", profile="fail-loud")


def test_strict_adf_renders_idiomatic_markdown():
    out = convert(_to_json_str(UGLY_ADF), src="adf", dst="markdown", profile="strict-adf")
    # Default rendering uses GitHub alert blockquotes for panels and HTML
    # comment markers for inline ADF nodes that have no native MD idiom.
    assert "[!NOTE]" in out
    assert "<!--adf:status" in out
    assert "Info body" in out
    # No legacy fenced-div envelope syntax should appear in the output.
    assert ":::" not in out


def test_strict_adf_pretty_round_trips_to_adf():
    # MD -> ADF should rebuild the original envelopes from the prettified forms.
    md = convert(_to_json_str(UGLY_ADF), src="adf", dst="markdown", profile="strict-adf")
    adf_back = convert(md, src="markdown", dst="adf", profile="strict-adf")
    parsed = json.loads(adf_back)
    types = {n["type"] for n in parsed.get("content", [])}
    assert "panel" in types


def test_reader_rejects_legacy_fenced_div_input():
    # Legacy pandoc-style ``::: {.adf-panel ...}`` syntax is no longer
    # supported as a source form; the reader treats it as plain text and
    # produces no panel envelope.
    md = "::: {.adf-panel panelType=info}\nInfo body\n:::\n"
    adf = convert(md, src="markdown", dst="adf", profile="strict-adf")
    parsed = json.loads(adf)
    types = {n["type"] for n in parsed.get("content", [])}
    assert "panel" not in types
