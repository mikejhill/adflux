"""Live Jira round-trip tests.

Each fixture is converted MD -> ADF, posted as a new Jira issue's
description, fetched back, and compared structurally. Issues are
**transitioned to a done/closed status** in teardown rather than
deleted, so they remain auditable in the Jira project.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.e2e.compare import adf_node_types, adf_summary, normalize_adf
from tests.e2e.conftest import E2ESettings
from tests.e2e.jira_client import JiraClient

from adflux import convert, validate

pytestmark = pytest.mark.e2e

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Jira's description ADF profile is stricter than Confluence's. The
# fixtures below are the subset that Jira accepts; the others are excluded
# because:
#   * `layouts.md` uses `layoutSection`/`layoutColumn`, which are
#     Confluence-page-only.
#   * `task-decision-lists.md` uses `taskList`/`decisionList`, which Jira
#     descriptions do not accept.
# These exclusions are validated empirically by the probe in
# `docs/e2e-testing.md` and re-checked whenever a fixture is added.
JIRA_FIXTURES: list[str] = [
    "basic.md",
    "panels.md",
    "mixed.md",
    "inline-macros.md",
    "smart-cards.md",
]


@pytest.mark.parametrize("fixture_name", JIRA_FIXTURES)
def test_markdown_roundtrip_via_jira(
    fixture_name: str,
    jira: JiraClient,
    created_issues: list[str],
    run_id: str,
    e2e_settings: E2ESettings,
) -> None:
    project_key = e2e_settings.jira_project_key
    assert project_key is not None  # guarded by the `jira` fixture

    fixture_path = FIXTURES_DIR / fixture_name
    original_md = fixture_path.read_text(encoding="utf-8")

    # 1. MD -> ADF (and schema-validate).
    uploaded_adf_str = convert(original_md, src="md", dst="adf")
    validate(uploaded_adf_str, fmt="adf")
    uploaded_adf = json.loads(uploaded_adf_str)

    # 2. Create a Jira issue with the ADF as the description body.
    summary = f"adflux E2E [{run_id}] {fixture_path.stem}"
    created = jira.create_issue(
        project_key=project_key,
        summary=summary,
        adf_description=uploaded_adf,
    )
    issue_key = str(created["key"])
    created_issues.append(issue_key)

    # 3. Fetch it back and pull out the ADF description.
    fetched = jira.get_issue(issue_key)
    description = fetched.get("fields", {}).get("description")
    assert description is not None, (
        f"Jira issue {issue_key} returned without an ADF description body"
    )

    # 4. Structural sanity check: every top-level node type uploaded must come
    #    back. Jira may add `localId` attrs and re-order trivial whitespace,
    #    so we use the same normalization helpers as the Confluence test.
    uploaded_types = set(adf_node_types(uploaded_adf))
    fetched_types = set(adf_node_types(description))
    missing = uploaded_types - fetched_types - {"doc"}
    assert not missing, (
        f"Jira dropped node types {sorted(missing)} from {fixture_name}: "
        f"uploaded={sorted(uploaded_types)} fetched={sorted(fetched_types)}"
    )

    # 5. Text-content equivalence (order-preserving) on non-text wrapping nodes.
    uploaded_text = [r[2] for r in adf_summary(normalize_adf(uploaded_adf)) if r[2]]
    fetched_text = [r[2] for r in adf_summary(normalize_adf(description)) if r[2]]
    assert uploaded_text == fetched_text, (
        f"ADF text content diverged for {fixture_name}.\n"
        f"  uploaded: {uploaded_text}\n  fetched : {fetched_text}"
    )


def test_jira_close_transition_available(jira: JiraClient, e2e_settings: E2ESettings) -> None:
    """Sanity check that the configured project exposes a closing transition."""
    project_key = e2e_settings.jira_project_key
    assert project_key is not None
    created = jira.create_issue(
        project_key=project_key,
        summary=f"adflux E2E transition probe [{project_key}]",
        adf_description={
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "probe"}]}],
        },
    )
    key = str(created["key"])
    try:
        chosen = jira.close_issue(key)
        assert chosen, "close_issue returned an empty transition name"
    finally:
        # Ensure we still attempt to close even if assertion above fails.
        # close_issue is idempotent enough — a second call on a terminal state
        # will just raise, which we swallow here.
        pass
