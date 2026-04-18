"""Comparison helpers for ADF and Markdown round-trips.

Confluence injects volatile attributes (e.g. `localId`) into ADF nodes and
may collapse / reorder some structural details. Likewise adflux's MD
writer normalizes whitespace, so byte-for-byte equality is too strict.

These helpers reduce both sides to a stable structural form for comparison.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

# ADF attrs Confluence injects on ingest that we should ignore on the way back.
_VOLATILE_ATTRS: frozenset[str] = frozenset(
    {
        "localId",
        "__confluenceMetadata",
        "id",  # only when paired with localId-style nodes; safe to drop globally
    }
)


def normalize_adf(node: Any) -> Any:
    """Return a deep copy of `node` with volatile attrs stripped and content normalized."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            if k == "attrs" and isinstance(v, dict):
                cleaned = {
                    ak: normalize_adf(av) for ak, av in v.items() if ak not in _VOLATILE_ATTRS
                }
                if cleaned:
                    out[k] = cleaned
            elif k == "version":
                # ADF version metadata is irrelevant for structural equality.
                continue
            else:
                out[k] = normalize_adf(v)
        return out
    if isinstance(node, list):
        return [normalize_adf(x) for x in node]
    return node


def adf_summary(node: Any) -> list[tuple[int, str, str]]:
    """Flatten an ADF doc to (depth, type, text) triples for diff-friendly compare."""
    rows: list[tuple[int, str, str]] = []

    def visit(n: Any, depth: int) -> None:
        if isinstance(n, dict):
            ntype = n.get("type", "?")
            text = n.get("text", "") if ntype == "text" else ""
            rows.append((depth, ntype, text))
            for child in n.get("content", []) or []:
                visit(child, depth + 1)
        elif isinstance(n, list):
            for x in n:
                visit(x, depth)

    visit(node, 0)
    return rows


def adf_node_types(node: Any) -> list[str]:
    """Return the ordered list of every `type` value found in the ADF tree."""
    found: list[str] = []

    def visit(n: Any) -> None:
        if isinstance(n, dict):
            t = n.get("type")
            if t:
                found.append(t)
            for v in n.values():
                visit(v)
        elif isinstance(n, list):
            for x in n:
                visit(x)

    visit(node)
    return found


_WS = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_markdown(text: str) -> str:
    """Collapse runs of whitespace + blank lines for tolerant MD comparison."""
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.rstrip()
        # Collapse internal runs of whitespace inside a line, but preserve
        # leading indentation (significant for fenced code / lists).
        leading_len = len(stripped) - len(stripped.lstrip(" \t"))
        leading = stripped[:leading_len]
        rest = stripped[leading_len:]
        rest = _WS.sub(" ", rest)
        lines.append(f"{leading}{rest}")
    joined = "\n".join(lines).strip()
    return _BLANK_LINES.sub("\n\n", joined)


def md_word_bag(text: str) -> set[str]:
    """Return the set of alphanumeric tokens present in a Markdown document."""
    return set(re.findall(r"[A-Za-z0-9]+", text.lower()))


def assert_word_bag_equal(original: str, roundtripped: str, ignore: Iterable[str] = ()) -> None:
    """Assert original and roundtripped MD share the same alphanumeric tokens.

    `ignore` lets a test exclude tokens known to be lost or transformed by a
    given fixture (e.g. fenced-div attribute values that Confluence renames).
    """
    drop = {t.lower() for t in ignore}
    original_bag = md_word_bag(original) - drop
    new_bag = md_word_bag(roundtripped) - drop
    missing = original_bag - new_bag
    extra = new_bag - original_bag
    assert not missing, f"tokens lost in roundtrip: {sorted(missing)}"
    # `extra` is informational only — Confluence sometimes adds default
    # attribute names (e.g. `localid`); fail only if a curated set leaks.
    suspicious = {t for t in extra if t.startswith("adf") or t.startswith("paneltype")}
    assert not suspicious, f"unexpected extra tokens in roundtrip: {sorted(suspicious)}"
