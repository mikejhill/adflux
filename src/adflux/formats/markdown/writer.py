"""Pure-Python CommonMark + GFM serializer for the panflute IR.

Walks a panflute ``Doc`` and emits CommonMark text plus the GFM extensions
that adflux relies on: tables, strikethrough, task-list-style brackets,
fenced code, GitHub-alert blockquotes, and raw HTML for ADF-envelope markers.

The serializer targets the subset of constructs produced by
:mod:`adflux.formats.markdown.pretty.prettify`. It is **not** a general-purpose
CommonMark formatter — its job is to round-trip adflux's prettified
Markdown losslessly through the matching :mod:`markdown.reader`.
"""

from __future__ import annotations

import re
from io import StringIO
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import panflute as pf


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render(doc: pf.Doc) -> str:
    """Render ``doc`` to CommonMark text (with GFM extensions)."""
    out = StringIO()
    _Writer(out).render_blocks(list(doc.content), indent="")
    text = out.getvalue()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if not text.endswith("\n"):
        text += "\n"
    return text


# ---------------------------------------------------------------------------
# Inline escaping
# ---------------------------------------------------------------------------


_INLINE_ESCAPE_RE = re.compile(r"([\\`*_\[\]<])")


def _escape_text(text: str) -> str:
    r"""Escape CommonMark inline metacharacters in plain text runs.

    We escape only characters that are unambiguously problematic in any
    inline position. Block-level metachars (``#``, ``>``, ``-``, ``+``,
    ``=``, ``|``, ``.``) are intentionally left alone because escaping
    them mid-paragraph would produce noisy output (``\.``) without
    semantic benefit; they are only meaningful at line start, and
    paragraphs are wrapped by the writer in ways that keep them inline.
    """
    return _INLINE_ESCAPE_RE.sub(r"\\\1", text)


# ---------------------------------------------------------------------------
# Internal writer
# ---------------------------------------------------------------------------


