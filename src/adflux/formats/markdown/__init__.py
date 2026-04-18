"""Markdown (CommonMark + GFM) reader/writer — pure-Python implementation.

The reader uses :mod:`markdown_it` (markdown-it-py) plus selected GFM
extensions and adapts its tokens into a panflute :class:`pf.Doc`. The
writer uses a hand-rolled CommonMark serializer that walks the AST.

The reader's output shape mirrors what pandoc's
``commonmark_x-fenced_divs-bracketed_spans`` reader used to produce so
that the existing :mod:`adflux.formats.markdown.pretty` ``unprettify`` /
``prettify`` passes continue to operate without change. ADF macros and
other ADF-only constructs are expressed through HTML-comment markers
(e.g. ``<!--adf:status text="..."/-->``) and GitHub idioms (alerts,
``<details>``, autolinks, GFM task lists) which are recognised by
``markdown.pretty`` and converted to/from ADF envelope nodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

    from adflux.profiles import Profile


def _md_reader(source: str | bytes, profile: Profile, options: dict[str, Any]) -> pf.Doc:
    _ = profile, options
    text = source.decode("utf-8") if isinstance(source, bytes) else source
    doc = _parse_md(text)
    return unprettify(doc)


def _md_writer(doc: pf.Doc, profile: Profile, options: dict[str, Any]) -> str:
    _ = options
    from adflux.ir.profile_filter import apply_profile

    # Skip prettify under fail-loud so apply_profile sees the raw envelopes
    # and can raise on the first unrepresentable node.
    if profile.name != "fail-loud":
        doc = prettify(doc)
        doc = splice_transparent_divs(doc)
    doc = apply_profile(doc, profile)
    return _render_md(doc)


register_reader("md", _md_reader)
register_reader("markdown", _md_reader)
register_writer("md", _md_writer)
register_writer("markdown", _md_writer)
