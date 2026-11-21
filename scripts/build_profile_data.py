"""Build the compact emoji and macro tables shipped in ``src/adflux/profiles/data``.

Inputs are captures from a live Atlassian Cloud site (``tests/fixtures/live``):

* ``emoji.json``: the standard and Atlassian emoji sets from ``/gateway/api/emoji/...``.
* ``confluence-macro-catalog.json``: every Confluence macro from the macro browser
  (``/wiki/plugins/macrobrowser/browse-macros.action?detailed=true``) with its parameters,
  plus the ADF Confluence produced for a minimal instance through
  ``/wiki/rest/api/contentbody/convert/atlas_doc_format``.

Run ``uv run python scripts/build_profile_data.py``; ``--check`` fails when stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "tests" / "fixtures" / "live"
DATA = ROOT / "src" / "adflux" / "profiles" / "data"


def emoji() -> dict[str, Any]:
    """Return ``{"standard": [[short, id, text], ...], "atlassian": [...]}``."""
    raw = json.loads((LIVE / "emoji.json").read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for group in ("standard", "atlassian"):
        rows = []
        for item in raw[group]:
            short = item["s"].strip(":")
            rows.append([short, item["id"], item["f"], 1 if item.get("h") else 0])
        out[group] = sorted(rows, key=lambda row: (row[0], row[1]))
    return out


def _node_of(adf: Any, inline: bool) -> dict[str, Any] | None:
    if not isinstance(adf, list) or not adf:
        return None
    node = adf[0]
    if node.get("type") == "paragraph":
        found = [c for c in node.get("content", []) if c.get("type") != "text"]
        if found:
            return found[0]
        return node if not inline else None
    return node


def macros() -> dict[str, Any]:
    """Return ``{name: macro}`` for every Confluence macro in the capture."""
    raw = json.loads((LIVE / "confluence-macro-catalog.json").read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for item in raw:
        name = item["name"]
        block = _node_of(item.get("adf_block"), False)
        node_type = block.get("type") if block else None
        if block and node_type in ("extension", "bodiedExtension", "inlineExtension"):
            key = block["attrs"].get("extensionKey")
            if key != name:  # converted to an "unsupported content" placeholder
                node_type = None
        params = []
        for p in item.get("params", []):
            entry: dict[str, Any] = {"name": p["n"], "type": p.get("t") or "string"}
            for short, long in (
                ("req", "required"),
                ("mul", "multiple"),
                ("d", "default"),
                ("e", "enum"),
                ("a", "aliases"),
                ("h", "hidden"),
            ):
                if short in p:
                    entry[long] = bool(p[short]) if short in ("req", "mul", "h") else p[short]
            params.append(entry)
        title = item.get("title") or name
        if title.startswith(("com.atlassian", "confluence.macros")) and title.endswith(".label"):
            title = name
        out[name] = {
            "title": title,
            "body": item.get("body") or "NONE",
            "output": item.get("output") or "BLOCK",
            "node": node_type,
            "hidden": bool(item.get("hidden")),
            "aliases": item.get("aliases") or [],
            "params": params,
        }
        if item.get("doc"):
            out[name]["docs"] = item["doc"]
    return dict(sorted(out.items()))


def render() -> dict[str, str]:
    """Return ``{filename: text}`` for every data file."""
    return {
        "emoji.json": json.dumps(emoji(), ensure_ascii=False, separators=(",", ":")) + "\n",
        "confluence_macros.json": json.dumps(macros(), ensure_ascii=False, indent=1) + "\n",
    }


def main() -> int:
    """Write or check the data files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for name, text in render().items():
        path = DATA / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
    if stale:
        print(f"stale: {', '.join(stale)}; run scripts/build_profile_data.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
