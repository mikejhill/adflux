"""Live Confluence round-trip tests.

Each fixture under `tests/e2e/fixtures/*.md` is:

1. Loaded as Markdown.
2. Converted MD → ADF via adflux (strict-adf profile).
3. POSTed as a new Confluence page using `atlas_doc_format`.
4. Re-fetched from Confluence.
5. Compared structurally (node-type sequence + key text) to the upload.
6. Converted back ADF → MD via adflux.
7. Compared to the original Markdown by alphanumeric word bag.

Pages are deleted in the fixture teardown unless `ADFLUX_E2E_KEEP_PAGES=true`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tests.e2e.compare import (
    adf_node_types,
    adf_summary,
    assert_word_bag_equal,
    normalize_adf,
)
from tests.e2e.confluence_client import ConfluenceClient

from adflux import convert, validate

pytestmark = pytest.mark.e2e

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES = sorted(FIXTURES_DIR.glob("*.md"))


# Per-fixture expectations: (always-required ADF node types,
# tokens to ignore when comparing the round-tripped Markdown).
EXPECTATIONS: dict[str, dict[str, object]] = {
    "basic.md": {
        "required_types": [
            "doc",
            "heading",
            "paragraph",
            "bulletList",
            "orderedList",
            "listItem",
            "codeBlock",
            "table",
            "tableRow",
            "tableHeader",
            "tableCell",
            "blockquote",
            "rule",
        ],
        "ignore_tokens": [],
    },
    "panels.md": {
        "required_types": ["doc", "heading", "panel", "paragraph", "bulletList", "codeBlock"],
        "ignore_tokens": [
            "adf",
            "paneltype",
            "info",
            "note",
            "warning",
            "success",
            "error",
            # Confluence normalizes code-block languages (bash <-> shell, etc.).
            "bash",
            "shell",
            "sh",
        ],
    },
    "mixed.md": {
        "required_types": ["doc", "heading", "panel", "expand", "status", "codeBlock"],
        "ignore_tokens": [
            "adf",
            "paneltype",
            "info",
            "expand",
            "title",
            "status",
            "text",
            "color",
            "yellow",
            "green",
            # Code-block language aliases — Confluence may normalize.
            "javascript",
            "js",
            "sql",
            "yaml",
            "yml",
        ],
    },
    "inline-macros.md": {
        "required_types": [
            "doc",
            "heading",
            "paragraph",
            "status",
            "date",
            "emoji",
            "inlineCard",
        ],
        "ignore_tokens": [
            "adf",
            "status",
            "text",
            "color",
            "timestamp",
            "green",
            "blue",
            "yellow",
            "red",
            "neutral",
            "purple",
            "date",
            "emoji",
            "shortname",
            "rocket",
            "thumbsup",
            "tada",
            "inlinecard",
            "url",
            # The inlineCard URL gets stripped to its host preview by Confluence.
            "https",
            "github",
            "com",
            "mikejhill",
            "adflux",
            "releases",
            "developer",
            "atlassian",
            "cloud",
            "jira",
            "platform",
            "apis",
            "document",
            "structure",
        ],
    },
    "task-decision-lists.md": {
        "required_types": [
            "doc",
            "heading",
            "paragraph",
            "taskList",
            "taskItem",
            "decisionList",
            "decisionItem",
        ],
        "ignore_tokens": [
            "adf",
            "tasklist",
            "taskitem",
            "decisionlist",
            "decisionitem",
            "state",
            "todo",
            "done",
            "decided",
        ],
    },
    "layouts.md": {
        "required_types": [
            "doc",
            "heading",
            "paragraph",
            "layoutSection",
            "layoutColumn",
            "bulletList",
            "listItem",
            "codeBlock",
        ],
        "ignore_tokens": [
            "adf",
            "layoutsection",
            "layoutcolumn",
            "width",
            # Confluence rounds layoutColumn widths.
            "50",
            "33",
            "33.33",
            # Code-block language aliases.
            "python",
        ],
    },
    "smart-cards.md": {
        "required_types": [
            "doc",
            "heading",
            "paragraph",
            "inlineCard",
            "blockCard",
            "embedCard",
        ],
        "ignore_tokens": [
            "adf",
            "inlinecard",
            "blockcard",
            "embedcard",
            "url",
            "layout",
            "width",
            "center",
            # URLs become tokenized when normalized to a word bag.
            "https",
            "github",
            "com",
            "mikejhill",
            "adflux",
            "issues",
            "www",
            "youtube",
            "watch",
            "v",
            "dqw4w9wgxcq",
            "100",
        ],
    },
}

# `extension` / `bodiedExtension` / `inlineExtension` ADF nodes are tied to
# Confluence "macros" provided by Forge or Connect apps, so the public REST
# API rejects arbitrary extensionKey/extensionType pairs (HTTP 500). adflux
# round-trips them correctly through its own pipeline — see
# `examples/extensions.md` for a demonstration — but a live Confluence Cloud
# tenant cannot ingest them without the corresponding installed app.


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda p: p.name)
def test_markdown_roundtrip_via_confluence(
    fixture_path: Path,
    confluence: ConfluenceClient,
    created_pages: list[str],
    e2e_parent_page_id: str,
    run_id: str,
) -> None:
    fixture_name = fixture_path.name
    expect = EXPECTATIONS.get(fixture_name, {"required_types": ["doc"], "ignore_tokens": []})
    required_types: list[str] = expect["required_types"]  # type: ignore[assignment]
    ignore_tokens: list[str] = expect["ignore_tokens"]  # type: ignore[assignment]

    # 1. Load Markdown.
    original_md = fixture_path.read_text(encoding="utf-8")

    # 2. MD -> ADF (and validate against the schema).
    uploaded_adf_str = convert(original_md, src="md", dst="adf")
    validate(uploaded_adf_str, fmt="adf")
    uploaded_adf = json.loads(uploaded_adf_str)

    uploaded_types = set(adf_node_types(uploaded_adf))
    missing_pre = [t for t in required_types if t not in uploaded_types]
    assert not missing_pre, (
        f"adflux MD->ADF dropped required node types {missing_pre} for {fixture_name}: "
        f"got {sorted(uploaded_types)}"
    )

    # 3. POST to Confluence (nested under the per-run parent page).
    title = f"adflux E2E [{run_id}] {fixture_path.stem}"
    page = confluence.create_page(
        title=title,
        adf_value=uploaded_adf_str,
        parent_id=e2e_parent_page_id,
    )
    page_id = str(page["id"])
    created_pages.append(page_id)

    # 4. GET it back.
    fetched = confluence.get_page_adf(page_id)
    body = fetched.get("body", {}).get("atlas_doc_format", {})
    fetched_value = body.get("value")
    assert fetched_value, f"page {page_id} returned without atlas_doc_format body"
    fetched_adf = json.loads(fetched_value)

    # 5. Structural comparison: every required type must survive the round trip.
    fetched_types = set(adf_node_types(fetched_adf))
    missing_post = [t for t in required_types if t not in fetched_types]
    assert not missing_post, (
        f"Confluence dropped node types {missing_post} after ingest of {fixture_name}: "
        f"got {sorted(fetched_types)}"
    )

    # And: the *order and text* of meaningful nodes match (after normalization).
    uploaded_summary = [r for r in adf_summary(normalize_adf(uploaded_adf)) if r[1] != "?"]
    fetched_summary = [r for r in adf_summary(normalize_adf(fetched_adf)) if r[1] != "?"]
    uploaded_text = [r[2] for r in uploaded_summary if r[2]]
    fetched_text = [r[2] for r in fetched_summary if r[2]]
    assert uploaded_text == fetched_text, (
        f"ADF text content diverged for {fixture_name}.\n"
        f"  uploaded: {uploaded_text}\n  fetched : {fetched_text}"
    )

    # 6. ADF -> MD.
    roundtripped_md = convert(json.dumps(fetched_adf), src="adf", dst="md")

    # 7. Word-bag equivalence (allow per-fixture ignores).
    assert_word_bag_equal(original_md, roundtripped_md, ignore=ignore_tokens)


def test_environment_loaded(e2e_settings) -> None:
    """Sanity check: settings have been loaded from .env."""
    assert e2e_settings.site
    assert e2e_settings.email
    assert e2e_settings.api_token.startswith("ATATT") or len(e2e_settings.api_token) >= 20
    assert e2e_settings.space_key or e2e_settings.space_id


def test_keep_pages_flag_respected(e2e_settings) -> None:
    """Document the opt-in keep flag; not a behavior test."""
    assert e2e_settings.keep_pages == (
        os.environ.get("ADFLUX_E2E_KEEP_PAGES", "").strip().lower() in {"1", "true", "yes"}
    )
