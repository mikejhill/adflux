"""ADF envelope convention.

An *envelope* is a Pandoc ``Div`` (block context) or ``Span`` (inline context)
whose class list starts with a marker like ``adf-panel`` or ``adf-status``, and
whose key-value attributes carry the ADF node's parameters. Opaque or complex
payloads are stored as a base64-encoded JSON blob under the ``data-adf-json`` key
so that the envelope remains round-trip stable across Pandoc's MD/AsciiDoc
writers (which preserve Div/Span attrs).

The ``adf-raw`` envelope is the universal fallback for ADF node types that
have no explicit entry in the mapping table - it stores the entire original
node as a JSON blob, guaranteeing zero data loss.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, overload

if TYPE_CHECKING:
    import panflute as pf

ENVELOPE_CLASS_PREFIX = "adf-"
ENVELOPE_RAW_CLASS = "adf-raw"
_JSON_ATTR = "data-adf-json"
_TYPE_ATTR = "data-adf-type"

EnvelopeKind = Literal["block", "inline"]


@dataclass(slots=True)
class Envelope:
    """Decoded envelope payload."""

    node_type: str
    kind: EnvelopeKind
    attrs: dict[str, Any] = field(default_factory=dict)
    classes: list[str] = field(default_factory=list)


def _envelope_class(node_type: str) -> str:
    return f"{ENVELOPE_CLASS_PREFIX}{node_type}"


def _encode_blob(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _decode_blob(blob: str) -> dict[str, Any]:
    raw = base64.b64decode(blob.encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("envelope JSON blob must decode to an object")
    return data


@overload
def pack_envelope(
    node_type: str,
    *,
    kind: Literal["block"],
    attrs: dict[str, Any] | None = None,
    children: list[Any] | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> pf.Div: ...


@overload
def pack_envelope(
    node_type: str,
    *,
    kind: Literal["inline"],
    attrs: dict[str, Any] | None = None,
    children: list[Any] | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> pf.Span: ...


def pack_envelope(
    node_type: str,
    *,
    kind: EnvelopeKind,
    attrs: dict[str, Any] | None = None,
    children: list[Any] | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> pf.Div | pf.Span:
    """Construct a panflute Div or Span wrapping ADF-specific data."""
    import panflute as pf

    attrs = dict(attrs or {})
    classes = [_envelope_class(node_type)]

    simple_kv: list[tuple[str, str]] = []
    complex_payload: dict[str, Any] = {}
    identifier = ""
    for key, value in attrs.items():
        if key == "id" and isinstance(value, (str, int, float)):
            # Pandoc promotes `id="..."` on Span/Div to the element identifier
            # slot. Set it directly so md round-trips don't lose it.
            identifier = str(value)
            continue
        if isinstance(value, bool):
            simple_kv.append((key, "true" if value else "false"))
        elif isinstance(value, (str, int, float)):
            simple_kv.append((key, str(value)))
        else:
            complex_payload[key] = value

    if raw_payload is not None:
        simple_kv.append((_TYPE_ATTR, node_type))
        simple_kv.append((_JSON_ATTR, _encode_blob(raw_payload)))
    elif complex_payload:
        simple_kv.append((_JSON_ATTR, _encode_blob(complex_payload)))

    # Pandoc-side limitation: `id` in Span/Div kv attrs is promoted to the
    # element identifier, so we set it explicitly to keep ADF round-trips.
    if kind == "block":
        return pf.Div(
            *(children or []),
            identifier=identifier,
            classes=classes,
            attributes=dict(simple_kv),
        )
    return pf.Span(
        *(children or []),
        identifier=identifier,
        classes=classes,
        attributes=dict(simple_kv),
    )


def is_envelope(elem: Any) -> bool:
    """Return True if elem is a Pandoc Div/Span carrying an ADF envelope marker."""
    import panflute as pf

    if not isinstance(elem, (pf.Div, pf.Span)):
        return False
    return any(cls.startswith(ENVELOPE_CLASS_PREFIX) for cls in elem.classes)


def unpack_envelope(elem: pf.Div | pf.Span) -> Envelope:
    """Decode an envelope Div/Span back into an Envelope instance."""
    import panflute as pf

    if not isinstance(elem, (pf.Div, pf.Span)):
        raise TypeError(f"unpack_envelope expects Div or Span, got {type(elem).__name__}")
    marker = next(
        (cls for cls in elem.classes if cls.startswith(ENVELOPE_CLASS_PREFIX)),
        None,
    )
    if marker is None:
        raise ValueError("element is not an ADF envelope (no adf-* class)")

    kind: EnvelopeKind = "block" if isinstance(elem, pf.Div) else "inline"
    raw_attrs = dict(elem.attributes)
    node_type = raw_attrs.pop(_TYPE_ATTR, marker.removeprefix(ENVELOPE_CLASS_PREFIX))
    blob = raw_attrs.pop(_JSON_ATTR, None)

    attrs: dict[str, Any] = dict(raw_attrs)
    # Pandoc promotes `id="..."` in Span/Div attributes to the element's
    # identifier slot rather than keeping it as a regular kv pair. Restore
    # it so envelopes whose ADF schema includes an `id` attr survive.
    elem_id = getattr(elem, "identifier", "") or ""
    if elem_id and "id" not in attrs:
        attrs["id"] = elem_id
    if blob is not None:
        attrs.update(_decode_blob(blob))

    return Envelope(
        node_type=node_type,
        kind=kind,
        attrs=attrs,
        classes=list(elem.classes),
    )
