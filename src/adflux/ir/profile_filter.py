"""Apply a fidelity profile to a panflute Doc before writing to a lossy target.

The profile filter mutates the AST according to the chosen :class:`Profile`:

- ``strict-adf``: envelopes are preserved so lossy-target writers (markdown,
  asciidoc) can render them via the format's idiomatic syntax (Markdown
  pretty rendering, AsciiDoc admonitions, …). No mutation is performed.
- ``pretty-md``: envelopes are silently dropped; block envelopes are replaced by
  their children, inline envelopes collapse to their content, and content-less
  envelopes are removed entirely.
- ``fail-loud``: the first envelope encountered causes
  :class:`UnrepresentableNodeError` to be raised, carrying the node type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adflux.errors import UnrepresentableNodeError
from adflux.ir.envelope import ENVELOPE_CLASS_PREFIX, is_envelope, unpack_envelope

if TYPE_CHECKING:
    import panflute as pf

    from adflux.profiles import Profile


def apply_profile(doc: pf.Doc, profile: Profile) -> pf.Doc:
    """Return ``doc`` after applying ``profile`` semantics in-place."""
    import panflute as pf

    if profile.preserve_envelopes and not profile.fail_on_unrepresentable:
        return doc

    def _walk(elem: pf.Element, _doc: pf.Doc) -> pf.Element | list[pf.Element] | None:
        if not is_envelope(elem):
            return None
        env = unpack_envelope(elem)
        if profile.fail_on_unrepresentable:
            raise UnrepresentableNodeError(env.node_type, "lossy-target")
        if profile.drop_unrepresentable:
            if isinstance(elem, pf.Span):
                return list(elem.content) if elem.content else []
            children = list(elem.content)
            return children if children else []
        return None

    doc.walk(_walk)
    return doc


__all__ = ["ENVELOPE_CLASS_PREFIX", "apply_profile"]
