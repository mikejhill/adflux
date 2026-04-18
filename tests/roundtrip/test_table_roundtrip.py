"""Regression tests for ADF table reader/writer."""

from __future__ import annotations

import json
from typing import Any

from adflux.formats.adf.reader import read_adf
from adflux.formats.adf.writer import write_adf
from adflux.profiles import resolve_profile

PROFILE = resolve_profile("strict-adf")


def _para(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _cell(text: str, *, header: bool = False) -> dict[str, Any]:
    return {
        "type": "tableHeader" if header else "tableCell",
        "content": [_para(text)],
    }


def _doc(*blocks: dict[str, Any]) -> dict[str, Any]:
    return {"type": "doc", "version": 1, "content": list(blocks)}


def _roundtrip(adf: dict[str, Any]) -> dict[str, Any]:
    doc = read_adf(json.dumps(adf), PROFILE, {})
    return json.loads(write_adf(doc, PROFILE, {}))


def test_table_with_header_and_body_roundtrips_all_rows() -> None:
    table = {
        "type": "table",
        "content": [
            {
                "type": "tableRow",
                "content": [_cell("A", header=True), _cell("B", header=True)],
            },
            {"type": "tableRow", "content": [_cell("1"), _cell("2")]},
            {"type": "tableRow", "content": [_cell("3"), _cell("4")]},
        ],
    }
    out = _roundtrip(_doc(table))
    out_table = out["content"][0]
    assert out_table["type"] == "table"
    assert len(out_table["content"]) == 3
    assert [r["content"][0]["type"] for r in out_table["content"]] == [
        "tableHeader",
        "tableCell",
        "tableCell",
    ]


def test_table_without_header_preserves_all_body_rows() -> None:
    table = {
        "type": "table",
        "content": [
            {"type": "tableRow", "content": [_cell("a"), _cell("b")]},
            {"type": "tableRow", "content": [_cell("c"), _cell("d")]},
        ],
    }
    out = _roundtrip(_doc(table))
    rows = out["content"][0]["content"]
    assert len(rows) == 2
    assert all(r["content"][0]["type"] == "tableCell" for r in rows)
