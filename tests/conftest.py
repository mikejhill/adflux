import json
import os
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile("default", max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("thorough", max_examples=2000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

LIVE = Path(__file__).parent / "fixtures" / "live"


def live(name: str):
    return json.loads((LIVE / name).read_text(encoding="utf-8"))


@pytest.fixture
def kitchen() -> dict:
    return live("kitchen.json")
