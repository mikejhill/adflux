"""Tests for the options system."""

from __future__ import annotations

import pytest

from adflux.options import OptionDef, OptionRegistry, Options, get_registry


def test_registry_has_core_options():
    reg = get_registry()
    names = [d.name for d in reg.all()]
    assert "envelopes" in names
    assert "jira-strict" in names


def test_resolve_defaults():
    reg = get_registry()
    opts = reg.resolve()
    assert opts["envelopes"] == "keep"
    assert opts["jira-strict"] == "false"


def test_resolve_with_overrides():
    reg = get_registry()
    opts = reg.resolve({"envelopes": "drop", "jira-strict": "true"})
    assert opts["envelopes"] == "drop"
    assert opts["jira-strict"] == "true"


def test_resolve_rejects_invalid_choice():
    reg = get_registry()
    with pytest.raises(ValueError, match="envelopes"):
        reg.resolve({"envelopes": "nope"})


def test_options_immutable():
    opts = Options({"envelopes": "keep"})
    with pytest.raises(TypeError):
        opts["envelopes"] = "drop"  # type: ignore[index]


def test_options_getitem_fallback_to_empty():
    opts = Options({})
    assert opts["unknown-key"] == ""


def test_options_iter_and_len():
    opts = Options({"a": "1", "b": "2"})
    assert len(opts) == 2
    assert set(opts) == {"a", "b"}


def test_custom_registry():
    reg = OptionRegistry()
    reg.register(OptionDef(name="foo", description="A foo", choices=("x", "y"), default="x"))
    opts = reg.resolve({"foo": "y"})
    assert opts["foo"] == "y"
