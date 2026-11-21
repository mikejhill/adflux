"""ADF -> Markdown: the idiomatic form is chosen whenever it loses nothing."""

import pytest

from adflux import to_adf, to_markdown


def doc(*content):
    return {"type": "doc", "version": 1, "content": list(content)}


def para(*inline):
    return {"type": "paragraph", "content": list(inline)}


def t(text, *marks):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = [m if isinstance(m, dict) else {"type": m} for m in marks]
    return node


@pytest.mark.parametrize(
    ("node", "markdown"),
    [
        (para(t("a "), t("b", "strong"), t(" "), t("c", "em")), "a **b** *c*"),
        (para(t("x", {"type": "link", "attrs": {"href": "https://a.example"}})), "[x](https://a.example)"),
        (para({"type": "inlineCard", "attrs": {"url": "https://a.example"}}), "<https://a.example>"),
        (para({"type": "status", "attrs": {"text": "DONE", "color": "green"}}), ":status[DONE]{color=green}"),
        (para({"type": "emoji", "attrs": {"shortName": ":smile:", "id": "1f604", "text": "😄"}}), ":smile:"),
        (para({"type": "date", "attrs": {"timestamp": "1704153600000"}}), ":date[2024-01-02]"),
        (para(t("1. not a list")), "1\\. not a list"),
        (para(t("# not a heading")), "\\# not a heading"),
        (para(t("*star* and 10:30:00 :smile:")), "\\*star\\* and 10:30:00 \\:smile:"),
        ({"type": "panel", "attrs": {"panelType": "warning"}, "content": [para(t("w"))]}, "> [!WARNING]\n> w"),
        ({"type": "expand", "attrs": {"title": "More"}, "content": [para(t("x"))]}, ":::expand{title=More}\nx\n:::"),
        ({"type": "rule"}, "---"),
    ],
)
def test_idiomatic(node, markdown):
    assert to_markdown(doc(node)).strip() == markdown


def test_flanking_falls_back_to_html():
    source = doc(para(t("a"), t("b", "strong", "strike")))
    markdown = to_markdown(source).strip()
    assert markdown == "a<del><strong>b</strong></del>" or "<strong>" in markdown
    assert to_adf(markdown)["content"] == source["content"]


def test_whitespace_moves_outside_emphasis():
    markdown = to_markdown(doc(para(t("bold ", "strong"), t("x")))).strip()
    assert markdown == "**bold** x"


def test_tight_lists_and_tasks():
    source = doc(
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [para(t("a"))]},
                {"type": "listItem", "content": [para(t("b"))]},
            ],
        },
        {
            "type": "taskList",
            "attrs": {"localId": "l"},
            "content": [
                {"type": "taskItem", "attrs": {"localId": "a", "state": "TODO"}, "content": [t("t1")]},
                {
                    "type": "taskList",
                    "attrs": {"localId": "m"},
                    "content": [{"type": "taskItem", "attrs": {"localId": "b", "state": "DONE"}, "content": [t("n")]}],
                },
            ],
        },
    )
    assert to_markdown(source) == "- a\n- b\n\n* [ ] t1\n  - [x] n\n"


def test_unknown_node_uses_raw_adf():
    markdown = to_markdown(doc({"type": "futureBlock", "attrs": {"x": 1}}))
    assert markdown.startswith("```adf\n")
    assert to_adf(markdown, check=False)["content"] == [{"type": "futureBlock", "attrs": {"x": 1}}]


def test_macro_short_form_in_confluence():
    ext = {
        "type": "extension",
        "attrs": {
            "extensionType": "com.atlassian.confluence.macro.core",
            "extensionKey": "toc",
            "parameters": {"macroParams": {"maxLevel": {"value": "3"}}, "macroMetadata": {"macroId": {"value": "x"}}},
        },
    }
    assert to_markdown(doc(ext), "confluence").strip() == "::toc{maxLevel=3}"
    kept = to_markdown(doc(ext), "confluence", keep_metadata=True)
    assert "adf.meta" in kept


def test_input_not_mutated():
    source = doc(para(t("bold ", "strong")))
    before = repr(source)
    to_markdown(source)
    assert repr(source) == before
