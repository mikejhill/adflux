"""Live Jira round trip: an issue description must come back as uploaded."""

from __future__ import annotations

from pathlib import Path

import pytest

from adflux import canonical, to_adf, to_markdown
from tests.e2e.conftest import E2ESettings
from tests.e2e.jira_client import JiraClient

pytestmark = pytest.mark.e2e

FIXTURES = [f for f in sorted((Path(__file__).parent / "fixtures").glob("*.md")) if f.stem not in ("macros", "layouts")]


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.stem for f in FIXTURES])
def test_markdown_roundtrip_via_jira(
    fixture: Path,
    jira: JiraClient,
    created_issues: list[str],
    run_id: str,
    e2e_settings: E2ESettings,
) -> None:
    assert e2e_settings.jira_project_key is not None
    uploaded = to_adf(fixture.read_text(encoding="utf-8"), "jira", strict=True)
    created = jira.create_issue(
        project_key=e2e_settings.jira_project_key,
        summary=f"adflux E2E [{run_id}] {fixture.stem}",
        adf_description=uploaded,
    )
    created_issues.append(str(created["key"]))
    stored = jira.get_issue(str(created["key"]))["fields"]["description"]

    assert canonical(stored) == canonical(uploaded)
    again = to_adf(to_markdown(stored, "jira"), "jira")
    assert canonical(again) == canonical(stored)
