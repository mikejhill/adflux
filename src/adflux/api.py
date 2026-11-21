"""Public conversion API."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal

from adflux.adf.model import Node, dump, load
from adflux.adf.validate import validate
from adflux.markdown.reader import markdown_to_adf
from adflux.markdown.writer import adf_to_markdown
from adflux.profiles.profile import Profile, get_profile

Format = Literal["markdown", "md", "adf"]
AdfInput = str | bytes | Mapping[str, Any] | Node


def _doc(value: AdfInput) -> Node:
    return value if isinstance(value, Node) else load(value)


def to_adf(
    markdown: str,
    profile: str | Profile | None = "generic",
    *,
    strict: bool = False,
    check: bool = True,
) -> dict[str, Any]:
    """Convert Markdown to an ADF document (a JSON-ready ``dict``).

    ``profile`` is ``"jira"``, ``"confluence"``, ``"generic"`` or a :class:`Profile`.
    ``strict`` turns conversion warnings into errors; ``check`` validates the result
    with the spec generated from the ADF JSON Schema (fast). Call
    :func:`adflux.validate` for the full JSON Schema pass as well.
    """
    doc = markdown_to_adf(markdown, get_profile(profile), strict=strict)
    if check:
        validate(doc, schema=False)
    return doc.to_json()


def to_markdown(
    adf: AdfInput,
    profile: str | Profile | None = "generic",
    *,
    keep_metadata: bool = False,
) -> str:
    """Convert ADF (JSON text, bytes, a dict, a Confluence body envelope or a node) to Markdown."""
    return adf_to_markdown(_doc(adf), get_profile(profile), keep_metadata=keep_metadata)


def convert(
    source: str | bytes | Mapping[str, Any],
    src: Format,
    dst: Format,
    profile: str | Profile | None = "generic",
    **options: Any,
) -> str:
    """Convert between ``markdown`` and ``adf`` (ADF output is JSON text)."""
    src_kind = "adf" if src == "adf" else "markdown"
    dst_kind = "adf" if dst == "adf" else "markdown"
    if src_kind == "markdown":
        text = source.decode("utf-8") if isinstance(source, bytes) else source
        if not isinstance(text, str):
            raise TypeError("Markdown input must be text")
        if dst_kind == "markdown":
            return to_markdown(to_adf(text, profile, **options), profile)
        return json.dumps(to_adf(text, profile, **options), ensure_ascii=False)
    doc = _doc(source)
    if dst_kind == "adf":
        return dump(doc)
    return to_markdown(doc, profile, **options)
