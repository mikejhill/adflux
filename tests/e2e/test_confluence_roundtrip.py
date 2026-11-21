"""Live Confluence round trip.

For each fixture: Markdown -> ADF, create a page, read it back, and require that

1. Confluence stored the document unchanged (up to :func:`adflux.canonical`), and
2. the stored ADF -> Markdown -> ADF reproduces it.

Pages are deleted at the end unless ``ADFLUX_E2E_KEEP_PAGES=true``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adflux import canonical, to_adf, to_markdown, validate
from tests.e2e.confluence_client import ConfluenceClient

pytestmark = pytest.mark.e2e

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.md"))


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.stem for f in FIXTURES])
def test_markdown_roundtrip_via_confluence(
    fixture: Path,
    confluence: ConfluenceClient,
    created_pages: list[str],
    e2e_parent_page_id: str,
    run_id: str,
) -> None:
    uploaded = to_adf(fixture.read_text(encoding="utf-8"), "confluence", strict=True)
    validate(uploaded)
    page = confluence.create_page(
        title=f"adflux E2E [{run_id}] {fixture.stem}", adf_value=json.dumps(uploaded), parent_id=e2e_parent_page_id
    )
    created_pages.append(str(page["id"]))
    stored = json.loads(confluence.get_page_adf(str(page["id"]))["body"]["atlas_doc_format"]["value"])

    assert canonical(stored) == canonical(uploaded)
    again = to_adf(to_markdown(stored, "confluence"), "confluence")
    assert canonical(again) == canonical(stored)
