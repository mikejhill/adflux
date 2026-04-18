"""panflute Doc -> ADF JSON writer.

The writer is the inverse of :mod:`adflux.formats.adf.reader`. Block and
inline handling for the "structural" nodes (paragraph, heading, lists, tables,
code blocks, rules, text + marks) is hard-coded; everything else is an
envelope Div/Span and goes through the mapping table.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from adflux.errors import InvalidADFError, UnrepresentableNodeError
from adflux.formats.adf.mapping import MappingTable, load_default_mapping
from adflux.formats.adf.schema import validate_adf
from adflux.ir.envelope import ENVELOPE_CLASS_PREFIX, is_envelope, unpack_envelope

if TYPE_CHECKING:
    import panflute as pf

    from adflux.options import Options

# ADF node types NOT supported in Jira's description field.
_JIRA_REJECTED_TYPES: frozenset[str] = frozenset(
    {
        "layoutSection",
        "layoutColumn",
        "extension",
        "bodiedExtension",
        "inlineExtension",
        "nestedExpand",
        "embedCard",
        "mediaGroup",
        "mediaSingle",
        "media",
        "mediaInline",
    }
)


def write_adf(doc: pf.Doc, options: Options) -> str:
    """Serialize a panflute ``Doc`` to an ADF JSON string."""
    mapping = load_default_mapping()
    envelopes = options["envelopes"]
    blocks = [_emit_block(b, mapping, envelopes) for b in doc.content]
    adf_doc = {
        "version": 1,
        "type": "doc",
        "content": [b for b in blocks if b is not None],
    }
    validate_adf(adf_doc)
    if options["jira-strict"] == "true":
        _check_jira_strict(adf_doc)
    return json.dumps(adf_doc, indent=2)


def _emit_block(
    block: pf.Block,
    mapping: MappingTable,
    envelopes: str,
) -> dict[str, Any] | None:
    import panflute as pf

    if isinstance(block, pf.Para):
        return {"type": "paragraph", "content": _emit_inlines(block.content, mapping, envelopes)}
    if isinstance(block, pf.Plain):
        return {"type": "paragraph", "content": _emit_inlines(block.content, mapping, envelopes)}
    if isinstance(block, pf.Header):
        return {
            "type": "heading",
            "attrs": {"level": block.level},
            "content": _emit_inlines(block.content, mapping, envelopes),
        }
    if isinstance(block, pf.CodeBlock):
        language = block.classes[0] if block.classes else ""
        cb_attrs: dict[str, Any] = {"language": language} if language else {}
        return {
            "type": "codeBlock",
            **({"attrs": cb_attrs} if cb_attrs else {}),
            "content": [{"type": "text", "text": block.text}] if block.text else [],
        }
    if isinstance(block, pf.BlockQuote):
        return {
            "type": "blockquote",
            "content": [_emit_block(b, mapping, envelopes) for b in block.content],
        }
    if isinstance(block, pf.BulletList):
        return {
            "type": "bulletList",
            "content": [_emit_list_item(item, mapping, envelopes) for item in block.content],
        }
    if isinstance(block, pf.OrderedList):
        attrs: dict[str, Any] = {}
        if getattr(block, "start", 1) and block.start != 1:
            attrs["order"] = block.start
        return {
            "type": "orderedList",
            **({"attrs": attrs} if attrs else {}),
            "content": [_emit_list_item(item, mapping, envelopes) for item in block.content],
        }
    if isinstance(block, pf.HorizontalRule):
        return {"type": "rule"}
    if isinstance(block, pf.Table):
        return _emit_table(block, mapping, envelopes)
    if isinstance(block, pf.Div) and is_envelope(block):
        return _emit_envelope_block(block, mapping, envelopes)
    # Unrepresentable top-level block: behavior depends on envelopes option.
    if envelopes == "keep-strict":
        raise UnrepresentableNodeError(type(block).__name__, "adf")
    if envelopes == "drop":
        return None
    # Fall back to wrapping the contents as a paragraph if possible.
    text = pf_stringify(block)
    return {"type": "paragraph", "content": [{"type": "text", "text": text}] if text else []}


def _emit_list_item(
    item: list[pf.Block] | Any,
    mapping: MappingTable,
    envelopes: str,
) -> dict[str, Any]:
    import panflute as pf

    # panflute BulletList/OrderedList contain ListItem with a .content list.
    blocks = list(item.content) if isinstance(item, pf.ListItem) else list(item)
    return {
        "type": "listItem",
        "content": [
            b for b in (_emit_block(b, mapping, envelopes) for b in blocks) if b is not None
        ],
    }


def _emit_table(
    table: pf.Table,
    mapping: MappingTable,
    envelopes: str,
) -> dict[str, Any]:

    rows: list[dict[str, Any]] = []

    def _emit_cell(cell: pf.TableCell, *, header: bool) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        rowspan = getattr(cell, "rowspan", 1) or 1
        colspan = getattr(cell, "colspan", 1) or 1
        if rowspan != 1:
            attrs["rowspan"] = rowspan
        if colspan != 1:
            attrs["colspan"] = colspan
        cell_type = "tableHeader" if header else "tableCell"
        return {
            "type": cell_type,
            **({"attrs": attrs} if attrs else {}),
            "content": [
                b
                for b in (_emit_block(b, mapping, envelopes) for b in cell.content)
                if b is not None
            ],
        }

    def _emit_row(row: pf.TableRow, *, header: bool) -> dict[str, Any]:
        return {
            "type": "tableRow",
            "content": [_emit_cell(c, header=header) for c in row.content],
        }

    for row in getattr(table.head, "content", []) or []:
        rows.append(_emit_row(row, header=True))
    for body in table.content:
        for row in getattr(body, "content", []) or []:
            rows.append(_emit_row(row, header=False))

    return {"type": "table", "content": rows}


def _emit_envelope_block(
    div: pf.Div,
    mapping: MappingTable,
    envelopes: str,
) -> dict[str, Any]:
    import panflute as pf

    env = unpack_envelope(div)
    if env.node_type in {"raw"}:
        return env.attrs
    entry = mapping.get(env.node_type)
    node: dict[str, Any] = {"type": env.node_type}
    if env.attrs:
        node["attrs"] = dict(env.attrs)

    content_kind = entry.content_kind if entry else "block"

    if content_kind == "none":
        return node

    if content_kind == "inline":
        inlines_src: list[Any] = []
        for child in div.content:
            if isinstance(child, (pf.Plain, pf.Para)):
                inlines_src.extend(child.content)
            else:
                inlines_src.append(child)
        emitted = _emit_inlines(inlines_src, mapping, envelopes)
        if emitted:
            node["content"] = emitted
        return node

    if div.content:
        node["content"] = [
            b for b in (_emit_block(b, mapping, envelopes) for b in div.content) if b is not None
        ]
    return node


def _emit_inlines(
    inlines: Any,
    mapping: MappingTable,
    envelopes: str,
    marks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    import panflute as pf

    out: list[dict[str, Any]] = []
    marks = marks or []
    buffer: list[str] = []

    def _flush() -> None:
        if not buffer:
            return
        text = "".join(buffer)
        if text:
            node: dict[str, Any] = {"type": "text", "text": text}
            if marks:
                node["marks"] = list(marks)
            out.append(node)
        buffer.clear()

    for inline in inlines or []:
        if isinstance(inline, pf.Str):
            buffer.append(inline.text)
        elif isinstance(inline, pf.Space):
            buffer.append(" ")
        elif isinstance(inline, pf.SoftBreak):
            buffer.append("\n")
        elif isinstance(inline, pf.LineBreak):
            _flush()
            out.append({"type": "hardBreak"})
        elif isinstance(inline, pf.Strong):
            _flush()
            out.extend(
                _emit_inlines(inline.content, mapping, envelopes, [*marks, {"type": "strong"}])
            )
        elif isinstance(inline, pf.Emph):
            _flush()
            out.extend(_emit_inlines(inline.content, mapping, envelopes, [*marks, {"type": "em"}]))
        elif isinstance(inline, pf.Strikeout):
            _flush()
            out.extend(
                _emit_inlines(inline.content, mapping, envelopes, [*marks, {"type": "strike"}])
            )
        elif isinstance(inline, pf.Underline):
            _flush()
            out.extend(
                _emit_inlines(inline.content, mapping, envelopes, [*marks, {"type": "underline"}])
            )
        elif isinstance(inline, pf.Subscript):
            _flush()
            out.extend(
                _emit_inlines(
                    inline.content,
                    mapping,
                    envelopes,
                    [*marks, {"type": "subsup", "attrs": {"type": "sub"}}],
                )
            )
        elif isinstance(inline, pf.Superscript):
            _flush()
            out.extend(
                _emit_inlines(
                    inline.content,
                    mapping,
                    envelopes,
                    [*marks, {"type": "subsup", "attrs": {"type": "sup"}}],
                )
            )
        elif isinstance(inline, pf.Code):
            _flush()
            out.append({"type": "text", "text": inline.text, "marks": [*marks, {"type": "code"}]})
        elif isinstance(inline, pf.Link):
            _flush()
            link_attrs: dict[str, Any] = {"href": inline.url}
            if inline.title:
                link_attrs["title"] = inline.title
            link_mark = {"type": "link", "attrs": link_attrs}
            out.extend(_emit_inlines(inline.content, mapping, envelopes, [*marks, link_mark]))
        elif isinstance(inline, pf.Span) and is_envelope(inline):
            _flush()
            out.append(_emit_envelope_inline(inline, mapping, envelopes))
        else:
            # Anything unrecognized: stringify into the current text buffer.
            buffer.append(pf_stringify(inline))
    _flush()
    return out


def _emit_envelope_inline(
    span: pf.Span,
    mapping: MappingTable,
    envelopes: str,
) -> dict[str, Any]:
    env = unpack_envelope(span)
    # Marks represented as inline envelopes (mark-*) are reconstructed at text level.
    if env.node_type.startswith("mark-"):
        # Best-effort: emit the child inlines as plain text with the mark name.
        mark_type = env.node_type.removeprefix("mark-")
        children = _emit_inlines(span.content, mapping, envelopes, [{"type": mark_type}])
        if children:
            return (
                children[0]
                if len(children) == 1
                else {
                    "type": "text",
                    "text": pf_stringify(span),
                    "marks": [{"type": mark_type}],
                }
            )
    node: dict[str, Any] = {"type": env.node_type}
    if env.attrs:
        node["attrs"] = dict(env.attrs)
    if span.content:
        node["content"] = _emit_inlines(span.content, mapping, envelopes)
    return node


def pf_stringify(elem: Any) -> str:
    """Stringify a panflute element, returning an empty string on failure."""
    import panflute as pf

    try:
        result: str = pf.stringify(elem)
    except Exception:
        return ""
    return result


def _check_jira_strict(adf_doc: dict[str, Any]) -> None:
    """Walk the ADF tree and raise if any Jira-rejected node types are found."""

    def _walk(node: dict[str, Any]) -> None:
        node_type = node.get("type", "")
        if node_type in _JIRA_REJECTED_TYPES:
            raise InvalidADFError(
                f"Node type {node_type!r} is not supported in Jira's ADF profile (jira-strict=true)"
            )
        for child in node.get("content", []):
            if isinstance(child, dict):
                _walk(child)

    _walk(adf_doc)


# Allow callers to identify envelope class prefix without extra imports.
__all__ = ["ENVELOPE_CLASS_PREFIX", "write_adf"]
