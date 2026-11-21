"""ADF -> Markdown.

Each node is written in the most idiomatic form that loses nothing:

1. plain Markdown when the node and its attributes fit (``**bold**``, lists, GFM tables,
   ``> [!NOTE]`` alerts, ``- [ ]`` tasks, ``<url>`` smart links, ``:smile:``);
2. a short directive (``:status[DONE]{color=green}``, ``::toc{maxLevel=3}``,
   ``:::expand{title="More"}``);
3. the generic directive named after the node type, with every attribute
   (``:::paragraph{align=center}``, ``:::table{layout=wide}`` with ``:::row``/``:::cell``);
4. a raw ADF block (```` ```adf ```` with the node's JSON) or ``:adf{json=...}`` inline,
   for anything else (unknown node types, card data, parameters that are not macro
   parameters).

The reader understands every form, so ``read(write(doc))`` reproduces the document up to
:func:`adflux.adf.normalize.canonical` (generated ``localId`` values and server metadata).
"""

from __future__ import annotations

import copy
import functools
import json
import re
from collections.abc import Iterable
from typing import Any

from adflux.adf.model import Mark, Node
from adflux.adf.normalize import MARK_ORDER, expel_whitespace, normalize
from adflux.adf.spec import NODES, node_spec
from adflux.markdown import names
from adflux.markdown.attrs import format_attrs
from adflux.markdown.syntax import NAME
from adflux.profiles.profile import Profile

