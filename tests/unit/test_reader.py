"""Markdown -> ADF for each construct of the dialect."""

import pytest

from adflux import ConversionWarning, MarkdownError, to_adf
from adflux.adf.normalize import canonical


def blocks(markdown, profile="generic", **kw):
    return canonical(to_adf(markdown, profile, **kw))["content"]


def inline(markdown, profile="generic"):
    return blocks(markdown, profile)[0]["content"]


def t(text, *marks):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = [m if isinstance(m, dict) else {"type": m} for m in marks]
    return node


def test_paragraph_and_marks():
    assert inline("a **b** *c* ~~d~~ `e` <u>f</u> <sub>g</sub> <sup>h</sup>") == [
        t("a "),
        t("b", "strong"),
        t(" "),
        t("c", "em"),
        t(" "),
        t("d", "strike"),
        t(" "),
        t("e", "code"),
        t(" "),
        t("f", "underline"),
        t(" "),
        t("g", {"type": "subsup", "attrs": {"type": "sub"}}),
        t(" "),
        t("h", {"type": "subsup", "attrs": {"type": "sup"}}),
    ]


def test_links_and_cards():
    assert inline("[x](https://a.example)") == [t("x", {"type": "link", "attrs": {"href": "https://a.example"}})]
    assert inline("<https://a.example>") == [{"type": "inlineCard", "attrs": {"url": "https://a.example"}}]
    assert blocks("::card{url=https://a.example}") == [{"type": "blockCard", "attrs": {"url": "https://a.example"}}]


def test_headings_rules_quotes_code():
    out = blocks("# H1\n\n---\n\n> q\n\n```python\nx = 1\n```")
    assert out[0] == {"type": "heading", "attrs": {"level": 1}, "content": [t("H1")]}
    assert out[1] == {"type": "rule"}
    assert out[2] == {"type": "blockquote", "content": [{"type": "paragraph", "content": [t("q")]}]}
    assert out[3] == {"type": "codeBlock", "attrs": {"language": "python"}, "content": [t("x = 1")]}


def test_lists_and_tasks():
    out = blocks("1. a\n2. b\n\n- [ ] t1\n  - [x] nested")
    assert out[0]["type"] == "orderedList" and len(out[0]["content"]) == 2
    tasks = out[1]
    assert tasks["type"] == "taskList"
    assert tasks["content"][0] == {"type": "taskItem", "attrs": {"state": "TODO"}, "content": [t("t1")]}
    assert tasks["content"][1]["type"] == "taskList"
    assert tasks["content"][1]["content"][0]["attrs"] == {"state": "DONE"}
    raw = to_adf("- [ ] t")["content"][0]
    assert raw["attrs"]["localId"] and raw["content"][0]["attrs"]["localId"]


@pytest.mark.parametrize(
    ("alert", "panel"),
    [
        ("NOTE", "note"),
        ("TIP", "tip"),
        ("WARNING", "warning"),
        ("CAUTION", "error"),
        ("INFO", "info"),
        ("ERROR", "error"),
        ("SUCCESS", "success"),
    ],
)
def test_alerts(alert, panel):
    out = blocks(f"> [!{alert}]\n> body")
    assert out == [
        {"type": "panel", "attrs": {"panelType": panel}, "content": [{"type": "paragraph", "content": [t("body")]}]}
    ]


def test_containers():
    out = blocks(':::expand{title="More"}\ninside\n:::\n\n:::panel{type=custom color=#ff0000}\np\n:::')
    assert out[0] == {
        "type": "expand",
        "attrs": {"title": "More"},
        "content": [{"type": "paragraph", "content": [t("inside")]}],
    }
    assert out[1]["attrs"] == {"panelType": "custom", "panelColor": "#ff0000"}


