"""Tests for ADF JSON-schema validation."""

from __future__ import annotations

import json

import pytest

from adflux.errors import InvalidADFError
from adflux.formats.adf.schema import validate_adf


def test_valid_minimal_doc():
    validate_adf({"type": "doc", "version": 1, "content": []})


def test_valid_paragraph():
    validate_adf(
        {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}],
        }
    )


def test_rejects_missing_type():
    with pytest.raises(InvalidADFError):
        validate_adf({"version": 1, "content": []})


def test_rejects_wrong_type():
    with pytest.raises(InvalidADFError):
        validate_adf({"type": "something-else", "version": 1, "content": []})


def test_rejects_bad_json_string():
    with pytest.raises(InvalidADFError, match="invalid JSON"):
        validate_adf("{not-json")


def test_accepts_string_input():
    validate_adf(json.dumps({"type": "doc", "version": 1, "content": []}))


def test_reports_pointer_on_failure():
    try:
        validate_adf({"type": "doc", "version": 1, "content": [{"noType": True}]})
    except InvalidADFError as exc:
        assert exc.pointer is not None
        assert "content" in exc.pointer
    else:
        pytest.fail("expected InvalidADFError")