_NAME_RE = re.compile(rf"^{NAME}$")
_AUTOLINK_SAFE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*$")
_LINE_START = re.compile(
    r"^(\s*)(#{1,6}(?:\s|$)|>|[-+*](?:\s|$)|\d{1,9}[.)](?:\s|$)|=+\s*$|-+\s*$|`{3,}|~{3,}|:{2,}|\|)"
)
_ENTITY = re.compile(r"&(#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
_COLON_WORD = re.compile(r":(?=([A-Za-z0-9_+\-]+)(:|[\[{]))")
_TRAILING_NAME = re.compile(rf"(?<!\\)((?:\\\\)*)(:{NAME})$")
_INLINE_SPECIAL = re.compile(r"([\\`*_\[\]<>~])")
_HTML_LIKE = re.compile(r"<(?=[A-Za-z/!?])")

DEFAULT_TABLE_ATTRS: dict[str, Any] = {"isNumberColumnEnabled": False, "layout": "default"}
BLOCK_MARKS = ("alignment", "indentation", "breakout")
_LIST_FAMILY = {"bulletList": "bullet", "taskList": "bullet", "orderedList": "ordered"}
_DELIMITED = {"strong": "**", "em": "*", "strike": "~~"}
_HTML_TAG = {"strong": "strong", "em": "em", "strike": "del"}


def _colons(lines: list[str]) -> int:
    longest = 2
    for line in lines:
        stripped = line.lstrip(" >")
        run = len(stripped) - len(stripped.lstrip(":"))
        longest = max(longest, run)
    return max(3, longest + 1)


def _indent(lines: list[str], first: str, rest: str) -> list[str]:
    out: list[str] = []
    for i, line in enumerate(lines):
        prefix = first if i == 0 else rest
        out.append(prefix + line if line else (prefix.rstrip() if i == 0 else ""))
    return out


class Writer:
    """Write one ADF document as Markdown."""

    def __init__(self, profile: Profile, *, keep_metadata: bool = False) -> None:
        self.profile = profile
        self.keep_metadata = keep_metadata
        self._reader: Any = None
        self._alternate = False

    def write(self, doc: Node) -> str:
        """Return Markdown for ``doc``."""
        doc = expel_whitespace(normalize(copy.deepcopy(doc)))
        lines = self._blocks(doc.children, "doc")
        text = "\n".join(lines).rstrip("\n")
        return text + "\n" if text else ""

    # -- blocks -----------------------------------------------------------------------
    def _blocks(self, nodes: list[Node], parent: str) -> list[str]:
        out: list[str] = []
        previous: str | None = None
        alternate = False
        for node in nodes:
            family = _LIST_FAMILY.get(node.type)
            # Adjacent lists of one family must switch marker or Markdown merges them.
            alternate = family is not None and family == previous and not alternate
            previous = family
            self._alternate = alternate
            lines = self._block(node, parent)
            if out and lines:
                out.append("")
            out.extend(lines)
        return out

    def _block(self, node: Node, parent: str) -> list[str]:
        method = getattr(self, f"_b_{node.type}", None)
        if method is not None:
            result = method(node, parent)
            if result is not None:
                return result
        return self._generic_block(node, parent)

    def _directive(self, name: str, attrs: dict[str, Any], body: list[str], label: str | None = None) -> list[str]:
        colons = ":" * _colons(body)
        head = colons + name + (f"[{label}]" if label is not None else "") + format_attrs(self._strs(attrs))
        return [head, *body, colons]

    def _leaf(self, name: str, attrs: dict[str, Any], label: str | None = None) -> list[str]:
        return ["::" + name + (f"[{label}]" if label is not None else "") + format_attrs(self._strs(attrs))]

    @staticmethod
    def _strs(attrs: dict[str, Any]) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, value in attrs.items():
            if isinstance(value, bool):
                out[key] = "true" if value else "false"
            elif isinstance(value, int | float):
                out[key] = str(int(value)) if float(value).is_integer() else repr(value)
            elif isinstance(value, str):
                out[key] = value
            else:
                out[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return out

    def _raw_block(self, node: Node) -> list[str]:
        body = json.dumps(node.to_json(), ensure_ascii=False, indent=2).split("\n")
        fence = "`" * max(3, 1 + max((len(m) for m in re.findall(r"`+", "\n".join(body))), default=0))
        return [fence + "adf", *body, fence]

    def _attrs(self, node: Node, skip: Iterable[str] = ()) -> dict[str, Any]:
        skipped = set(skip) | {"localId"}
        return {k: v for k, v in node.attrs.items() if k not in skipped}

    def _mark_attrs(self, node: Node) -> dict[str, Any] | None:
        """Return directive attributes for block marks, or None if one cannot be expressed."""
        out: dict[str, Any] = {}
        raw: list[dict[str, Any]] = []
        for mark in node.marks:
            if mark.type == "alignment" and set(mark.attrs) == {"align"}:
                out["align"] = mark.attrs["align"]
            elif mark.type == "indentation" and set(mark.attrs) == {"level"}:
                out["indent"] = mark.attrs["level"]
            elif mark.type == "breakout" and set(mark.attrs) <= {"mode", "width"} and "mode" in mark.attrs:
                out["breakout"] = mark.attrs["mode"]
                if "width" in mark.attrs:
                    out["breakoutWidth"] = mark.attrs["width"]
            else:
                raw.append(mark.to_json())
        if raw:
            out["marks"] = raw
        return out

    def _generic_block(self, node: Node, parent: str) -> list[str]:
        spec = NODES.get(node.type)
        if (
            spec is None
            or spec.inline
            or not _NAME_RE.match(node.type)
            or node.text is not None
            or node.extra
            or node.type == "extension"  # ::extension is the macro form
        ):
            return self._raw_block(node)
        attrs = {**self._attrs(node), **(self._mark_attrs(node) or {})}
        if spec.leaf:
            return self._leaf(node.type, attrs)
        children = node.children
        if children and all(NODES.get(c.type) is not None and NODES[c.type].inline for c in children):
            return self._directive(node.type, attrs, [self._inline(children, node.type)])
        if not children and spec.content and all(NODES.get(c) is None or NODES[c].inline for c in spec.content):
            return self._directive(node.type, attrs, [])
        return self._directive(node.type, attrs, self._blocks(children, node.type))

    def _b_paragraph(self, node: Node, parent: str) -> list[str] | None:
        if node.marks or self._attrs(node) or not node.children:
            return None
        return self._inline(node.children, "paragraph").split("\n")

    def _b_heading(self, node: Node, parent: str) -> list[str] | None:
        if node.marks or self._attrs(node, ("level",)):
            return None
        text = self._inline(node.children, "heading")
        if "\n" in text:
            return None
        level = int(node.attrs.get("level", 1))
        closing = re.search(r"(^|[ \t])(#+)$", text)
        if closing:  # a trailing run of # would read as the closing sequence
            text = text[: closing.start(2)] + "\\" + text[closing.start(2) :]
        return [("#" * level + " " + text).rstrip()]

    def _b_rule(self, node: Node, parent: str) -> list[str] | None:
        return None if self._attrs(node) or node.marks else ["---"]

    def _b_blockquote(self, node: Node, parent: str) -> list[str] | None:
        if self._attrs(node) or node.marks:
            return None
        body = self._blocks(node.children, "blockquote")
        if body and body[0].startswith("[!"):
            body[0] = "\\" + body[0]
        return [("> " + line) if line else ">" for line in body] or [">"]

    def _b_panel(self, node: Node, parent: str) -> list[str] | None:
        attrs = self._attrs(node)
        panel_type = attrs.get("panelType")
        body = self._blocks(node.children, "panel")
        if set(attrs) == {"panelType"} and panel_type in names.PANEL_TO_ALERT and not node.marks:
            lines = [f"[!{names.PANEL_TO_ALERT[panel_type]}]", *body]
            return [("> " + line) if line else ">" for line in lines]
        friendly = names.unrename(attrs, names.PANEL_ATTRS)
        return self._directive("panel", {**friendly, **(self._mark_attrs(node) or {})}, body)

    def _b_expand(self, node: Node, parent: str) -> list[str] | None:
        if node.marks:
            return None
        attrs = self._attrs(node)
        if attrs.get("title") == "":
            attrs.pop("title")
        return self._directive("expand", attrs, self._blocks(node.children, node.type))

    _b_nestedExpand = _b_expand  # noqa: N815 - matches the ADF node name

    def _b_codeBlock(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        if node.marks:
            return None
        attrs = self._attrs(node)
        language = attrs.pop("language", None) or ""
        if not re.fullmatch(r"[^\s`{]*", language) or language == "adf":  # ```adf is raw ADF
            return None
        body = node.text_content()
        runs = [len(m) for m in re.findall(r"`{3,}", body)]
        fence = "`" * max(3, 1 + max(runs, default=0))
        info = language + ((" " + format_attrs(self._strs(attrs))) if attrs else "")
        if not language and attrs:
            return None
        lines = body.split("\n") if body else []
        return [fence + info, *lines, fence]

    def _list_item_lines(self, item: Node, marker: str, tight: bool) -> list[str] | None:
        if item.type != "listItem" or self._attrs(item) or item.marks:
            return None
        if tight:
            body = [line for child in item.children for line in self._block(child, "listItem")]
        else:
            body = self._blocks(item.children, "listItem")
        if not body:
            body = [""]
        # A list item starting like a task marker would be read as a task.
        if item.children and item.children[0].type == "paragraph" and re.match(r"^\[[ xX]\](\s|$)", body[0]):
            body[0] = "\\" + body[0]
        return _indent(body, marker, " " * len(marker))

    def _tight(self, items: list[Node]) -> bool:
        for item in items:
            paragraphs = [c for c in item.children if c.type == "paragraph"]
            others = [c for c in item.children if c.type not in ("paragraph", "bulletList", "orderedList", "taskList")]
            if len(paragraphs) > 1 or others:
                return False
            if item.children and item.children[0].type != "paragraph":
                return False
            for before, after in zip(item.children, item.children[1:], strict=False):
                # only a list starting at 1 may interrupt a paragraph
                if before.type == "paragraph" and after.type == "orderedList" and int(after.attrs.get("order", 1)) != 1:
                    return False
        return True

    def _join_items(self, rendered: list[list[str]], tight: bool) -> list[str]:
        out: list[str] = []
        for lines in rendered:
            if out and not tight:
                out.append("")
            out.extend(lines)
        return out

    def _b_bulletList(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        if self._attrs(node) or node.marks:
            return None
        marker = "* " if self._alternate else "- "
        tight = self._tight(node.children)
        rendered = []
        for item in node.children:
            lines = self._list_item_lines(item, marker, tight)
            if lines is None:
                return None
            rendered.append(lines)
        return self._join_items(rendered, tight)

    def _b_orderedList(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        attrs = self._attrs(node, ("order",))
        if attrs or node.marks:
            return None
        start = int(node.attrs.get("order", 1))
        if start < 0 or start + max(len(node.children) - 1, 0) > 999_999_999:
            return None  # CommonMark list markers have at most nine digits
        delimiter = ")" if self._alternate else "."
        tight = self._tight(node.children)
        rendered = []
        for i, item in enumerate(node.children):
            lines = self._list_item_lines(item, f"{start + i}{delimiter} ", tight)
            if lines is None:
                return None
            rendered.append(lines)
        return self._join_items(rendered, tight)

    def _task_lines(self, node: Node, item_type: str, bullet: str = "-") -> list[str] | None:
        states = ("TODO", "DONE") if item_type == "taskItem" else ("UNDECIDED", "DECIDED")
        lines: list[str] = []
        previous_item = False
        for child in node.children:
            if child.type in (item_type, "blockTaskItem") and (child.type == item_type or item_type == "taskItem"):
                if set(self._attrs(child)) - {"state"} or child.marks:
                    return None
                state = child.attrs.get("state")
                if state not in states:
                    return None  # only two states fit a checkbox
                marker = f"{bullet} [{'x' if state == states[1] else ' '}] "
                if child.type == "blockTaskItem":
                    body = self._block_task_body(child)
                    if body is None:
                        return None
                else:
                    text = self._inline(child.children, item_type)
                    if child.content == [] or (not text and child.content):
                        return None  # empty content array or content that renders as nothing
                    body = text.split("\n") if text else [""]
                lines.extend(_indent(body, marker, "  "))
                previous_item = True
            elif child.type == node.type and previous_item and item_type == "taskItem":
                nested = self._task_lines(child, item_type)
                if nested is None:
                    return None
                lines.extend("  " + line if line else "" for line in nested)
            else:
                return None
        return lines

    def _block_task_body(self, item: Node) -> list[str] | None:
        """Lines for a block task item: two or more plain paragraphs (one reads as a task item)."""
        paragraphs = item.children
        if len(paragraphs) < 2 or any(
            p.type != "paragraph" or p.attrs or p.marks or not p.children for p in paragraphs
        ):
            return None
        body: list[str] = []
        for paragraph in paragraphs:
            if body:
                body.append("")
            body.extend(self._inline(paragraph.children, "paragraph").split("\n"))
        return body

    def _b_taskList(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        if node.marks or set(self._attrs(node)):
            return None
        return self._task_lines(node, "taskItem", "*" if self._alternate else "-")

    def _b_decisionList(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        if node.marks or set(self._attrs(node)):
            return None
        lines = self._task_lines(node, "decisionItem")
        return None if lines is None else self._directive("decisions", {}, lines)

    def _b_layoutSection(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        attrs = {**self._attrs(node), **(self._mark_attrs(node) or {})}
        body: list[str] = []
        for column in node.children:
            if column.type != "layoutColumn" or column.marks:
                return None
            if body:
                body.append("")
            body.extend(self._directive("column", self._attrs(column), self._blocks(column.children, "layoutColumn")))
        return self._directive("layout", attrs, body)

    def _b_mediaSingle(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        media = [c for c in node.children if c.type == "media"]
        captions = [c for c in node.children if c.type == "caption"]
        others = [c for c in node.children if c.type not in ("media", "caption")]
        if len(media) != 1 or others or len(captions) > 1 or node.marks or media[0].marks:
            return None
        if captions and (self._attrs(captions[0]) or captions[0].marks):
            return None
        single = self._attrs(node)
        item = self._attrs(media[0])
        caption = self._inline(captions[0].children, "caption") if captions else None
        if (
            set(single) == {"layout"}
            and single["layout"] == "center"
            and item.get("type") == "external"
            and set(item) <= {"type", "url", "alt"}
            and caption is None
            and "url" in item
            and not re.search(r"[\s()<>]", str(item["url"]))
            and _url_kept(str(item["url"]))
        ):
            alt = _escape_inline(str(item.get("alt", "")), table=False)
            return [f"![{alt}]({item['url']})"]
        attrs: dict[str, Any] = {}
        if single.get("layout") != "center":
            attrs["layout"] = single.get("layout")
        for key, value in single.items():
            if key != "layout":
                attrs[f"single.{key}"] = value
        for key, value in item.items():
            if key == "type" and ((value == "external" and "url" in item) or (value == "file" and "url" not in item)):
                continue
            attrs[key] = value
        if caption is not None and "\n" in caption:
            return None
        return self._leaf("media", attrs, caption)

    def _b_blockCard(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        attrs = self._attrs(node)
        if "url" not in attrs or node.marks:
            return None
        return self._leaf("card", attrs)

    def _b_embedCard(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        attrs = self._attrs(node)
        if "url" not in attrs or node.marks:
            return None
        return self._leaf("embed", attrs)

    def _b_table(self, node: Node, parent: str) -> list[str] | None:
        simple = self._gfm_table(node)
        if simple is not None:
            return simple
        attrs = {k: v for k, v in self._attrs(node).items() if DEFAULT_TABLE_ATTRS.get(k, object()) != v}
        attrs.update(self._mark_attrs(node) or {})
        body: list[str] = []
        for row in node.children:
            if row.type != "tableRow" or row.marks:
                return self._generic_block(node, parent)
            cells: list[str] = []
            for cell in row.children:
                if cells:
                    cells.append("")
                name = "header" if cell.type == "tableHeader" else "cell"
                cell_attrs = {
                    k: v for k, v in self._attrs(cell).items() if not (k in ("colspan", "rowspan") and v == 1)
                }
                cells.extend(self._directive(name, cell_attrs, self._blocks(cell.children, cell.type)))
            if body:
                body.append("")
            body.extend(self._directive("row", self._attrs(row), cells))
        return self._directive("table", attrs, body)

    def _gfm_table(self, node: Node) -> list[str] | None:
        attrs = self._attrs(node)
        if node.marks or any(DEFAULT_TABLE_ATTRS.get(k, object()) != v for k, v in attrs.items()):
            return None
        rows = node.children
        if not rows or any(r.type != "tableRow" or r.attrs or r.marks for r in rows):
            return None
        width = len(rows[0].children)
        if width == 0 or any(len(r.children) != width for r in rows):
            return None
        if any(c.type != "tableHeader" for c in rows[0].children):
            return None
        if any(c.type != "tableCell" for r in rows[1:] for c in r.children):
            return None
        aligns: list[str | None] = [None] * width
        grid: list[list[str]] = []
        for r_index, row in enumerate(rows):
            cells: list[str] = []
            for c_index, cell in enumerate(row.children):
                cell_attrs = {
                    k: v for k, v in self._attrs(cell).items() if not (k in ("colspan", "rowspan") and v == 1)
                }
                if cell_attrs or cell.marks:
                    return None
                if len(cell.children) != 1 or cell.children[0].type != "paragraph":
                    return None
                paragraph = cell.children[0]
                if self._attrs(paragraph):
                    return None
                align = None
                for mark in paragraph.marks:
                    if mark.type == "alignment" and set(mark.attrs) == {"align"}:
                        align = mark.attrs["align"]
                    else:
                        return None
                if r_index == 0:
                    aligns[c_index] = align
                elif aligns[c_index] != align:
                    return None
                text = self._inline(paragraph.children, "paragraph", table=True)
                if "\n" in text:
                    return None
                # GFM splits rows on unescaped pipes before inline parsing, everywhere
                cells.append(text.replace("|", "\\|"))
            grid.append(cells)

        def row_line(cells: list[str]) -> str:
            return "| " + " | ".join(cells) + " |"

        sep = []
        for align in aligns:
            sep.append({None: "---", "center": ":---:", "end": "---:"}[align])
        return [row_line(grid[0]), "| " + " | ".join(sep) + " |", *(row_line(r) for r in grid[1:])]

    # -- extensions (macros) ----------------------------------------------------------
    def _extension_parts(self, node: Node) -> tuple[str, dict[str, Any], str | None] | None:
        """Return (directive name, attributes, label) for an extension node."""
        attrs = dict(node.attrs)
        key = attrs.pop("extensionKey", None)
        ext_type = attrs.pop("extensionType", None)
        if not isinstance(key, str) or not isinstance(ext_type, str):
            return None
        out: dict[str, Any] = {}
        parameters = attrs.pop("parameters", None)
        label: str | None = None
        macro = self.profile.macros.get(key) if ext_type == self.profile.macros.extension_type else None
        params = parameters.get("macroParams") if isinstance(parameters, dict) else None
        simple = (
            isinstance(parameters, dict)
            and isinstance(params, dict)
            and set(parameters) <= {"macroParams", "macroMetadata"}
            and all(
                isinstance(v, dict) and set(v) == {"value"} and isinstance(v["value"], str) for v in params.values()
            )
        )
        if parameters is None:
            out["adf.params"] = "null"  # no parameters at all (the reader would add macroParams)
        elif not simple:
            out["adf.params"] = json.dumps(parameters, ensure_ascii=False, separators=(",", ":"))
        elif params:
            label_name = names.label_param(macro)
            for name, value in params.items():
                text = value["value"]
                if name == "__bodyContent":
                    out["adf.body"] = text
                elif name == label_name and label is None and "\n" not in text and _label_safe(text):
                    label = text
                elif _NAME_RE.match(name) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]*", name):
                    out[name] = text
                else:
                    return None
        if simple and self.keep_metadata and isinstance(parameters, dict) and "macroMetadata" in parameters:
            out["adf.meta"] = parameters["macroMetadata"]
        for name in ("layout", "localId", "text"):
            if name in attrs:
                out[f"adf.{name}"] = attrs.pop(name)
        if attrs:
            return None
        short = (
            ext_type == (self.profile.macros.extension_type or "")
            and _NAME_RE.match(key)
            and key not in names.RESERVED
            and key not in NODES
            and "." not in key
        )
        if short and (key in self.profile.macros or self.profile.unknown_directives_are_macros):
            return key, out, label
        generic = {"adf.key": key}
        if ext_type != self.profile.macros.extension_type:
            generic["adf.type"] = ext_type
        if label is not None:
            out = {names.label_param(macro): label, **out} if names.label_param(macro) else out
            if not names.label_param(macro):
                label_value = label
                return "extension", {**generic, **out}, label_value
        return "extension", {**generic, **out}, None

    def _b_extension(self, node: Node, parent: str) -> list[str] | None:
        if node.marks:
            return self._raw_block(node)
        parts = self._extension_parts(node)
        if parts is None:
            return None
        name, attrs, label = parts
        return self._leaf(name, attrs, None if label is None else _escape_label(label))

    def _b_bodiedExtension(self, node: Node, parent: str) -> list[str] | None:  # noqa: N802
        if node.marks:
            return self._raw_block(node)
        parts = self._extension_parts(node)
        if parts is None:
            return None
        name, attrs, label = parts
        return self._directive(
            name, attrs, self._blocks(node.children, "bodiedExtension"), None if label is None else _escape_label(label)
        )

    # -- inline -----------------------------------------------------------------------
    def _inline(self, nodes: list[Node], parent: str, *, table: bool = False) -> str:
        """Render inline content.

        Falls back to HTML emphasis tags when the delimiter form would not parse back
        (CommonMark flanking rules around punctuation).
        """
        text = self._render_inline(nodes, parent, table=table, html=False)
        if not any(m.type in _DELIMITED for n in nodes for m in n.marks):
            return text
        if self._reads_back(text, nodes, parent):
            return text
        return self._render_inline(nodes, parent, table=table, html=True)

    def _reads_back(self, text: str, nodes: list[Node], parent: str) -> bool:
        from adflux.adf.normalize import canonical
        from adflux.markdown.reader import Reader

        if self._reader is None:
            self._reader = Reader(self.profile)
        try:
            back = self._reader.inline(text, parent)
        except Exception:
            return False
        want = canonical(Node("paragraph", content=list(nodes)))
        got = canonical(Node("paragraph", content=back))
        return want == got

    def _render_inline(self, nodes: list[Node], parent: str, *, table: bool, html: bool) -> str:
        parts: list[str] = []
        active: list[Mark] = []
        previous: Node | None = None
        for node in nodes:
            marks = [m for m in node.marks if m.type != "code"]
            # close marks that end here (and everything opened after them)
            keep = 0
            while keep < len(active) and keep < len(marks) and active[keep].key() == marks[keep].key():
                keep += 1
            for mark in reversed(active[keep:]):
                parts.append(self._close(mark, html))
            active = active[:keep]
            text = self._inline_node(node, parent, table)
            if text.startswith("{") and previous is not None and previous.type != "text":
                text = "\\" + text  # would read as the attributes of the directive before it
            previous = node
            if node.type == "hardBreak" and node is nodes[-1]:
                text = ":hardBreak{}"  # a trailing backslash break would not parse
            for mark in marks[keep:]:
                opener = self._open(mark, html)
                if opener == "[" and parts and _ends_with_bang(parts[-1]):
                    parts[-1] = parts[-1][:-1] + "\\!"  # "![" would start an image
                parts.append(opener)
                active.append(mark)
            parts.append(text)
        for mark in reversed(active):
            parts.append(self._close(mark, html))
        # text ending in "!" right before a link would turn the link into an image
        return _fix_line_starts("".join(parts))

    @staticmethod
    def _open(mark: Mark, html: bool = False) -> str:
        if mark.type in _DELIMITED:
            return f"<{_HTML_TAG[mark.type]}>" if html else _DELIMITED[mark.type]
        if mark.type == "underline":
            return "<u>"
        if mark.type == "subsup":
            return "<sub>" if mark.attrs.get("type") == "sub" else "<sup>"
        if mark.type == "link" and _simple_link(mark):
            return "["
        return ":span["

    def _close(self, mark: Mark, html: bool = False) -> str:
        if mark.type in _DELIMITED:
            return f"</{_HTML_TAG[mark.type]}>" if html else _DELIMITED[mark.type]
        if mark.type == "underline":
            return "</u>"
        if mark.type == "subsup":
            return "</sub>" if mark.attrs.get("type") == "sub" else "</sup>"
        if mark.type == "link" and _simple_link(mark):
            href = str(mark.attrs.get("href", ""))
            target = href if not re.search(r"[\s()<>]", href) and href else "<" + href.replace(">", "%3E") + ">"
            title = mark.attrs.get("title")
            if title:
                escaped = str(title).replace("\\", "\\\\").replace('"', '\\"')
                return f']({target} "{escaped}")'
            return f"]({target})"
        attrs: dict[str, Any] = {}
        if mark.type == "textColor" and set(mark.attrs) == {"color"}:
            attrs["color"] = mark.attrs["color"]
        elif mark.type == "backgroundColor" and set(mark.attrs) == {"color"}:
            attrs["background"] = mark.attrs["color"]
        elif mark.type == "fontSize" and set(mark.attrs) == {"fontSize"}:
            attrs["size"] = mark.attrs["fontSize"]
        else:
            attrs["marks"] = [mark.to_json()]
        return "]" + format_attrs(self._strs(attrs))

    def _inline_node(self, node: Node, parent: str, table: bool) -> str:
        kind = node.type
        if kind == "text":
            value = node.text or ""
            if node.has_mark("code"):
                if "\n" in value or "\r" in value:  # a code span would turn the newline into a space
                    return (
                        ":span["
                        + _escape_inline(value, table=table)
                        + "]"
                        + format_attrs({"marks": '[{"type":"code"}]'})
                    )
                return _code_span(value, table)
            # ":name" right before a link or span would read as an inline directive
            return _TRAILING_NAME.sub(r"\1\\\2", _escape_inline(value, table=table))
        if kind == "hardBreak":
            return "<br>" if table else "\\\n"
        if kind == "emoji":
            code = (
                self.profile.emoji_code(node.attrs)
                if set(node.attrs) - {"localId"} <= {"shortName", "id", "text"}
                else None
            )
            wanted = {k: v for k, v in node.attrs.items() if k != "localId"}
            if code is not None and self.profile.resolve_emoji(code) != wanted:
                code = None  # :code: would fill in or change attributes
            if code is not None:
                return f":{code}:"
            return ":emoji" + (format_attrs(self._strs(self._attrs(node))) or "{}")
        if kind == "status":
            attrs = self._attrs(node)
            label = str(attrs.pop("text", ""))
            return ":status[" + _escape_label(label) + "]" + format_attrs(self._strs(attrs))
        if kind == "date":
            attrs = self._attrs(node)
            date = names.timestamp_to_date(str(attrs.get("timestamp", "")))
            if date and set(attrs) == {"timestamp"}:
                return f":date[{date}]"
            return ":date" + (format_attrs(self._strs(attrs)) or "{}")
        if kind == "mention":
            attrs = self._attrs(node)
            if attrs.get("accessLevel") == "":
                attrs.pop("accessLevel")
            shown = attrs.get("text")
            if isinstance(shown, str) and shown.startswith("@") and not shown.startswith("@@"):
                attrs.pop("text")
                return ":mention[" + _escape_label(shown[1:]) + "]" + format_attrs(self._strs(attrs))
            return ":mention" + (format_attrs(self._strs(attrs)) or "{}")
        if kind == "inlineCard":
            attrs = self._attrs(node)
            url = attrs.get("url")
            if (
                set(attrs) == {"url"}
                and isinstance(url, str)
                and _AUTOLINK_SAFE.match(url)
                and _url_kept(url)
                and not url.lower().startswith("mailto:")
            ):
                return f"<{url}>"
            if set(attrs) == {"url"} and isinstance(url, str):
                return ":card" + format_attrs(self._strs(attrs))
            return self._raw_inline(node)
        if kind == "inlineExtension":
            parts = self._extension_parts(node)
            if parts is None:
                return self._raw_inline(node)
            name, attrs, label = parts
            return (
                ":"
                + name
                + ("[" + _escape_label(label) + "]" if label is not None else "")
                + (format_attrs(self._strs(attrs)) or ("{}" if label is None else ""))
            )
        spec = NODES.get(kind)
        if (
            spec is not None
            and spec.inline
            and _NAME_RE.match(kind)
            and not node.extra
            and kind not in names.INLINE_ALIASES
        ):
            attrs = self._attrs(node)
            inner = ""
            if node.children:
                inner = "[" + self._inline(node.children, kind, table=table) + "]"
            return ":" + kind + inner + (format_attrs(self._strs(attrs)) or ("{}" if not inner else ""))
        return self._raw_inline(node)

    def _raw_inline(self, node: Node) -> str:
        return ":adf" + format_attrs({"json": json.dumps(node.to_json(), ensure_ascii=False, separators=(",", ":"))})


def _ends_with_bang(text: str) -> bool:
    """Whether ``text`` ends with an unescaped ``!``."""
    if not text.endswith("!"):
        return False
    body = text[:-1]
    return (len(body) - len(body.rstrip("\\"))) % 2 == 0


def _simple_link(mark: Mark) -> bool:
    href = mark.attrs.get("href")
    return set(mark.attrs) <= {"href", "title"} and isinstance(href, str) and bool(href) and _url_kept(href)


@functools.cache
def _url_kept(url: str) -> bool:
    """Whether Markdown keeps ``url`` exactly (it percent-encodes spaces, non-ASCII...)."""
    from adflux.markdown.reader import _parser

    md = _parser()
    return bool(md.validateLink(url)) and md.normalizeLink(url) == url


def _label_safe(text: str) -> bool:
    return "\n" not in text


def _escape_label(text: str) -> str:
    return _escape_inline(text, table=False)


def _code_span(value: str, table: bool) -> str:
    runs = [len(m) for m in re.findall(r"`+", value)]
    ticks = "`" * (1 + max(runs, default=0))
    body = value
    if body.startswith("`") or body.endswith("`") or (body.startswith(" ") and body.endswith(" ") and body.strip()):
        body = f" {body} "
    return ticks + body + ticks


@functools.cache
def _is_shortcode(name: str) -> bool:
    """Whether ``:name:`` is an emoji in any profile (so it must be escaped as text)."""
    from adflux.profiles import CONFLUENCE, GENERIC, JIRA

    return any(p.resolve_emoji(name) is not None for p in (GENERIC, CONFLUENCE, JIRA))


def _escape_colon(match: re.Match[str]) -> str:
    if match.group(2) != ":" or _is_shortcode(match.group(1)):
        return "\\:"
    return ":"


def _escape_inline(value: str, *, table: bool) -> str:
    out = _INLINE_SPECIAL.sub(r"\\\1", value)
    out = _ENTITY.sub(lambda m: "&amp;" + m.group(0)[1:], out)
    out = _COLON_WORD.sub(_escape_colon, out)
    return out.replace("\n", "&#10;")


def _fix_line_starts(text: str) -> str:
    """Escape characters that would start block syntax at the beginning of a line."""
    lines = text.split("\n")
    fixed = []
    for i, line in enumerate(lines):
        if i == 0 or lines[i - 1].endswith("\\"):
            match = _LINE_START.match(line)
            if match:
                lead = match.group(1)
                rest = line[len(lead) :]
                if rest[:1].isdigit():
                    digits = re.match(r"\d+", rest)
                    assert digits
                    end = digits.end()
                    rest = rest[:end] + "\\" + rest[end:]
                else:
                    rest = "\\" + rest
                line = lead + rest
            stripped = line.lstrip(" ")
            if len(line) - len(stripped) and (i == 0 or lines[i - 1].endswith("\\")):
                spaces = len(line) - len(stripped)
                line = "&#32;" * spaces + stripped
        fixed.append(line)
    last = fixed[-1]
    stripped = last.rstrip(" ")
    if stripped != last:
        fixed[-1] = stripped + "&#32;" * (len(last) - len(stripped))
    return "\n".join(fixed)


def adf_to_markdown(doc: Node, profile: Profile, *, keep_metadata: bool = False) -> str:
    """Convert an ADF document to Markdown."""
    return Writer(profile, keep_metadata=keep_metadata).write(doc)


__all__ = ["MARK_ORDER", "Writer", "adf_to_markdown", "node_spec"]
