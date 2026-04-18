"""Convert an ADF document to Markdown using each envelope option.

Usage:
    python examples/adf_to_markdown.py [path/to/input.adf.json]

Defaults to ``examples/sample.adf.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from adflux import convert
from adflux.errors import UnrepresentableNodeError

OPTIONS = [
    {"envelopes": "keep"},
    {"envelopes": "drop"},
    {"envelopes": "keep-strict"},
]


def main() -> int:
    """Convert a sample ADF JSON file (or argv[1]) to Markdown on stdout."""
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("sample.adf.json")
    adf = src.read_text(encoding="utf-8")

    for opts in OPTIONS:
        label = ", ".join(f"{k}={v}" for k, v in opts.items())
        print(f"\n===== options: {label} =====\n")
        try:
            print(convert(adf, src="adf", dst="markdown", options=opts))
        except UnrepresentableNodeError as exc:
            print(f"[keep-strict raised] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
