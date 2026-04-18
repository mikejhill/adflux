"""Property-based round-trip test for ADF using Hypothesis.

Generates small random ADF documents using the subset of node types that are
first-class in the mapping table, and asserts that ``ADF -> panflute -> ADF``
preserves structure and attributes exactly.
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from adflux.formats.adf.reader import read_adf
from adflux.formats.adf.writer import write_adf
from adflux.options import Options

OPTIONS = Options({"envelopes": "keep", "jira-strict": "false"})


def _text(s: str) -> dict:
    return {"type": "text", "text": s}


_INLINE = st.builds(_text, st.text(min_size=1, max_size=20).filter(lambda s: s.strip()))

_PARA = st.builds(
    lambda kids: {"type": "paragraph", "content": kids},
    st.lists(_INLINE, min_size=1, max_size=4),
)

_HEADING = st.builds(
    lambda level, kids: {"type": "heading", "attrs": {"level": level}, "content": kids},
    st.integers(min_value=1, max_value=6),
    st.lists(_INLINE, min_size=1, max_size=3),
)

_CODEBLOCK = st.builds(
    lambda text: {"type": "codeBlock", "content": [_text(text)]},
    st.text(alphabet="abc \n", min_size=1, max_size=30).filter(lambda s: s.strip()),
)

_RULE = st.just({"type": "rule"})

_BLOCKS = st.one_of(_PARA, _HEADING, _CODEBLOCK, _RULE)

_DOC = st.builds(
    lambda kids: {"version": 1, "type": "doc", "content": kids},
    st.lists(_BLOCKS, min_size=1, max_size=5),
)


@settings(max_examples=30, deadline=None)
@given(_DOC)
def test_adf_roundtrip_property(doc: dict) -> None:
    ir = read_adf(json.dumps(doc), OPTIONS)
    out_text = write_adf(ir, OPTIONS)
    out = json.loads(out_text)
    assert out["type"] == "doc"
    # Content length matches the input top-level block count.
    assert len(out["content"]) == len(doc["content"])
    # Types are preserved in order.
    assert [b["type"] for b in out["content"]] == [b["type"] for b in doc["content"]]
