"""Fail unless a JUnit report ran at least one test and skipped none.

Usage::

    python scripts/require_no_skips.py e2e.xml
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main(argv: list[str]) -> int:
    """Print the counts and return non-zero when nothing ran or anything was skipped."""
    root = ET.parse(Path(argv[1])).getroot()  # noqa: S314 -- trusted local file
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    tests = sum(int(s.get("tests", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    print(f"{tests} tests, {skipped} skipped")
    if tests == 0 or skipped:
        print("live tests did not all run; check the e2e environment secrets", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
