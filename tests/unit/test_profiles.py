from adflux.profiles import CONFLUENCE, GENERIC, JIRA, get_profile
from adflux.profiles.emoji import default_index
from adflux.profiles.macros import confluence_catalog


def test_emoji_lookup():
    index = default_index()
    smile = index.resolve("smile")
    assert smile is not None and smile.id == "1f604"
    check = index.resolve("atlassian-check_mark")
    assert check is not None
    assert index.resolve("definitely-not-an-emoji") is None
    assert any(e.short_name == "thumbsup" for e in index.search("thumbs"))


def test_profile_aliases():
    assert CONFLUENCE.resolve_emoji("tick")["id"] == "atlassian-check_mark"
    assert JIRA.resolve_emoji("tick")["id"] == "atlassian-check_mark"
    # a real short name always wins over an alias
    assert CONFLUENCE.resolve_emoji("smile")["shortName"] == ":smile:"
    assert GENERIC.emoji_code({"shortName": ":smile:", "id": "1f604", "text": "😄"}) == "smile"


def test_macro_catalog():
    catalog = confluence_catalog()
    toc = catalog.get("toc")
    assert toc is not None and toc.param("maxLevel") is not None
    assert catalog.get("info") is not None
    assert "toc" in catalog


def test_get_profile():
    assert get_profile("jira") is JIRA
    assert get_profile(None) is GENERIC
    assert get_profile(CONFLUENCE) is CONFLUENCE
