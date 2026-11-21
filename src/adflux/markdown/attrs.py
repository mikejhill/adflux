r"""Attribute lists of directives: ``{key=value key2="quoted value" flag}``.

Grammar (whitespace separates entries)::

    attrs  := "{" entry* "}"
    entry  := key ( "=" value )?
    key    := [A-Za-z_][A-Za-z0-9_.:-]*
    value  := bare | '"' ( [^"\\] | "\\" any )* '"' | "'" ( [^'\\] | "\\" any )* "'"
    bare   := [^\s"'{}=]+

Escapes inside quotes: ``\\"``, ``\\'``, ``\\\\``, ``\\n``. A key without a value means
``true``. Values stay strings here; the converter types them with the ADF spec.
"""

from __future__ import annotations

import re

from adflux.errors import MarkdownError

_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]*")
_BARE = re.compile(r"[^\s\"'{}=]+")
_SAFE_BARE = re.compile(r"[A-Za-z0-9_.:/#%+@,-]+")


def parse_attrs(source: str, start: int = 0) -> tuple[dict[str, str], int]:
    """Parse ``{...}`` at ``source[start]``; return the attributes and the index after ``}``.

    Raises :class:`MarkdownError` when the list is malformed.
    """
    if start >= len(source) or source[start] != "{":
        raise MarkdownError("expected '{'")
    pos = start + 1
    out: dict[str, str] = {}
    length = len(source)
    while True:
        while pos < length and source[pos] in " \t":
            pos += 1
        if pos >= length:
            raise MarkdownError("unterminated attribute list (missing '}')")
        if source[pos] == "}":
            return out, pos + 1
        key_match = _KEY.match(source, pos)
        if not key_match:
            raise MarkdownError(f"bad attribute name at {source[pos : pos + 20]!r}")
        key = key_match.group(0)
        pos = key_match.end()
        if pos < length and source[pos] == "=":
            pos += 1
            if pos < length and source[pos] in "\"'":
                value, pos = _quoted(source, pos)
            else:
                bare = _BARE.match(source, pos)
                if not bare:
                    raise MarkdownError(f"missing value for {key!r}")
                value = bare.group(0)
                pos = bare.end()
        else:
            value = "true"
        out[key] = value
        if pos < length and source[pos] not in " \t}":
            raise MarkdownError(f"expected a space or '}}' after {key!r}")


def _quoted(source: str, pos: int) -> tuple[str, int]:
    quote = source[pos]
    pos += 1
    chars: list[str] = []
    while pos < len(source):
        char = source[pos]
        if char == "\\" and pos + 1 < len(source):
            nxt = source[pos + 1]
            chars.append("\n" if nxt == "n" else nxt)
            pos += 2
            continue
        if char == quote:
            return "".join(chars), pos + 1
        chars.append(char)
        pos += 1
    raise MarkdownError("unterminated quoted attribute value")


def quote(value: str) -> str:
    """Return ``value`` bare when safe, else double-quoted with escapes."""
    if value and _SAFE_BARE.fullmatch(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def format_attrs(attrs: dict[str, str]) -> str:
    """Return ``{k=v ...}`` (empty string for no attributes)."""
    if not attrs:
        return ""
    return "{" + " ".join(f"{key}={quote(value)}" for key, value in attrs.items()) + "}"
