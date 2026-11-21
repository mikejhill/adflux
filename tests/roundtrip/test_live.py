"""Round trips over ADF captured from a live Jira and Confluence site."""

import pytest

from adflux import to_adf, to_markdown
from adflux.adf.model import load
from adflux.adf.normalize import canonical, expel_whitespace, normalize
from tests.conftest import live

PROBE = live("node-probe.json")
KITCHEN = live("kitchen.json")
CATALOG = live("confluence-macro-catalog.json")


def _doc(node):
    return node if node.get("type") == "doc" else {"type": "doc", "version": 1, "content": [node]}


def _canon(doc):
    return canonical(expel_whitespace(normalize(load(doc))))


def _roundtrip(doc, profile):
    markdown = to_markdown(doc, profile)
    back = to_adf(markdown, profile)
    assert _canon(back) == _canon(doc), markdown
    return markdown


@pytest.mark.parametrize("name", sorted(KITCHEN))
@pytest.mark.parametrize("profile", ["generic", "confluence"])
def test_kitchen_nodes(name, profile):
    _roundtrip(_doc(KITCHEN[name]), profile)


@pytest.mark.parametrize(("product", "name"), [(p, n) for p in ("jira", "conf") for n in sorted(PROBE[p])])
@pytest.mark.filterwarnings("ignore:jira does not render")
def test_server_returned_adf(product, name):
    """What the products returned after storing each probe node."""
    back = PROBE[product][name].get("back")
    if not back:
        pytest.skip("no ADF captured")
    doc = {"type": "doc", "version": 1, "content": back} if isinstance(back, list) else _doc(back)
    _roundtrip(doc, "jira" if product == "jira" else "confluence")


def test_jira_wiki_conversion():
    data = live("jira-wiki.json")
    markdown = _roundtrip(data["adf"], "jira")
    assert "## Head" in markdown


MACROS = [m for m in CATALOG if isinstance(m.get("adf_block"), list) and m["adf_block"]]


@pytest.mark.parametrize("macro", MACROS, ids=[m["name"] for m in MACROS])
def test_every_confluence_macro(macro):
    doc = {"type": "doc", "version": 1, "content": macro["adf_block"]}
    _roundtrip(doc, "confluence")
