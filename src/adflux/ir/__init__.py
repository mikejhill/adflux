"""Internal intermediate representation (IR).

adflux uses the panflute AST as its IR. This package re-exports the types
we touch most often and provides helpers for the ADF-envelope convention
that guarantees lossless round-tripping of ADF-specific constructs
(panels, macros, mentions, etc.) through the IR.
"""

from __future__ import annotations

from adflux.ir.envelope import (
    ENVELOPE_CLASS_PREFIX,
    ENVELOPE_RAW_CLASS,
    Envelope,
    is_envelope,
    pack_envelope,
    unpack_envelope,
)

__all__ = [
    "ENVELOPE_CLASS_PREFIX",
    "ENVELOPE_RAW_CLASS",
    "Envelope",
    "is_envelope",
    "pack_envelope",
    "unpack_envelope",
]
