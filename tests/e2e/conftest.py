"""Shared fixtures for the E2E suite.

Provides:

* `e2e_settings` — typed view of the `.env` configuration.
* `confluence` — authenticated `ConfluenceClient` ready for use.
* `e2e_parent_page_id` — id of a per-run Confluence parent page; all created
  pages are nested underneath it for easy manual cleanup when
  `ADFLUX_E2E_KEEP_PAGES=true`.
* `created_pages` — pytest auto-deletes children at session end (when not
  keeping pages); the parent itself is also deleted afterwards.
* `jira` — authenticated `JiraClient` (skipped if
  `ADFLUX_E2E_JIRA_PROJECT_KEY` is missing). Jira issues are *closed*,
  never deleted.
* `created_issues` — list of Jira issue keys that get transitioned to
  Done/Closed at session teardown.

If credentials are absent or do not authenticate, every test in this
package is skipped with a helpful message.

All environment variables consumed here use the `ADFLUX_E2E_` prefix so
they cannot collide with unrelated tooling that also reaches into the
shell environment for Atlassian credentials.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from dotenv import load_dotenv
from tests.e2e.confluence_client import ConfluenceAuthError, ConfluenceClient
from tests.e2e.jira_client import JiraAuthError, JiraClient

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Stable parent-page label so re-runs nest under one place.
PARENT_PAGE_TITLE_BASE = "adflux E2E (automated)"


@dataclass(frozen=True)
class E2ESettings:
    site: str
    email: str
    api_token: str
    space_key: str | None
    space_id: str | None
    keep_pages: bool
    parent_page_id: str | None
    jira_project_key: str | None


def _load_settings() -> E2ESettings | None:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)

    site = os.environ.get("ADFLUX_E2E_ATLASSIAN_SITE", "").strip()
    email = os.environ.get("ADFLUX_E2E_ATLASSIAN_EMAIL", "").strip()
    token = os.environ.get("ADFLUX_E2E_ATLASSIAN_API_TOKEN", "").strip()
    space_key = os.environ.get("ADFLUX_E2E_CONFLUENCE_SPACE_KEY", "").strip() or None
    space_id = os.environ.get("ADFLUX_E2E_CONFLUENCE_SPACE_ID", "").strip() or None
    parent_id = os.environ.get("ADFLUX_E2E_CONFLUENCE_PARENT_PAGE_ID", "").strip() or None
    jira_project = os.environ.get("ADFLUX_E2E_JIRA_PROJECT_KEY", "").strip() or None
    keep = os.environ.get("ADFLUX_E2E_KEEP_PAGES", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    if not (site and email and token and (space_key or space_id)):
        return None
    return E2ESettings(
        site=site,
        email=email,
        api_token=token,
        space_key=space_key,
        space_id=space_id,
        keep_pages=keep,
        parent_page_id=parent_id,
        jira_project_key=jira_project,
    )


@pytest.fixture(scope="session")
def e2e_settings() -> E2ESettings:
    settings = _load_settings()
    if settings is None:
        pytest.skip(
            "E2E settings missing — copy .env.example to .env at the project "
            "root and fill in ADFLUX_E2E_ATLASSIAN_SITE, "
            "ADFLUX_E2E_ATLASSIAN_EMAIL, ADFLUX_E2E_ATLASSIAN_API_TOKEN, and "
            "ADFLUX_E2E_CONFLUENCE_SPACE_KEY (or _SPACE_ID). Alternatively, "
            "set the same variables in the process environment (e.g. via "
            "GitHub Actions secrets in CI).",
            allow_module_level=False,
        )
    return settings


@pytest.fixture(scope="session")
def run_id() -> str:
    """Stable per-session identifier injected into page/issue titles."""
    return f"{int(time.time())}-{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="session")
def confluence(e2e_settings: E2ESettings) -> Iterator[ConfluenceClient]:
    client = ConfluenceClient(
        site=e2e_settings.site,
        email=e2e_settings.email,
        api_token=e2e_settings.api_token,
    )
    try:
        client.verify_auth()
    except ConfluenceAuthError as exc:
        pytest.skip(f"Confluence credentials did not authenticate: {exc}")
    if e2e_settings.space_id is None:
        assert e2e_settings.space_key is not None
        try:
            resolved = client.resolve_space_id(e2e_settings.space_key)
        except Exception as exc:
            pytest.skip(f"Could not resolve space '{e2e_settings.space_key}': {exc}")
        client.default_space_id = resolved
    else:
        client.default_space_id = e2e_settings.space_id
    yield client
    client.close()


def _parent_placeholder_adf(run_label: str) -> str:
    """Minimal ADF body for the ephemeral parent page."""
    doc = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Container for adflux E2E test artifacts (run {run_label}). "
                            "Safe to delete."
                        ),
                    }
                ],
            }
        ],
    }
    return json.dumps(doc)


@pytest.fixture(scope="session")
def e2e_parent_page_id(
    confluence: ConfluenceClient,
    e2e_settings: E2ESettings,
    run_id: str,
) -> Iterator[str]:
    """Yield a Confluence page id used as the parent of every created page.

    If ``ADFLUX_E2E_CONFLUENCE_PARENT_PAGE_ID`` is set, that page is reused
    as the parent and never deleted. Otherwise a per-run parent page is
    created and (unless ``ADFLUX_E2E_KEEP_PAGES=true``) deleted at session
    end.
    """
    if e2e_settings.parent_page_id:
        yield e2e_settings.parent_page_id
        return

    parent_title = f"{PARENT_PAGE_TITLE_BASE} [{run_id}]"
    parent = confluence.create_page(
        title=parent_title,
        adf_value=_parent_placeholder_adf(run_id),
    )
    parent_id = str(parent["id"])
    try:
        yield parent_id
    finally:
        if not e2e_settings.keep_pages:
            with contextlib.suppress(Exception):
                confluence.delete_page(parent_id)


@pytest.fixture
def created_pages(confluence: ConfluenceClient, e2e_settings: E2ESettings) -> Iterator[list[str]]:
    pages: list[str] = []
    yield pages
    if e2e_settings.keep_pages:
        return
    for page_id in pages:
        with contextlib.suppress(Exception):
            confluence.delete_page(page_id)


# --------------------------------------------------------------------- jira


@pytest.fixture(scope="session")
def jira(e2e_settings: E2ESettings) -> Iterator[JiraClient]:
    if not e2e_settings.jira_project_key:
        pytest.skip(
            "Jira tests skipped — set ADFLUX_E2E_JIRA_PROJECT_KEY in .env "
            "(or as a workflow secret on the e2e environment) to enable."
        )
    client = JiraClient(
        site=e2e_settings.site,
        email=e2e_settings.email,
        api_token=e2e_settings.api_token,
    )
    try:
        client.verify_auth()
    except JiraAuthError as exc:
        pytest.skip(f"Jira credentials did not authenticate: {exc}")
    yield client
    client.close()


@pytest.fixture
def created_issues(jira: JiraClient) -> Iterator[list[str]]:
    """Track issue keys created during a test; close (do NOT delete) at teardown."""
    issues: list[str] = []
    yield issues
    for key in issues:
        with contextlib.suppress(Exception):
            jira.close_issue(key)
