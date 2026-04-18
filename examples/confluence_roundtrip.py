"""Round-trip an ADF document through the internal IR and assert equivalence.

This is the recommended way to verify that a real Confluence ADF page can
travel through adflux without losing information.

Usage:
    python examples/confluence_roundtrip.py [path/to/page.adf.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from adflux.formats.adf.reader import read_adf
from adflux.formats.adf.writer import write_adf
from adflux.profiles import resolve_profile


def main() -> int:
    """Run a Confluence round-trip demo against a sample ADF document."""
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("sample.adf.json")
    original = json.loads(src.read_text(encoding="utf-8"))

    profile = resolve_profile("strict-adf")
    ir = read_adf(json.dumps(original), profile=profile, options={})
    out = json.loads(write_adf(ir, profile=profile, options={}))

    if original == out:
        print("PASS: lossless ADF round-trip")
        return 0

    print("FAIL: structural difference detected")
    print("--- input  ---")
    print(json.dumps(original, indent=2, sort_keys=True))
    print("--- output ---")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
