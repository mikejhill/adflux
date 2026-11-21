"""Regressions for documents that once lost content or failed to convert."""

from __future__ import annotations

import json
from typing import Any

import pytest

from adflux import canonical, convert, to_adf, to_markdown, validation_issues
from adflux.cli import main
from adflux.errors import MarkdownError


def doc(*content: Any) -> dict[str, Any]:
    return {"type": "doc", "version": 1, "content": list(content)}


def para(*content: Any) -> dict[str, Any]:
    return {"type": "paragraph", "content": list(content)}


def text(value: str, *marks: dict[str, Any]) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": value}
    if marks:
        node["marks"] = list(marks)
    return node


def media(**attrs: Any) -> dict[str, Any]:
    return {"type": "media", "attrs": attrs}


ROUND_TRIPS: dict[str, tuple[dict[str, Any], str]] = {
    "pixel width image": (
        doc(
            {
                "type": "mediaSingle",
                "attrs": {"layout": "center", "width": 640, "widthType": "pixel"},
                "content": [media(type="external", url="https://x.example.com/a.png")],
            }
        ),
        "generic",
    ),
    "media group": (doc({"type": "mediaGroup", "content": [media(type="file", id="abc", collection="c")]}), "generic"),
    "block task item": (
        doc(
            {
                "type": "taskList",
                "attrs": {"localId": "l"},
                "content": [
                    {"type": "blockTaskItem", "attrs": {"localId": "i", "state": "TODO"}, "content": [para(text("a"))]}
                ],
            }
        ),
        "generic",
    ),
    "multi-paragraph task": (
        doc(
            {
                "type": "taskList",
                "attrs": {"localId": "l"},
                "content": [
                    {
                        "type": "blockTaskItem",
                        "attrs": {"localId": "i", "state": "DONE"},
                        "content": [para(text("a")), para(text("b"))],
                    }
                ],
            }
        ),
        "generic",
    ),
    "marked extension": (
        doc(
            {
                "type": "extension",
                "attrs": {"extensionKey": "k", "extensionType": "t"},
                "marks": [{"type": "fragment", "attrs": {"localId": "f", "name": "n"}}],
            }
        ),
        "generic",
    ),
    "extension without parameters": (
        doc({"type": "extension", "attrs": {"extensionKey": "k", "extensionType": "t"}}),
        "generic",
    ),
    "extension with string parameters": (
        doc({"type": "extension", "attrs": {"extensionKey": "k", "extensionType": "t", "parameters": "hello"}}),
        "generic",
    ),
    "code block in language adf": (
        doc({"type": "codeBlock", "attrs": {"language": "adf"}, "content": [text("hello")]}),
        "generic",
    ),
    "inline code with a newline": (doc(para(text("a\nb", {"type": "code"}))), "generic"),
    "heading ending in a hash": (
        doc({"type": "heading", "attrs": {"level": 2}, "content": [text("example #")]}),
        "generic",
    ),
    "link with a space": (
        doc(para(text("x", {"type": "link", "attrs": {"href": "https://a.example.com/a b"}}))),
        "generic",
    ),
    "linked inline media": (
        doc(
            para(
                {
                    "type": "mediaInline",
                    "attrs": {"id": "i", "collection": "c", "type": "file"},
                    "marks": [{"type": "link", "attrs": {"href": "https://a.example.com"}}],
                }
            )
        ),
        "generic",
    ),
    "image alt with brackets": (
        doc(
            {
                "type": "mediaSingle",
                "attrs": {"layout": "center"},
                "content": [media(type="external", url="https://x.example.com/a.png", alt="a [b]")],
            }
        ),
        "generic",
    ),
    "wide expand": (
        doc(
            {
                "type": "expand",
                "attrs": {"title": "T"},
                "marks": [{"type": "breakout", "attrs": {"mode": "wide"}}],
                "content": [para(text("a"))],
            }
        ),
        "generic",
    ),
    "mention with only an id": (doc(para({"type": "mention", "attrs": {"id": "u1"}})), "generic"),
    "mention text without @": (doc(para({"type": "mention", "attrs": {"id": "u1", "text": "Ada"}})), "generic"),
    "emoji with only a short name": (doc(para({"type": "emoji", "attrs": {"shortName": ":smile:"}})), "generic"),
    "empty task item": (
        doc(
            {
                "type": "taskList",
                "attrs": {"localId": "l"},
                "content": [{"type": "taskItem", "attrs": {"localId": "i", "state": "DONE"}}],
            }
        ),
        "generic",
    ),
    "custom decision state": (
        doc(
            {
                "type": "decisionList",
                "attrs": {"localId": "l"},
                "content": [
                    {"type": "decisionItem", "attrs": {"localId": "i", "state": "CUSTOM"}, "content": [text("a")]}
                ],
            }
        ),
        "generic",
    ),
    "ordered list past nine digits": (
        doc(
            {
                "type": "orderedList",
                "attrs": {"order": 1000000000},
                "content": [{"type": "listItem", "content": [para(text("x"))]}],
            }
        ),
        "generic",
    ),
    "backslash before a link": (
        doc(
            para(
                text("\\:A"),
                text("0", {"type": "strong"}, {"type": "link", "attrs": {"href": "https://a.example.com/A"}}),
            )
        ),
        "generic",
    ),
}


