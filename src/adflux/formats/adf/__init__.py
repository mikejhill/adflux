"""ADF (Atlassian Document Format) reader/writer registration.

The reader and writer implementations live in :mod:`adflux.formats.adf.reader`
and :mod:`adflux.formats.adf.writer`. This module wires them into the format
registry under the ``"adf"`` identifier.
"""

from __future__ import annotations

from adflux.formats import register_reader, register_writer
from adflux.formats.adf.reader import read_adf
from adflux.formats.adf.writer import write_adf

register_reader("adf", read_adf)
register_writer("adf", write_adf)
