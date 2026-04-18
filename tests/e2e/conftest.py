"""Shared fixtures for the E2E suite.

Provides:

* `e2e_settings` — typed view of the `.env` configuration.
* `confluence` — authenticated `ConfluenceClient` ready for use.
* `created_pages` — list pytest auto-cleans by deleting at session end.

If credentials are absent or do not authenticate, every test in this
package is skipped with a helpful message.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from dotenv import load_dotenv
from tests.e2e.confluence_client import ConfluenceAuthError, ConfluenceClient

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class E2ESettings:
    site: str
    email: str
    api_token: str
    space_key: str | None
    space_id: str | None
    keep_pages: bool


def _load_settings() -> E2ESettings | None:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)

    site = os.environ.get("CONFLUENCE_SITE", "").strip()
    email = os.environ.get("CONFLUENCE_EMAIL", "").strip()
    token = os.environ.get("CONFLUENCE_API_TOKEN", "").strip()
    space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "").strip() or None
    space_id = os.environ.get("CONFLUENCE_SPACE_ID", "").strip() or None
    keep = os.environ.get("ADFLUX_E2E_KEEP_PAGES", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    if not (site and email and token and (space_key or space_id)):
        return None
    return E2ESettings(site, email, token, space_key, space_id, keep)


@pytest.fixture(scope="session")
def e2e_settings() -> E2ESettings:
    settings = _load_settings()
    if settings is None:
        pytest.skip(
            "E2E settings missing — copy .env.example to .env at the project "
            "root and fill in CONFLUENCE_SITE, CONFLUENCE_EMAIL, "
            "CONFLUENCE_API_TOKEN, and CONFLUENCE_SPACE_KEY (or _ID). "
            "Alternatively, set the same variables in the process environment "
            "(e.g. via GitHub Actions secrets in CI).",
            allow_module_level=False,
        )
    return settings


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


@pytest.fixture
def created_pages(confluence: ConfluenceClient, e2e_settings: E2ESettings) -> Iterator[list[str]]:
    pages: list[str] = []
    yield pages
    if e2e_settings.keep_pages:
        return
    for page_id in pages:
        with contextlib.suppress(Exception):
            confluence.delete_page(page_id)
