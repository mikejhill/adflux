import pytest

from adflux.adf import validate, validation_issues
from adflux.errors import AdfValidationError


def doc(*content):
    return {"type": "doc", "version": 1, "content": list(content)}


def para(text="x"):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def test_valid(kitchen):
    assert validation_issues(doc(para())) == []
    for name, node in kitchen.items():
        assert validation_issues(doc(node) if node["type"] != "doc" else node) == [], name


@pytest.mark.parametrize(
    ("document", "fragment"),
    [
        (doc({"type": "nope"}), "nope"),
        (doc({"type": "bulletList", "content": [para()]}), "paragraph"),
        (doc({"type": "heading", "content": [{"type": "text", "text": "x"}]}), "level"),
        (doc({"type": "heading", "attrs": {"level": 9}, "content": []}), "level"),
        (doc({"type": "panel", "attrs": {"panelType": "rainbow"}, "content": [para()]}), "panelType"),
        (doc({"type": "paragraph", "content": [{"type": "text", "text": "x", "marks": [{"type": "blink"}]}]}), "blink"),
        (doc({"type": "paragraph", "content": [{"type": "text", "text": ""}]}), "text"),
    ],
)
def test_invalid(document, fragment):
    issues = validation_issues(document)
    assert issues, document
    assert any(fragment in f"{i.path} {i.message}" for i in issues), issues
    with pytest.raises(AdfValidationError):
        validate(document)
