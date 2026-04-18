"""Convert a Markdown file to ADF JSON and print it.

Usage:
    python examples/md_to_adf.py [path/to/input.md]

If no path is given, reads from STDIN.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from adflux import convert


def main() -> int:
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    adf_json = convert(text, src="md", dst="adf")
    # Pretty-print the result.
    print(json.dumps(json.loads(adf_json), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
