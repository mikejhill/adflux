import subprocess
import sys
from pathlib import Path

import pytest

from adflux.adf.spec import MARKS, NODES, node_spec

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("script", ["generate_spec.py", "build_profile_data.py"])
def test_generated_files_are_fresh(script):
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_core_nodes_present():
    for name in ("doc", "paragraph", "text", "panel", "table", "extension", "mediaSingle", "taskList", "status"):
        assert name in NODES
    for name in ("strong", "link", "textColor", "alignment", "breakout"):
        assert name in MARKS


def test_attr_kinds():
    heading = node_spec("heading")
    level = heading.attr("level")
    assert level is not None and level.required
    assert level.coerce("3") == 3
    panel = node_spec("panel").attr("panelType")
    assert panel is not None and "info" in panel.enum
    assert node_spec("status").inline
    assert not node_spec("panel").inline


def test_content_rules():
    assert "listItem" in node_spec("bulletList").content
    assert "paragraph" in node_spec("panel").content
    assert node_spec("rule").leaf
