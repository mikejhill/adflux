"""Hypothesis strategies that build schema-valid ADF documents from the generated spec."""

from __future__ import annotations

import string

from hypothesis import strategies as st

TEXT_ALPHABET = string.ascii_letters + string.digits + " .,;:!?*_`~[](){}<>#|\\-+=&'\"/@^$%" + "éü😀"

plain_text = st.text(alphabet=TEXT_ALPHABET, min_size=1, max_size=12)
word = st.text(alphabet=string.ascii_letters, min_size=1, max_size=8)
url = st.builds(lambda a, b: f"https://{a.lower()}.example.com/{b}", word, word)
color = st.sampled_from(["#ff5630", "#36b37e", "#0052cc"])

SIMPLE_MARKS = ["strong", "em", "strike", "underline"]


@st.composite
def marks(draw):
    chosen = draw(
        st.lists(
            st.sampled_from([*SIMPLE_MARKS, "link", "sub", "sup", "textColor", "backgroundColor"]),
            unique=True,
            max_size=3,
        )
    )
    out = []
    has_sub = False
    for name in chosen:
        if name == "link":
            out.append({"type": "link", "attrs": {"href": draw(url)}})
        elif name in ("sub", "sup"):
            if has_sub:
                continue
            has_sub = True
            out.append({"type": "subsup", "attrs": {"type": name}})
        elif name in ("textColor", "backgroundColor"):
            out.append({"type": name, "attrs": {"color": draw(color)}})
        else:
            out.append({"type": name})
    return out


@st.composite
def text_node(draw, allow_marks=True):
    node = {"type": "text", "text": draw(plain_text)}
    if allow_marks and draw(st.booleans()):
        if draw(st.integers(0, 4)) == 0:
            node["marks"] = [{"type": "code"}]
        else:
            m = draw(marks())
            if m:
                node["marks"] = m
    return node


@st.composite
def inline_atom(draw):
    kind = draw(st.sampled_from(["emoji", "mention", "status", "date", "inlineCard", "hardBreak"]))
    if kind == "emoji":
        return {
            "type": "emoji",
            "attrs": draw(
                st.sampled_from(
                    [
                        {"shortName": ":grinning:", "id": "1f600", "text": "😀"},
                        {"shortName": ":check_mark:", "id": "atlassian-check_mark", "text": ":check_mark:"},
                        {"shortName": ":warning:", "id": "atlassian-warning", "text": ":warning:"},
                    ]
                )
            ),
        }
    if kind == "mention":
        return {"type": "mention", "attrs": {"id": "557058:" + draw(word), "text": "@" + draw(word)}}
    if kind == "status":
        return {
            "type": "status",
            "attrs": {
                "text": draw(plain_text).strip() or "X",
                "color": draw(st.sampled_from(["neutral", "green", "red"])),
            },
        }
    if kind == "date":
        return {"type": "date", "attrs": {"timestamp": str(draw(st.integers(0, 20000)) * 86_400_000)}}
    if kind == "inlineCard":
        return {"type": "inlineCard", "attrs": {"url": draw(url)}}
    return {"type": "hardBreak"}


@st.composite
def inline_content(draw, min_size=1):
    return draw(st.lists(st.one_of(text_node(), text_node(), inline_atom()), min_size=min_size, max_size=6))


def paragraph(min_size=1):
    return st.builds(lambda c: {"type": "paragraph", "content": c}, inline_content(min_size))


@st.composite
def block(draw, depth=0):
    choices = ["paragraph", "heading", "codeBlock", "rule"]
    if depth < 2:
        choices += ["bulletList", "orderedList", "blockquote", "panel", "taskList", "table", "expand"]
    kind = draw(st.sampled_from(choices))
    if kind == "paragraph":
        return draw(paragraph())
    if kind == "heading":
        return {"type": "heading", "attrs": {"level": draw(st.integers(1, 6))}, "content": draw(inline_content())}
    if kind == "codeBlock":
        node = {
            "type": "codeBlock",
            "content": [
                {"type": "text", "text": draw(st.text(alphabet=TEXT_ALPHABET + "\n", min_size=1, max_size=30))}
            ],
        }
        if draw(st.booleans()):
            node["attrs"] = {"language": draw(st.sampled_from(["python", "java", "c++"]))}
        return node
    if kind == "rule":
        return {"type": "rule"}
    if kind in ("bulletList", "orderedList"):
        items = []
        for _ in range(draw(st.integers(1, 3))):
            content = [draw(paragraph())]
            if depth < 1 and draw(st.booleans()):
                content.append(
                    draw(
                        block(depth + 1).filter(
                            lambda b: b["type"] in ("bulletList", "orderedList", "codeBlock", "paragraph")
                        )
                    )
                )
            items.append({"type": "listItem", "content": content})
        node = {"type": kind, "content": items}
        if kind == "orderedList" and draw(st.booleans()):
            node["attrs"] = {"order": draw(st.integers(1, 20))}
        return node
    if kind == "blockquote":
        return {"type": "blockquote", "content": [draw(paragraph())]}
    if kind == "panel":
        return {
            "type": "panel",
            "attrs": {"panelType": draw(st.sampled_from(["info", "note", "tip", "warning", "error", "success"]))},
            "content": [draw(paragraph())],
        }
    if kind == "expand":
        return {"type": "expand", "attrs": {"title": draw(plain_text)}, "content": [draw(paragraph())]}
    if kind == "taskList":
        items = [
            {
                "type": "taskItem",
                "attrs": {"localId": f"t{i}", "state": draw(st.sampled_from(["TODO", "DONE"]))},
                "content": draw(inline_content()),
            }
            for i in range(draw(st.integers(1, 3)))
        ]
        return {"type": "taskList", "attrs": {"localId": "tl"}, "content": items}
    # table
    width = draw(st.integers(1, 3))
    header = draw(st.booleans())
    rows = []
    for r in range(draw(st.integers(1, 3))):
        cells = []
        for _ in range(width):
            cell_type = "tableHeader" if header and r == 0 else "tableCell"
            cells.append({"type": cell_type, "content": [draw(paragraph(min_size=0))]})
        rows.append({"type": "tableRow", "content": cells})
    return {"type": "table", "content": rows}


documents = st.builds(
    lambda blocks: {"type": "doc", "version": 1, "content": blocks}, st.lists(block(), min_size=1, max_size=4)
)