@pytest.mark.parametrize("name", sorted(ROUND_TRIPS))
def test_round_trip(name: str) -> None:
    document, profile = ROUND_TRIPS[name]
    assert not validation_issues(document), validation_issues(document)
    markdown = to_markdown(document, profile)
    assert canonical(to_adf(markdown, profile)) == canonical(document), markdown


def test_macro_metadata_without_parameters_is_kept() -> None:
    meta = {"macroId": {"value": "m1"}}
    document = doc(
        {
            "type": "extension",
            "attrs": {
                "extensionKey": "toc",
                "extensionType": "com.atlassian.confluence.macro.core",
                "parameters": {"macroParams": {}, "macroMetadata": meta},
            },
        }
    )
    back = to_adf(to_markdown(document, "confluence", keep_metadata=True), "confluence")
    assert back["content"][0]["attrs"]["parameters"]["macroMetadata"] == meta


def test_validation_checks_the_input_as_given() -> None:
    assert validation_issues({"type": "doc", "content": []})  # no version
    marks = doc({"type": "paragraph", "content": [text("a")], "marks": {}})
    assert validation_issues(marks)
    assert validation_issues(doc()) == []
    assert to_adf("") == doc()


def test_markdown_tasks_keep_continuation_paragraphs() -> None:
    item = to_adf("- [x] a\n\n  b\n")["content"][0]["content"][0]
    assert item["type"] == "blockTaskItem"
    assert [p["content"][0]["text"] for p in item["content"]] == ["a", "b"]


def test_decision_items_need_markers() -> None:
    for source in (":::decisions\n- \n:::\n", ":::decisions\n- text\n:::\n"):
        with pytest.raises(MarkdownError, match="marker"):
            to_adf(source)


def test_code_macro_body_inside_containers() -> None:
    quoted = to_adf("> :::code\n> x\n> :::\n")
    assert quoted["content"][0]["content"][0]["content"][0]["text"] == "x"
    spaced = to_adf(":::code\n  x\n    y\n:::\n")
    assert spaced["content"][0]["content"][0]["text"] == "  x\n    y"


def test_unknown_inline_directives_stay_intact() -> None:
    with pytest.warns(UserWarning):
        out = to_adf("a :wat[body]{key=value} b")
    assert out["content"][0]["content"][0]["text"] == "a :wat[body]{key=value} b"


def test_jira_checks_inline_nodes_too() -> None:
    with pytest.raises(MarkdownError, match="inlineExtension"):
        to_adf("a :extension{adf.key=foo} b", "jira", strict=True)


@pytest.mark.parametrize("source", [":date[bad]", ":span[x]{marks=oops}", "::panel{indent=x}"])
def test_bad_directive_values_are_markdown_errors(source: str) -> None:
    with pytest.raises(MarkdownError):
        to_adf(source)


def test_keep_local_ids_covers_tables() -> None:
    def table(local_id: str) -> dict[str, Any]:
        cell = {"type": "tableCell", "content": [para(text("x"))]}
        return doc(
            {"type": "table", "attrs": {"localId": local_id}, "content": [{"type": "tableRow", "content": [cell]}]}
        )

    assert canonical(table("a"), keep_local_ids=True) != canonical(table("b"), keep_local_ids=True)
    assert canonical(table("a")) == canonical(table("b"))


def test_convert_rejects_unknown_formats() -> None:
    with pytest.raises(ValueError, match="unsupported format"):
        convert("x", "markdown", "panflute")  # ty: ignore[invalid-argument-type]


def test_cli_validates_markdown_against_the_schema(tmp_path: Any, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "a.md"
    source.write_text("::media{type=file}\n", encoding="utf-8")
    assert main(["validate", str(source), "-f", "markdown"]) == 1
    assert main(["validate", str(source), "-f", "markdown", "--no-schema"]) == 0
    capsys.readouterr()


def test_nested_spans_parse_in_linear_time() -> None:
    source = ":span[" * 18 + "x" + "]{color=#ff0000}" * 18
    out = json.dumps(to_adf(source))
    assert '"x"' in out
