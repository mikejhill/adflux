"""Markdown (CommonMark + GFM) reader/writer — pure-Python implementation.

The reader uses :mod:`markdown_it` (markdown-it-py) plus selected GFM
extensions and adapts its tokens into a panflute :class:`pf.Doc`. The
writer uses a hand-rolled CommonMark serializer that walks the AST.

ADF macros and other ADF-only constructs are expressed through HTML-comment
markers (e.g. ``<!--adf:status text="..."/-->``) and GitHub idioms (alerts,
``<details>``, autolinks, GFM task lists) which are recognised by
``markdown.pretty`` and converted to/from ADF envelope nodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adflux.formats import register_reader, register_writer
from adflux.formats.markdown.pretty import (
    prettify,
    splice_transparent_divs,
    unprettify,
)
from adflux.formats.markdown.reader import parse as _parse_md
from adflux.formats.markdown.writer import render as _render_md

if TYPE_CHECKING:
    import panflute as pf

    from adflux.options import Options


def _md_reader(source: str | bytes, options: Options) -> pf.Doc:
    _ = options
    text = source.decode("utf-8") if isinstance(source, bytes) else source
    doc = _parse_md(text)
    return unprettify(doc)


def _md_writer(doc: pf.Doc, options: Options) -> str:
    from adflux.ir.profile_filter import apply_options

    envelopes = options["envelopes"]

    # Skip prettify under keep-strict so apply_options sees the raw envelopes
    # and can raise on the first unrepresentable node.
    if envelopes != "keep-strict":
        doc = prettify(doc)
        doc = splice_transparent_divs(doc)
    doc = apply_options(doc, options)
    return _render_md(doc)


register_reader("md", _md_reader)
register_reader("markdown", _md_reader)
register_writer("md", _md_writer)
register_writer("markdown", _md_writer)
