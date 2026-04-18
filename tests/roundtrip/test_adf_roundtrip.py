"""Round-trip tests: ADF -> IR -> ADF must equal input (modulo normalization)."""

from __future__ import annotations

import json

import pytest

from adflux.formats.adf.reader import read_adf
from adflux.formats.adf.writer import write_adf
from adflux.options import Options

OPTIONS = Options({"envelopes": "keep", "jira-strict": "false"})


def _roundtrip(adf: dict) -> dict:
    doc = read_adf(json.dumps(adf), OPTIONS)
    return json.loads(write_adf(doc, OPTIONS))


CASES: list[tuple[str, dict]] = [
    (
        "empty",
        {"type": "doc", "version": 1, "content": []},
    ),
    (
        "paragraph-plain",
        {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "hi"}]},
            ],
        },
    ),
    (
        "heading-l3",
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Title"}],
                }
            ],
        },
    ),
    (
        "panel-with-para",
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "panel",
                    "attrs": {"panelType": "info"},
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "note"}],
                        }
                    ],
                }
            ],
        },
    ),
    (
        "rule",
        {"type": "doc", "version": 1, "content": [{"type": "rule"}]},
    ),
    (
        "code-block",
        {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "codeBlock",
                    "attrs": {"language": "python"},
                    "content": [{"type": "text", "text": "print(1)"}],
                }
            ],
        },
    ),
]


@pytest.mark.parametrize(("name", "adf"), CASES, ids=[c[0] for c in CASES])
def test_adf_roundtrip(name, adf):
    result = _roundtrip(adf)
    assert result["type"] == adf["type"]
    assert result["version"] == adf["version"]
    assert result["content"] == adf["content"]
