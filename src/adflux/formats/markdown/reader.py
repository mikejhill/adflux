"""Pure-Python Markdown reader: ``markdown-it-py`` tokens → panflute Doc.

Uses ``markdown-it-py`` configured for CommonMark + the GFM extensions
adflux needs (tables, strikethrough, GFM alerts via blockquote convention,
hard line breaks, autolinks).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

if TYPE_CHECKING:
    import panflute as pf
    from markdown_it.token import Token


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse(text: str) -> pf.Doc:
    """Parse ``text`` and return a panflute Doc."""
    import panflute as pf

    md = _build_parser()
    tokens = md.parse(text)
    parser = _Parser(tokens)
    blocks = parser.parse_blocks()
    return pf.Doc(*blocks)


# ---------------------------------------------------------------------------
# markdown-it configuration
# ---------------------------------------------------------------------------


def _build_parser() -> MarkdownIt:
    return (
        MarkdownIt("commonmark", {"breaks": False, "html": True})
        .enable("table")
        .enable("strikethrough")
        .use(tasklists_plugin, enabled=False, label=False)
    )


# ---------------------------------------------------------------------------
# Token → AST translation
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    # -- block parsing -----------------------------------------------------

    def parse_blocks(self, stop: str | None = None) -> list[Any]:
        import panflute as pf

        blocks: list[Any] = []
        while self.i < len(self.tokens):
            tok = self.tokens[self.i]
            if stop is not None and tok.type == stop:
                self.i += 1
                return blocks
            t = tok.type
            if t == "heading_open":
                blocks.append(self._parse_heading())
            elif t == "paragraph_open":
                blocks.append(self._parse_paragraph())
            elif t == "fence":
                blocks.append(self._parse_fence(tok))
                self.i += 1
            elif t == "code_block":
                blocks.append(pf.CodeBlock(tok.content.rstrip("\n")))
                self.i += 1
            elif t == "blockquote_open":
                blocks.append(self._parse_blockquote())
            elif t == "bullet_list_open":
                blocks.append(self._parse_list(ordered=False))
            elif t == "ordered_list_open":
                blocks.append(self._parse_list(ordered=True, start=int(tok.attrGet("start") or 1)))
            elif t == "hr":
                blocks.append(pf.HorizontalRule())
                self.i += 1
            elif t == "table_open":
                blocks.append(self._parse_table())
            elif t == "html_block":
                blocks.append(pf.RawBlock(tok.content.rstrip("\n"), format="html"))
                self.i += 1
            else:
                # Skip closers / anything we don't model explicitly.
                self.i += 1
        return blocks

    def _parse_heading(self) -> pf.Header:
        import panflute as pf

        open_tok = self.tokens[self.i]
        level = int(open_tok.tag[1])
        self.i += 1  # consume heading_open
        inline = self.tokens[self.i]
        self.i += 1
        # Skip heading_close
        if self.i < len(self.tokens) and self.tokens[self.i].type == "heading_close":
            self.i += 1
        children = self._inlines_from_token(inline)
        return pf.Header(*children, level=level)

    def _parse_paragraph(self) -> pf.Para | pf.Plain:
        import panflute as pf

        open_tok = self.tokens[self.i]
        self.i += 1  # consume paragraph_open
        inline = self.tokens[self.i]
        self.i += 1
        if self.i < len(self.tokens) and self.tokens[self.i].type == "paragraph_close":
            self.i += 1
        children = self._inlines_from_token(inline)
        # tight list items emit paragraph_open with `hidden=True`; render as Plain.
        if open_tok.hidden:
            return pf.Plain(*children)
        return pf.Para(*children)

    def _parse_fence(self, tok: Token) -> pf.CodeBlock:
        import panflute as pf

        info = (tok.info or "").strip()
        cls = [info] if info else []
        return pf.CodeBlock(tok.content.rstrip("\n"), classes=cls)

    def _parse_blockquote(self) -> pf.BlockQuote:
        import panflute as pf

        self.i += 1  # consume blockquote_open
        body = self.parse_blocks(stop="blockquote_close")
        return pf.BlockQuote(*body)

    def _parse_list(self, *, ordered: bool, start: int = 1) -> pf.BulletList | pf.OrderedList:
        import panflute as pf

        close_type = "ordered_list_close" if ordered else "bullet_list_close"
        self.i += 1  # consume *_list_open
        items: list[pf.ListItem] = []
        while self.i < len(self.tokens) and self.tokens[self.i].type != close_type:
            tok = self.tokens[self.i]
            if tok.type == "list_item_open":
                self.i += 1
                body = self.parse_blocks(stop="list_item_close")
                items.append(pf.ListItem(*body))
            else:
                self.i += 1
        if self.i < len(self.tokens) and self.tokens[self.i].type == close_type:
            self.i += 1
        if ordered:
            return pf.OrderedList(*items, start=start)
        return pf.BulletList(*items)

    def _parse_table(self) -> pf.Table:
        import panflute as pf

        self.i += 1  # consume table_open
        head_rows: list[pf.TableRow] = []
        body_rows: list[pf.TableRow] = []
        aligns: list[str] = []

        # thead
        if self.i < len(self.tokens) and self.tokens[self.i].type == "thead_open":
            self.i += 1
            while self.i < len(self.tokens) and self.tokens[self.i].type != "thead_close":
                tok = self.tokens[self.i]
                if tok.type == "tr_open":
                    self.i += 1
                    cells: list[pf.TableCell] = []
                    while self.tokens[self.i].type != "tr_close":
                        cell_tok = self.tokens[self.i]
                        if cell_tok.type in ("th_open", "td_open"):
                            # Capture alignment from style="text-align:..."
                            style_val = cell_tok.attrGet("style") or ""
                            style = str(style_val) if not isinstance(style_val, str) else style_val
                            if "text-align:center" in style:
                                aligns.append("AlignCenter") if len(aligns) < len(
                                    cells
                                ) + 1 else None
                                aligns += ["AlignCenter"] if len(aligns) <= len(cells) else []
                            elif "text-align:right" in style:
                                aligns += ["AlignRight"] if len(aligns) <= len(cells) else []
                            elif "text-align:left" in style:
                                aligns += ["AlignLeft"] if len(aligns) <= len(cells) else []
                            else:
                                aligns += ["AlignDefault"] if len(aligns) <= len(cells) else []
                            self.i += 1
                            inline = self.tokens[self.i]
                            self.i += 1
                            inlines = self._inlines_from_token(inline)
                            cells.append(pf.TableCell(pf.Plain(*inlines)))
                            # consume th_close / td_close
                            self.i += 1
                        else:
                            self.i += 1
                    head_rows.append(pf.TableRow(*cells))
                    self.i += 1  # tr_close
                else:
                    self.i += 1
            self.i += 1  # thead_close

        # tbody
        if self.i < len(self.tokens) and self.tokens[self.i].type == "tbody_open":
            self.i += 1
            while self.i < len(self.tokens) and self.tokens[self.i].type != "tbody_close":
                tok = self.tokens[self.i]
                if tok.type == "tr_open":
                    self.i += 1
                    cells = []
                    while self.tokens[self.i].type != "tr_close":
                        cell_tok = self.tokens[self.i]
                        if cell_tok.type in ("th_open", "td_open"):
                            self.i += 1
                            inline = self.tokens[self.i]
                            self.i += 1
                            inlines = self._inlines_from_token(inline)
                            cells.append(pf.TableCell(pf.Plain(*inlines)))
                            self.i += 1
                        else:
                            self.i += 1
                    body_rows.append(pf.TableRow(*cells))
                    self.i += 1  # tr_close
                else:
                    self.i += 1
            self.i += 1  # tbody_close

        if self.i < len(self.tokens) and self.tokens[self.i].type == "table_close":
            self.i += 1

        head = pf.TableHead(*head_rows)
        body = pf.TableBody(*body_rows)
        n_cols = len(head_rows[0].content) if head_rows else 0
        while len(aligns) < n_cols:
            aligns.append("AlignDefault")
        colspec = [(a, "ColWidthDefault") for a in aligns[:n_cols]]
        return pf.Table(body, head=head, colspec=colspec)

    # -- inline parsing ----------------------------------------------------

    def _inlines_from_token(self, inline_tok: Token) -> list[Any]:
        children = inline_tok.children or []
        return _InlineParser(children).parse()


class _InlineParser:
    """Convert a list of inline markdown-it tokens into panflute inlines."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    def parse(self, stop: str | None = None) -> list[Any]:
        import panflute as pf

        out: list[Any] = []
        while self.i < len(self.tokens):
            tok = self.tokens[self.i]
            if stop is not None and tok.type == stop:
                self.i += 1
                return out
            t = tok.type
            if t == "text":
                out.extend(_text_to_inlines(tok.content))
                self.i += 1
            elif t == "softbreak":
                out.append(pf.SoftBreak())
                self.i += 1
            elif t == "hardbreak":
                out.append(pf.LineBreak())
                self.i += 1
            elif t == "code_inline":
                out.append(pf.Code(tok.content))
                self.i += 1
            elif t == "em_open":
                self.i += 1
                inner = self.parse(stop="em_close")
                out.append(pf.Emph(*inner))
            elif t == "strong_open":
                self.i += 1
                inner = self.parse(stop="strong_close")
                out.append(pf.Strong(*inner))
            elif t == "s_open":
                self.i += 1
                inner = self.parse(stop="s_close")
                out.append(pf.Strikeout(*inner))
            elif t == "link_open":
                href = tok.attrGet("href") or ""
                title = tok.attrGet("title") or ""
                self.i += 1
                inner = self.parse(stop="link_close")
                out.append(pf.Link(*inner, url=href, title=title))
            elif t == "image":
                src = tok.attrGet("src") or ""
                alt = tok.content or ""
                title = tok.attrGet("title") or ""
                # alt is plain string; wrap as Str sequence
                inner = _text_to_inlines(alt)
                out.append(pf.Image(*inner, url=src, title=title))
                self.i += 1
            elif t == "html_inline":
                out.append(pf.RawInline(tok.content, format="html"))
                self.i += 1
            else:
                # Unrecognized - skip but don't crash
                self.i += 1
        return out


# ---------------------------------------------------------------------------
# Text → inline tokens
# ---------------------------------------------------------------------------


_WHITESPACE_SPLIT = re.compile(r"(\s+)")


def _text_to_inlines(text: str) -> list[Any]:
    """Split a text run into Str / Space / SoftBreak panflute inlines."""
    import panflute as pf

    out: list[Any] = []
    if not text:
        return out
    parts = _WHITESPACE_SPLIT.split(text)
    for part in parts:
        if part == "":
            continue
        if part.isspace():
            # A run of whitespace becomes one Space (newlines become SoftBreak).
            if "\n" in part:
                out.append(pf.SoftBreak())
            else:
                out.append(pf.Space())
        else:
            out.append(pf.Str(part))
    return out
