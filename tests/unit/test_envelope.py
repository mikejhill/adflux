"""Unit tests for the envelope pack/unpack primitives."""

from __future__ import annotations

import panflute as pf
import pytest

from adflux.ir.envelope import (
    ENVELOPE_CLASS_PREFIX,
    Envelope,
    is_envelope,
    pack_envelope,
    unpack_envelope,
)


def test_pack_block_envelope_basic_attrs():
    div = pack_envelope("panel", kind="block", attrs={"panelType": "info"})
    assert isinstance(div, pf.Div)
    assert f"{ENVELOPE_CLASS_PREFIX}panel" in div.classes
    assert div.attributes["panelType"] == "info"


def test_pack_inline_envelope_returns_span():
    span = pack_envelope("status", kind="inline", attrs={"color": "green", "text": "OK"})
    assert isinstance(span, pf.Span)
    assert "adf-status" in span.classes
    assert span.attributes["color"] == "green"


def test_pack_envelope_complex_attr_uses_json_blob():
    div = pack_envelope(
        "extension",
        kind="block",
        attrs={"extensionKey": "macro", "parameters": {"foo": [1, 2, 3]}},
    )
    assert "data-adf-json" in div.attributes
    # simple scalar still stored flat
    assert div.attributes["extensionKey"] == "macro"


def test_roundtrip_simple_envelope():
    original = pack_envelope(
        "panel",
        kind="block",
        attrs={"panelType": "warning"},
        children=[pf.Para(pf.Str("hi"))],
    )
    env = unpack_envelope(original)
    assert env == Envelope(
        node_type="panel",
        kind="block",
        attrs={"panelType": "warning"},
        classes=["adf-panel"],
    )


def test_roundtrip_complex_payload():
    complex_params = {"jql": "project = TEST", "columns": ["key", "summary"]}
    div = pack_envelope(
        "extension",
        kind="block",
        attrs={"extensionKey": "jira-filter", "parameters": complex_params},
    )
    env = unpack_envelope(div)
    assert env.attrs["extensionKey"] == "jira-filter"
    assert env.attrs["parameters"] == complex_params


def test_raw_envelope_preserves_full_payload():
    payload = {"type": "futureUnknownNode", "attrs": {"x": 1}, "content": []}
    div = pack_envelope("raw", kind="block", raw_payload=payload)
    env = unpack_envelope(div)
    assert env.node_type == "raw"
    # raw payload is stored in attrs via the json blob
    # (implementation detail: unpack merges the blob into attrs)
    assert env.attrs == payload


def test_is_envelope_true_false():
    div = pack_envelope("panel", kind="block")
    assert is_envelope(div)
    assert not is_envelope(pf.Div(pf.Para(pf.Str("x")), classes=["not-envelope"]))
    assert not is_envelope(pf.Para(pf.Str("x")))


def test_unpack_envelope_rejects_non_envelope():
    with pytest.raises(ValueError, match="not an ADF envelope"):
        unpack_envelope(pf.Div(classes=["random"]))


def test_unpack_envelope_rejects_wrong_type():
    with pytest.raises(TypeError):
        unpack_envelope(pf.Para(pf.Str("x")))  # type: ignore[arg-type]


def test_bool_attr_round_trips_as_string():
    # booleans become "true"/"false" strings when flat-stored
    div = pack_envelope("panel", kind="block", attrs={"collapsed": True})
    env = unpack_envelope(div)
    assert env.attrs["collapsed"] == "true"
