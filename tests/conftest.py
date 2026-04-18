"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return the golden-fixtures directory."""
    return Path(__file__).parent / "golden" / "fixtures"
