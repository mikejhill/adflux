"""Reader/writer registry and format auto-registration.

Each format module calls :func:`register_reader` and :func:`register_writer` at
import time. Importing :mod:`adflux.formats` triggers registration of all
built-in formats.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from adflux.errors import UnsupportedFormatError

if TYPE_CHECKING:
    import panflute as pf

    from adflux.options import Options

Reader = Callable[[str | bytes, "Options"], "pf.Doc"]
Writer = Callable[["pf.Doc", "Options"], str]

_READERS: dict[str, Reader] = {}
_WRITERS: dict[str, Writer] = {}


def register_reader(fmt: str, reader: Reader) -> None:
    """Register a reader function for format ``fmt``."""
    _READERS[fmt] = reader


def register_writer(fmt: str, writer: Writer) -> None:
    """Register a writer function for format ``fmt``."""
    _WRITERS[fmt] = writer


def _wrap_reader(fn: Reader) -> Callable[..., pf.Doc]:
    def _call(source: str | bytes, *, options: Options) -> pf.Doc:
        return fn(source, options)

    return _call


def _wrap_writer(fn: Writer) -> Callable[..., str]:
    def _call(doc: pf.Doc, *, options: Options) -> str:
        return fn(doc, options)

    return _call


def get_reader(fmt: str) -> Callable[..., pf.Doc]:
    """Return the kwargs-based reader callable for format ``fmt``."""
    try:
        return _wrap_reader(_READERS[fmt])
    except KeyError as exc:
        raise UnsupportedFormatError(fmt, role="source format") from exc


def get_writer(fmt: str) -> Callable[..., str]:
    """Return the kwargs-based writer callable for format ``fmt``."""
    try:
        return _wrap_writer(_WRITERS[fmt])
    except KeyError as exc:
        raise UnsupportedFormatError(fmt, role="target format") from exc


def registered_formats() -> set[str]:
    """Return the set of formats that have at least a reader or a writer."""
    return set(_READERS) | set(_WRITERS)


# Auto-register built-in formats. Keep imports at bottom to avoid cycles.
from adflux.formats import adf as _adf  # noqa: E402,F401
from adflux.formats import markdown as _markdown  # noqa: E402,F401
from adflux.formats import panflute_fmt as _panflute_fmt  # noqa: E402,F401
