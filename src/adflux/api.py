"""High-level public API for adflux.

The :func:`convert` function is the library's primary entry point. It dispatches
to the reader/writer registry populated in :mod:`adflux.formats`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from adflux.errors import UnsupportedFormatError
from adflux.formats import get_reader, get_writer, registered_formats
from adflux.profiles import Profile, resolve_profile

if TYPE_CHECKING:
    import panflute as pf


def convert(
    source: str | bytes,
    *,
    src: str,
    dst: str,
    profile: str | Profile = "strict-adf",
    options: dict[str, Any] | None = None,
) -> str:
    """Convert ``source`` from format ``src`` to format ``dst``.

    Args:
        source: Input document (text for Markdown, JSON text for ADF).
        src: Source-format identifier (``"md"`` / ``"markdown"`` or ``"adf"``).
        dst: Target-format identifier.
        profile: Fidelity profile name or :class:`Profile` instance.
        options: Optional per-format options, forwarded to reader/writer.

    Returns:
        Converted document as a string.

    Raises:
        UnsupportedFormatError: If ``src`` or ``dst`` is not registered.
        InvalidADFError: If ADF input fails schema validation.
        UnrepresentableNodeError: When ``fail-loud`` profile cannot represent a node.
    """
    opts = options or {}
    resolved = resolve_profile(profile)
    reader = get_reader(src)
    writer = get_writer(dst)
    doc: pf.Doc = reader(source, profile=resolved, options=opts)
    return writer(doc, profile=resolved, options=opts)


def validate(source: str | bytes, *, fmt: str) -> None:
    """Validate ``source`` as format ``fmt``. Raises on failure.

    Currently meaningful for ``fmt="adf"`` (JSON-schema validation). Other
    formats are accepted unconditionally.
    """
    if fmt not in registered_formats():
        raise UnsupportedFormatError(fmt)
    if fmt == "adf":
        from adflux.formats.adf.schema import validate_adf

        validate_adf(source)


def inspect_ast(source: str | bytes, *, src: str) -> str:
    """Parse ``source`` and return the internal IR as pretty-printed JSON."""
    import io
    import json as _json

    import panflute as pf

    reader = get_reader(src)
    doc = reader(source, profile=resolve_profile("strict-adf"), options={})
    buffer = io.StringIO()
    pf.dump(doc, buffer)
    return _json.dumps(_json.loads(buffer.getvalue()), indent=2)


def list_formats() -> list[str]:
    """Return the list of registered format identifiers, sorted."""
    return sorted(registered_formats())
