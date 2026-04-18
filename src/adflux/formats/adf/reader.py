"""ADF JSON -> panflute Doc reader.

The reader is intentionally generic: it consults the YAML mapping table
(:mod:`adflux.formats.adf.mapping`) to decide how each ADF node type is
translated. Only a small core of "special" nodes (document root, text, marks)
requires dedicated logic, because those are structural rather than mapping-
configurable.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from adflux.errors import InvalidADFError
from adflux.formats.adf.mapping import MappingTable, load_default_mapping
from adflux.formats.adf.schema import validate_adf
from adflux.ir.envelope import pack_envelope

if TYPE_CHECKING:
    import panflute as pf

    from adflux.options import Options


_MARK_HANDLERS: dict[str, str] = {
    "strong": "Strong",
    "em": "Emph",
    "code": "Code",
    "strike": "Strikeout",
    "underline": "Underline",
    "subsup": "SubSup",  # dispatched specially
    "link": "Link",
    "textColor": "TextColor",
}


def read_adf(source: str | bytes, options: Options) -> pf.Doc:
    """Parse an ADF JSON document into a panflute ``Doc``."""
    _ = options
    import panflute as pf

    if isinstance(source, bytes):
        source = source.decode("utf-8")
    try:
        adf = json.loads(source)
    except json.JSONDecodeError as exc:
        raise InvalidADFError(f"invalid JSON: {exc}") from exc

    validate_adf(adf)

    mapping = load_default_mapping()
    blocks = [_convert_block(node, mapping) for node in adf.get("content", [])]
    return pf.Doc(*blocks)


def _convert_block(node: dict[str, Any], mapping: MappingTable) -> pf.Block:
    import panflute as pf

    node_type = node.get("type", "")
    entry = mapping.get(node_type)

    if node_type == "paragraph":
        return pf.Para(*_convert_inlines(node.get("content", []), mapping))
    if node_type == "heading":
        level = int(node.get("attrs", {}).get("level", 1))
        return pf.Header(*_convert_inlines(node.get("content", []), mapping), level=level)
    if node_type == "codeBlock":
        language = node.get("attrs", {}).get("language", "")
        text = "".join(child.get("text", "") for child in node.get("content", []))
        classes = [language] if language else []
        return pf.CodeBlock(text, classes=classes)
    if node_type == "blockquote":
        return pf.BlockQuote(*(_convert_block(c, mapping) for c in node.get("content", [])))
    if node_type == "bulletList":
        return pf.BulletList(*(_convert_list_item(c, mapping) for c in node.get("content", [])))
    if node_type == "orderedList":
        start = int(node.get("attrs", {}).get("order", 1))
        return pf.OrderedList(
            *(_convert_list_item(c, mapping) for c in node.get("content", [])),
            start=start,
        )
    if node_type == "rule":
        return pf.HorizontalRule()
    if node_type == "table":
        return _convert_table(node, mapping)

    # Everything else goes through the envelope (either mapped or raw fallback).
    if entry is None or entry.kind != "block":
        return pack_envelope(
            node_type,
            kind="block",
            raw_payload=node,
        )

    # Inline-content envelope (taskItem, decisionItem): children are inline runs,
    # stored inside the Div as a single Plain so they survive the AST.
    if entry.content_kind == "inline":
        inline_children = _convert_inlines(node.get("content", []), mapping)
        children_blocks: list[pf.Block] = [pf.Plain(*inline_children)] if inline_children else []
        return pack_envelope(
            node_type,
            kind="block",
            attrs=dict(node.get("attrs", {})),
            children=children_blocks,
        )

    if entry.content_kind == "none":
        return pack_envelope(
            node_type,
            kind="block",
            attrs=dict(node.get("attrs", {})),
        )

    children_blocks = []
    for child in node.get("content", []):
        child_type = child.get("type")
        child_entry = mapping.get(child_type) if child_type else None
        if child_entry and child_entry.kind == "inline":
            children_blocks.append(pf.Plain(*_convert_inlines([child], mapping)))
        else:
            children_blocks.append(_convert_block(child, mapping))
    return pack_envelope(
        node_type,
        kind="block",
        attrs=dict(node.get("attrs", {})),
        children=children_blocks,
    )


def _convert_list_item(node: dict[str, Any], mapping: MappingTable) -> pf.ListItem:
    import panflute as pf

    return pf.ListItem(*(_convert_block(c, mapping) for c in node.get("content", [])))


def _convert_table(node: dict[str, Any], mapping: MappingTable) -> pf.Block:
    import panflute as pf

    rows_src = node.get("content", [])
    if not rows_src:
        return pf.Null()

    def _cell(cell_node: dict[str, Any]) -> pf.TableCell:
        blocks = [_convert_block(c, mapping) for c in cell_node.get("content", [])]
        attrs = cell_node.get("attrs", {}) or {}
        rowspan = int(attrs.get("rowspan", 1))
        colspan = int(attrs.get("colspan", 1))
        return pf.TableCell(*blocks, rowspan=rowspan, colspan=colspan)

    def _row(row_node: dict[str, Any]) -> pf.TableRow:
        return pf.TableRow(*(_cell(c) for c in row_node.get("content", [])))

    # ADF tables may have a header row when the first row uses tableHeader cells.
    first_row = rows_src[0]
    first_cells = first_row.get("content", [])
    has_header = bool(first_cells) and all(c.get("type") == "tableHeader" for c in first_cells)
    if has_header:
        head = pf.TableHead(_row(first_row))
        body_rows = rows_src[1:]
    else:
        head = pf.TableHead()
        body_rows = rows_src
    body = pf.TableBody(*(_row(r) for r in body_rows))
    return pf.Table(body, head=head)


def _convert_inlines(
    nodes: list[dict[str, Any]],
    mapping: MappingTable,
) -> list[pf.Inline]:
    import panflute as pf

    out: list[pf.Inline] = []
    for node in nodes:
        node_type = node.get("type")
        if node_type == "text":
            out.extend(_convert_text(node))
        elif node_type == "hardBreak":
            out.append(pf.LineBreak())
        else:
            entry = mapping.get(node_type) if node_type else None
            if entry is None or entry.kind != "inline":
                out.append(
                    pack_envelope(
                        node_type or "unknown",
                        kind="inline",
                        raw_payload=node,
                    )
                )
            else:
                children = _convert_inlines(node.get("content", []), mapping)
                out.append(
                    pack_envelope(
                        node_type or "unknown",
                        kind="inline",
                        attrs=dict(node.get("attrs", {})),
                        children=children,
                    )
                )
    return out


def _convert_text(node: dict[str, Any]) -> list[pf.Inline]:

    text = node.get("text", "")
    inlines: list[pf.Inline] = _split_text(text)
    for mark in node.get("marks", []) or []:
        inlines = _apply_mark(inlines, mark)
    return inlines


def _split_text(text: str) -> list[pf.Inline]:
    """Split raw text into panflute Str/Space/SoftBreak runs."""
    import panflute as pf

    if not text:
        return []
    out: list[pf.Inline] = []
    parts = text.split("\n")
    for i, line in enumerate(parts):
        if i > 0:
            out.append(pf.SoftBreak())
        tokens = line.split(" ")
        for j, tok in enumerate(tokens):
            if j > 0:
                out.append(pf.Space())
            if tok:
                out.append(pf.Str(tok))
    return out


def _apply_mark(inlines: list[pf.Inline], mark: dict[str, Any]) -> list[pf.Inline]:
    import panflute as pf

    mtype = mark.get("type")
    attrs = mark.get("attrs", {}) or {}
    if mtype == "strong":
        return [pf.Strong(*inlines)]
    if mtype == "em":
        return [pf.Emph(*inlines)]
    if mtype == "code":
        text = pf.stringify(pf.Plain(*inlines))
        return [pf.Code(text)]
    if mtype == "strike":
        return [pf.Strikeout(*inlines)]
    if mtype == "underline":
        return [pf.Underline(*inlines)]
    if mtype == "subsup":
        if attrs.get("type") == "sup":
            return [pf.Superscript(*inlines)]
        return [pf.Subscript(*inlines)]
    if mtype == "link":
        url = attrs.get("href", "")
        title = attrs.get("title", "")
        return [pf.Link(*inlines, url=url, title=title)]
    if mtype == "textColor":
        color = attrs.get("color", "")
        return [pf.Span(*inlines, classes=["adf-mark-textColor"], attributes={"color": color})]
    # Unknown mark: wrap in an inline envelope to preserve it.
    return [
        pack_envelope(
            f"mark-{mtype}",
            kind="inline",
            attrs=dict(attrs),
            children=inlines,
        )
    ]
