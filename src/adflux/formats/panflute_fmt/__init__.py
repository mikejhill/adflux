"""Panflute (Pandoc JSON) reader/writer.

This format allows integration with other panflute-based tools by reading
and writing the Pandoc JSON AST format that ``panflute`` natively supports.

- **Reader**: accepts Pandoc JSON text → ``panflute.load()`` → ``pf.Doc``
- **Writer**: ``pf.Doc`` → ``panflute.dump()`` → Pandoc JSON text
"""

from __future__ import annotations

import io

import panflute as pf

from adflux.formats import register_reader, register_writer
from adflux.options import Options


def _panflute_reader(source: str | bytes, options: Options) -> pf.Doc:
    """Parse a Pandoc JSON string into a panflute ``Doc``."""
    text = source if isinstance(source, str) else source.decode("utf-8")
    return pf.load(io.StringIO(text))


def _panflute_writer(doc: pf.Doc, options: Options) -> str:
    """Serialize a panflute ``Doc`` to Pandoc JSON text."""
    buffer = io.StringIO()
    pf.dump(doc, buffer)
    return buffer.getvalue()


register_reader("panflute", _panflute_reader)
register_reader("pf", _panflute_reader)
register_writer("panflute", _panflute_writer)
register_writer("pf", _panflute_writer)