def test_nested_expand_and_layout():
    out = blocks(":::::layout\n::::column{width=50}\na\n::::\n::::column\n:::expand{title=x}\nb\n:::\n::::\n:::::")
    section = out[0]
    assert section["type"] == "layoutSection"
    assert [c["attrs"]["width"] for c in section["content"]] == [50, 50]
    assert section["content"][1]["content"][0]["type"] == "expand"
    assert blocks("::::expand\n:::expand\nx\n:::\n::::")[0]["content"][0]["type"] == "nestedExpand"
    with pytest.raises(MarkdownError, match="more colons"):
        to_adf("::::layout\n:::column\n:::expand\nb\n:::\n:::\n::::")


def test_gfm_table():
    out = blocks("| a | b |\n|:--|--:|\n| 1 | 2 |")
    table = out[0]
    assert table["type"] == "table"
    assert table["content"][0]["content"][0]["type"] == "tableHeader"
    cell = table["content"][1]["content"][1]["content"][0]
    assert cell["marks"] == [{"type": "alignment", "attrs": {"align": "end"}}]


def test_inline_nodes():
    out = inline(":status[DONE]{color=green} :date[2024-01-02] :mention[@Ada]{id=abc} :smile:")
    assert out[0] == {"type": "status", "attrs": {"text": "DONE", "color": "green"}}
    assert out[2] == {"type": "date", "attrs": {"timestamp": "1704153600000"}}
    assert out[4] == {"type": "mention", "attrs": {"id": "abc", "text": "@Ada"}}
    assert out[6]["type"] == "emoji" and out[6]["attrs"]["shortName"] == ":smile:"


def test_unknown_emoji_stays_text():
    assert inline("time 10:30:00 :notanemoji:") == [t("time 10:30:00 :notanemoji:")]


def test_span_marks():
    assert inline(":span[x]{color=#ff0000 background=#00ff00}") == [
        t(
            "x",
            {"type": "textColor", "attrs": {"color": "#ff0000"}},
            {"type": "backgroundColor", "attrs": {"color": "#00ff00"}},
        )
    ]


def test_block_marks():
    out = blocks(":::paragraph{align=center}\nx\n:::")
    assert out[0]["marks"] == [{"type": "alignment", "attrs": {"align": "center"}}]


def test_confluence_macros():
    out = blocks("::toc{maxLevel=3}\n\n:::excerpt\nbody\n:::\n\nsee :jira[SAM1-6]", "confluence")
    assert out[0]["type"] == "extension"
    assert out[0]["attrs"]["extensionKey"] == "toc"
    assert out[0]["attrs"]["parameters"]["macroParams"]["maxLevel"] == {"value": "3"}
    assert out[1]["type"] == "bodiedExtension" and out[1]["attrs"]["extensionKey"] == "excerpt"
    jira = out[2]["content"][1]
    assert jira["type"] == "inlineExtension" and jira["attrs"]["extensionKey"] == "jira"


def test_unknown_directive_is_macro_only_in_confluence():
    assert blocks("::recently-updated{max=5}", "confluence")[0]["type"] == "extension"
    assert blocks("::not-a-macro{max=5}", "confluence")[0]["attrs"]["extensionKey"] == "not-a-macro"
    with pytest.raises(MarkdownError):
        to_adf("::not-a-macro{max=5}", "jira")


def test_jira_warns_for_confluence_only_nodes():
    with pytest.warns(ConversionWarning):
        to_adf("::::layout\n:::column\nx\n:::\n:::column\ny\n:::\n::::", "jira")


def test_raw_adf_fallback():
    out = blocks('```adf\n{"type":"rule"}\n```\n\nx :adf{json="{\\"type\\":\\"hardBreak\\"}"}')
    assert out[0] == {"type": "rule"}
    assert out[1]["content"][1] == {"type": "hardBreak"}


def test_image_becomes_external_media():
    out = blocks("![alt](https://a.example/i.png)")
    assert out[0]["type"] == "mediaSingle"
    media = out[0]["content"][0]
    assert media["attrs"]["type"] == "external" and media["attrs"]["url"] == "https://a.example/i.png"


def test_bad_attrs_raise_with_line():
    with pytest.raises(MarkdownError) as info:
        to_adf("ok\n\n::toc{maxLevel=", "confluence")
    assert "line" in str(info.value)
