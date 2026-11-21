"""Shared fixtures; suite markers come from the directory a test lives in.

``tests/unit`` → ``unit``, ``tests/roundtrip`` → ``roundtrip``, ``tests/e2e`` → ``e2e``,
so ``pytest -m unit`` selects a suite without every file repeating its marker.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile("default", max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("thorough", max_examples=2000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

ROOT = Path(__file__).parent
SUITES = ("unit", "roundtrip", "e2e")
LIVE = ROOT / "fixtures" / "live"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if not item.path.is_relative_to(ROOT):
            continue
        parts = item.path.relative_to(ROOT).parts
        if parts and parts[0] in SUITES:
            item.add_marker(getattr(pytest.mark, parts[0]))


def live(name: str):
    return json.loads((LIVE / name).read_text(encoding="utf-8"))


@pytest.fixture
def kitchen() -> dict[str, Any]:
    return live("kitchen.json")
