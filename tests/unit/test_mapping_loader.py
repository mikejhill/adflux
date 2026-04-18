"""Tests for the YAML mapping loader."""

from __future__ import annotations

import textwrap

import pytest

from adflux.errors import MappingError
from adflux.formats.adf.mapping import load_default_mapping, load_mapping


def _write_yaml(tmp_path, content: str):
    path = tmp_path / "mapping.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_default_mapping_loads_and_covers_key_nodes():
    table = load_default_mapping()
    for required in ["panel", "mention", "status", "extension", "taskList", "layoutSection"]:
        assert required in table, f"mapping.yaml missing {required!r}"


def test_mapping_requires_version(tmp_path):
    path = _write_yaml(tmp_path, "nodes: {}\n")
    with pytest.raises(MappingError, match="version"):
        load_mapping(path)


def test_mapping_requires_kind(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
        version: 1
        nodes:
          foo:
            pandoc: Div
        """,
    )
    with pytest.raises(MappingError, match="kind"):
        load_mapping(path)


def test_mapping_rejects_bad_kind(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
        version: 1
        nodes:
          foo:
            pandoc: Div
            kind: paragraph
        """,
    )
    with pytest.raises(MappingError, match="kind"):
        load_mapping(path)


def test_mapping_missing_file_raises():
    with pytest.raises(MappingError, match="not found"):
        load_mapping("/nonexistent/mapping.yaml")