class _Writer:
    def __init__(self, out: StringIO) -> None:
        self._out = out

    # -- block dispatch ----------------------------------------------------

    def render_blocks(self, blocks: list[Any], *, indent: str) -> None:
        import panflute as pf

        for i, block in enumerate(blocks):
            if i > 0:
                self._out.write("\n")
            if isinstance(block, pf.Header):
                self._render_header(block, indent)
            elif isinstance(block, pf.Para):
                self._render_para(block, indent)
            elif isinstance(block, pf.Plain):
                self._render_plain(block, indent)
            elif isinstance(block, pf.CodeBlock):
                self._render_code_block(block, indent)
            elif isinstance(block, pf.BlockQuote):
                self._render_blockquote(block, indent)
            elif isinstance(block, pf.BulletList):
                self._render_bullet_list(block, indent)
            elif isinstance(block, pf.OrderedList):
                self._render_ordered_list(block, indent)
            elif isinstance(block, pf.HorizontalRule):
                self._out.write(f"{indent}---\n")
            elif isinstance(block, pf.Table):
                self._render_table(block, indent)
            elif isinstance(block, pf.RawBlock):
                self._render_raw_block(block, indent)
            elif isinstance(block, pf.Div):
                # Untransformed Div: render its children transparently.
                self.render_blocks(list(block.content), indent=indent)
            else:
                # Fallback: stringify whatever we got.
                self._out.write(f"{indent}{pf.stringify(block)}\n")

    # -- block renderers ---------------------------------------------------

    def _render_header(self, hdr: pf.Header, indent: str) -> None:
        text = self._inlines_to_text(list(hdr.content))
        self._out.write(f"{indent}{'#' * hdr.level} {text}\n")

    def _render_para(self, para: pf.Para, indent: str) -> None:
        text = self._inlines_to_text(list(para.content))
        for line in text.split("\n"):
            self._out.write(f"{indent}{line}\n")

    def _render_plain(self, plain: pf.Plain, indent: str) -> None:
        text = self._inlines_to_text(list(plain.content))
        for line in text.split("\n"):
            self._out.write(f"{indent}{line}\n")

    def _render_code_block(self, blk: pf.CodeBlock, indent: str) -> None:
        info = ""
        if blk.classes:
            info = blk.classes[0]
        text = blk.text or ""
        # Choose enough backticks to outdo any run inside the content.
        max_run = max((len(m.group(0)) for m in re.finditer(r"`+", text)), default=0)
        fence = "`" * max(3, max_run + 1)
        self._out.write(f"{indent}{fence}{info}\n")
        for line in text.split("\n"):
            self._out.write(f"{indent}{line}\n")
        self._out.write(f"{indent}{fence}\n")

    def _render_blockquote(self, bq: pf.BlockQuote, indent: str) -> None:
        # Render children to a temporary buffer, then prefix every line with "> ".
        buf = StringIO()
        _Writer(buf).render_blocks(list(bq.content), indent="")
        for line in buf.getvalue().rstrip("\n").split("\n"):
            prefix = "> " if line else ">"
            self._out.write(f"{indent}{prefix}{line}\n")

    def _render_bullet_list(self, lst: pf.BulletList, indent: str) -> None:
        marker = "- "
        cont_indent = indent + "  "
        for item in lst.content:
            self._render_list_item(item, indent=indent, marker=marker, cont_indent=cont_indent)

    def _render_ordered_list(self, lst: pf.OrderedList, indent: str) -> None:
        start = getattr(lst, "start", 1) or 1
        # Width of the largest marker so continuation indent matches.
        for n, item in enumerate(lst.content, start=start):
            marker_text = f"{n}. "
            cont_indent = indent + " " * len(marker_text)
            self._render_list_item(item, indent=indent, marker=marker_text, cont_indent=cont_indent)

    def _render_list_item(
        self,
        item: pf.ListItem,
        *,
        indent: str,
        marker: str,
        cont_indent: str,
    ) -> None:
        import panflute as pf

        children = list(item.content)
        if not children:
            self._out.write(f"{indent}{marker}\n")
            return

        # Render the item's blocks into a fresh buffer with the cont_indent
        # already applied to nested content. Then we replace the first line's
        # indent with marker.
        buf = StringIO()
        _Writer(buf).render_blocks(children, indent="")
        text = buf.getvalue().rstrip("\n")
        lines = text.split("\n") if text else [""]
        first = True
        for line in lines:
            if first:
                self._out.write(f"{indent}{marker}{line}\n")
                first = False
            else:
                self._out.write(f"{cont_indent}{line}\n" if line else "\n")
        # If the item contains multiple Para blocks (loose list), the inner
        # writer already produced blank separators. Nothing else needed.
        _ = pf  # quiet linter

    def _render_table(self, tbl: pf.Table, indent: str) -> None:
        import panflute as pf

        # Extract header row + body rows.
        head_rows: list[list[list[Any]]] = []
        body_rows: list[list[list[Any]]] = []
        aligns: list[str] = []

        head = getattr(tbl, "head", None)
        if head is not None:
            for row in head.content:
                head_rows.append([list(cell.content) for cell in row.content])
        for body in getattr(tbl, "content", []) or []:
            for row in body.content:
                body_rows.append([list(cell.content) for cell in row.content])

        # Alignments come from tbl.colspec (panflute) — list of (align, width) tuples.
        n_cols = len(head_rows[0]) if head_rows else (len(body_rows[0]) if body_rows else 0)
        raw_colspec = list(getattr(tbl, "colspec", []) or [])
        aligns = []
        for i in range(n_cols):
            a = raw_colspec[i][0] if i < len(raw_colspec) else "AlignDefault"
            if a == "AlignCenter":
                aligns.append("center")
            elif a == "AlignRight":
                aligns.append("right")
            elif a == "AlignLeft":
                aligns.append("left")
            else:
                aligns.append("default")

        def _cell_text(cell_blocks: list[Any]) -> str:
            # Tables in CommonMark are inline-only — flatten any Plain/Para into inlines.
            inlines: list[Any] = []
            for b in cell_blocks:
                if isinstance(b, (pf.Plain, pf.Para)):
                    inlines.extend(b.content)
                else:
                    inlines.append(pf.Str(pf.stringify(b)))
            text = self._inlines_to_text(inlines)
            return text.replace("\n", " ").replace("|", "\\|")

        if not head_rows:
            return  # GFM tables require a header

        header_cells = [_cell_text(c) for c in head_rows[0]]
        body_cells = [[_cell_text(c) for c in row] for row in body_rows]

        # Compute column widths for prettiness.
        widths = [len(h) for h in header_cells]
        for row in body_cells:
            for i, c in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(c))
        # Minimum width 3 to keep separator readable.
        widths = [max(w, 3) for w in widths]

        def _sep(width: int, align: str) -> str:
            if align == "left":
                return ":" + "-" * (width - 1)
            if align == "right":
                return "-" * (width - 1) + ":"
            if align == "center":
                return ":" + "-" * (width - 2) + ":"
            return "-" * width

        def _row(cells: list[str]) -> str:
            padded = [
                cells[i].ljust(widths[i]) if i < len(widths) else cells[i]
                for i in range(len(cells))
            ]
            return "| " + " | ".join(padded) + " |"

        self._out.write(f"{indent}{_row(header_cells)}\n")
        sep_cells = [
            _sep(widths[i], aligns[i] if i < len(aligns) else "default")
            for i in range(len(header_cells))
        ]
        self._out.write(f"{indent}| " + " | ".join(sep_cells) + " |\n")
        for row in body_cells:
            self._out.write(f"{indent}{_row(row)}\n")

    def _render_raw_block(self, blk: pf.RawBlock, indent: str) -> None:
        if blk.format != "html":
            return
        text = blk.text.rstrip("\n")
        for line in text.split("\n"):
            self._out.write(f"{indent}{line}\n")

    # -- inline serialization ---------------------------------------------

    def _inlines_to_text(self, inlines: list[Any]) -> str:
        import panflute as pf

        parts: list[str] = []
        for el in inlines:
            if isinstance(el, pf.Str):
                parts.append(_escape_text(el.text))
            elif isinstance(el, pf.Space):
                parts.append(" ")
            elif isinstance(el, pf.SoftBreak):
                parts.append("\n")
            elif isinstance(el, pf.LineBreak):
                parts.append("\\\n")
            elif isinstance(el, pf.Emph):
                parts.append("*" + self._inlines_to_text(list(el.content)) + "*")
            elif isinstance(el, pf.Strong):
                parts.append("**" + self._inlines_to_text(list(el.content)) + "**")
            elif isinstance(el, pf.Strikeout):
                parts.append("~~" + self._inlines_to_text(list(el.content)) + "~~")
            elif isinstance(el, pf.Code):
                txt = el.text or ""
                run = max((len(m.group(0)) for m in re.finditer(r"`+", txt)), default=0)
                ticks = "`" * (run + 1)
                pad = " " if txt.startswith("`") or txt.endswith("`") else ""
                parts.append(f"{ticks}{pad}{txt}{pad}{ticks}")
            elif isinstance(el, pf.Link):
                inner = self._inlines_to_text(list(el.content))
                url = el.url or ""
                title = el.title or ""
                # Autolink shortcut: <url> when the visible text equals the URL
                # and there's no title.
                if not title and inner == url and re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
                    parts.append(f"<{url}>")
                else:
                    if title:
                        parts.append(f'[{inner}]({url} "{title}")')
                    else:
                        parts.append(f"[{inner}]({url})")
            elif isinstance(el, pf.Image):
                inner = self._inlines_to_text(list(el.content))
                parts.append(f"![{inner}]({el.url or ''})")
            elif isinstance(el, pf.RawInline):
                # Pass raw inline content through verbatim regardless of
                # declared format — adflux only emits raw inlines we
                # explicitly want preserved (HTML comments, GFM alert
                # markers, etc.).
                parts.append(el.text)
            elif isinstance(el, pf.Span):
                # Untransformed Span: render its children transparently.
                parts.append(self._inlines_to_text(list(el.content)))
            else:
                # Fallback: best-effort stringify.
                parts.append(_escape_text(pf.stringify(el)))
        return "".join(parts)
