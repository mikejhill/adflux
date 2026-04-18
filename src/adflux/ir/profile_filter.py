"""Apply conversion options to a panflute Doc before writing to a lossy target.

The options filter mutates the AST according to the ``envelopes`` option:

- ``keep``: envelopes are preserved so lossy-target writers (Markdown) can
  render them via the format's idiomatic syntax (pretty rendering with
  GitHub alerts, HTML comments, etc.). No mutation is performed.
- ``drop``: envelopes are silently dropped; block envelopes are replaced by
  their children, inline envelopes collapse to their content, and content-less
  envelopes are removed entirely.
- ``keep-strict``: the first envelope encountered causes
  :class:`UnrepresentableNodeError` to be raised, carrying the node type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adflux.errors import UnrepresentableNodeError
from adflux.ir.envelope import ENVELOPE_CLASS_PREFIX, is_envelope, unpack_envelope

if TYPE_CHECKING:
    import panflute as pf

    from adflux.options import Options


def apply_options(doc: pf.Doc, options: Options) -> pf.Doc:
    """Return ``doc`` after applying ``options`` semantics in-place."""
    import panflute as pf

    envelopes = options["envelopes"]

    if envelopes == "keep":
        return doc

    def _walk(elem: pf.Element, _doc: pf.Doc) -> pf.Element | list[pf.Element] | None:
        if not is_envelope(elem):
            return None
        if not isinstance(elem, (pf.Div, pf.Span)):
            return None
        env = unpack_envelope(elem)
        if envelopes == "keep-strict":
            raise UnrepresentableNodeError(env.node_type, "lossy-target")
        if envelopes == "drop":
            if isinstance(elem, pf.Span):
                return list(elem.content) if elem.content else []
            children = list(elem.content)
            return children if children else []
        return None

    doc.walk(_walk)
    return doc


__all__ = ["ENVELOPE_CLASS_PREFIX", "apply_options"]
