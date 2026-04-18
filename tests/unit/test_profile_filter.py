"""Tests for the options system (envelopes behavior) on lossy-target writes."""

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


def test_envelopes_drop_removes_envelopes():
    out = convert(_to_json_str(UGLY_ADF), src="adf", dst="markdown", options={"envelopes": "drop"})
    assert "Info body" in out
    assert "Before" in out and "after" in out
    assert "adf-" not in out


def test_envelopes_keep_strict_raises():
    with pytest.raises(UnrepresentableNodeError):
        convert(
            _to_json_str(UGLY_ADF),
            src="adf",
            dst="markdown",
            options={"envelopes": "keep-strict"},
        )


def test_envelopes_keep_renders_idiomatic_markdown():
    out = convert(_to_json_str(UGLY_ADF), src="adf", dst="markdown", options={"envelopes": "keep"})
    assert "[!NOTE]" in out
    assert "<!--adf:status" in out
    assert "Info body" in out
    assert ":::" not in out


def test_envelopes_keep_round_trips_to_adf():
    md = convert(_to_json_str(UGLY_ADF), src="adf", dst="markdown", options={"envelopes": "keep"})
    adf_back = convert(md, src="markdown", dst="adf", options={"envelopes": "keep"})
    parsed = json.loads(adf_back)
    types = {n["type"] for n in parsed.get("content", [])}
    assert "panel" in types


def test_reader_rejects_legacy_fenced_div_input():
    md = "::: {.adf-panel panelType=info}\nInfo body\n:::\n"
    adf = convert(md, src="markdown", dst="adf", options={"envelopes": "keep"})
    parsed = json.loads(adf)
    types = {n["type"] for n in parsed.get("content", [])}
    assert "panel" not in types
