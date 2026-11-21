"""Generate ``src/adflux/adf/_spec.py`` from the vendored ADF JSON Schema.

The ADF JSON Schema expresses each node type as one or more definitions (for example
``paragraph_with_alignment_node`` and ``paragraph_with_no_marks_node``) and each content
model as ``anyOf`` groups of ``$ref`` s. This script folds those variants into one compact
spec per node and mark type: its attributes (type, enum, pattern, bounds, required), the
child node types it may contain, the marks it may carry, and whether it is a block or an
inline node. The converter, the generic directive codec and the validator read that table,
so supporting a new ADF node usually starts with refreshing the schema and running:

    uv run python scripts/generate_spec.py

``--check`` fails when the committed file is stale (CI runs it).
"""

from __future__ import annotations

import argparse
import json
import pprint
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "src" / "adflux" / "adf" / "schema" / "full.json"
SOURCE = ROOT / "src" / "adflux" / "adf" / "schema" / "SOURCE.json"
OUTPUT = ROOT / "src" / "adflux" / "adf" / "_spec.py"


def _ref(defs: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = defs[schema["$ref"].rsplit("/", 1)[1]]
    return schema


def _objects(defs: dict[str, Any], schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the object schemas (with ``properties``) a definition stands for."""
    schema = _ref(defs, schema)
    if "properties" in schema and "allOf" not in schema:
        return [schema]
    if "allOf" in schema:
        merged: dict[str, Any] = {"properties": {}, "required": []}
        for part in schema["allOf"]:
            for obj in _objects(defs, part):
                for key, value in obj.get("properties", {}).items():
                    merged["properties"].setdefault(key, value)
                    if key == "content" or key == "marks":
                        merged["properties"][key] = value  # later parts narrow content
                merged["required"] += obj.get("required", [])
        return [merged]
    found: list[dict[str, Any]] = []
    for option in schema.get("anyOf", []):
        found += _objects(defs, option)
    return found


def _type_name(obj: dict[str, Any]) -> str | None:
    enum = obj.get("properties", {}).get("type", {}).get("enum")
    return enum[0] if enum else None


def _attr(defs: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    schema = _ref(defs, schema)
    spec: dict[str, Any] = {}
    if "enum" in schema:
        spec["kind"] = "enum"
        spec["enum"] = list(schema["enum"])
    elif schema.get("type") in ("string", "number", "boolean", "integer", "array", "object"):
        spec["kind"] = "number" if schema["type"] == "integer" else schema["type"]
    else:
        spec["kind"] = "any"
    for key in ("pattern", "minimum", "maximum", "minLength"):
        if key in schema:
            spec[key] = schema[key]
    return spec


def _attrs(defs: dict[str, Any], obj: dict[str, Any]) -> list[tuple[dict[str, Any], set[str]]]:
    attrs = obj.get("properties", {}).get("attrs")
    if not attrs:
        return []
    variants = []
    for option in _ref(defs, attrs).get("anyOf", [attrs]):
        option = _ref(defs, option)
        props = {k: _attr(defs, v) for k, v in option.get("properties", {}).items()}
        variants.append((props, set(option.get("required", []))))
    return variants


def _children(defs: dict[str, Any], schema: dict[str, Any] | None, seen: set[str]) -> set[str]:
    if not schema:
        return set()
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[1]
        if name in seen:
            return set()
        seen = seen | {name}
    schema = _ref(defs, schema)
    if schema.get("type") == "array" or "items" in schema:
        items = schema.get("items", {})
        out: set[str] = set()
        for item in items if isinstance(items, list) else [items]:
            out |= _children(defs, item, seen)
        return out
    if "anyOf" in schema:
        out = set()
        for option in schema["anyOf"]:
            out |= _children(defs, option, seen)
        return out
    names = set()
    for obj in _objects(defs, schema):
        name = _type_name(obj)
        if name:
            names.add(name)
    return names


def build() -> dict[str, Any]:
    """Fold the schema into ``{"nodes": {...}, "marks": {...}}``."""
    defs = json.loads(SCHEMA.read_text(encoding="utf-8"))["definitions"]
    nodes: dict[str, Any] = {}
    marks: dict[str, Any] = {}
    for key in sorted(defs):
        for obj in _objects(defs, {"$ref": f"#/definitions/{key}"}):
            name = _type_name(obj)
            if not name:
                continue
            table = marks if key.endswith("_mark") else nodes
            entry = table.setdefault(name, {"attrs": {}, "required": None, "content": set(), "marks": set()})
            for props, required in _attrs(defs, obj) or [({}, set())]:
                for attr, spec in props.items():
                    old = entry["attrs"].get(attr)
                    if old and old != spec:
                        if old.get("kind") == "enum" and spec.get("kind") == "enum":
                            old["enum"] = sorted(set(old["enum"]) | set(spec["enum"]))
                        elif old.get("kind") != spec.get("kind"):
                            entry["attrs"][attr] = {"kind": "any"}
                    else:
                        entry["attrs"][attr] = spec
                entry["required"] = required if entry["required"] is None else entry["required"] & required
            props = obj.get("properties", {})
            if table is nodes:
                entry["content"] |= _children(defs, props.get("content"), set())
                entry["marks"] |= _children(defs, props.get("marks"), set())
                if "text" in props:
                    entry["text"] = True
                if "content" in obj.get("required", []):
                    entry["content_required"] = True
    inline = _children(defs, {"$ref": "#/definitions/inline_node"}, set()) | {"text"}
    for name, entry in nodes.items():
        entry["required"] = sorted(entry["required"] or [])
        entry["content"] = sorted(entry["content"])
        entry["marks"] = sorted(entry["marks"])
        entry["group"] = "inline" if name in inline else "block"
    for entry in marks.values():
        entry["required"] = sorted(entry["required"] or [])
        del entry["content"], entry["marks"]
    text_marks = set()
    for key, _schema in defs.items():
        for obj in _objects(defs, {"$ref": f"#/definitions/{key}"}):
            if _type_name(obj) == "text":
                text_marks |= _children(defs, obj.get("properties", {}).get("marks"), set())
    nodes["text"]["marks"] = sorted(text_marks or set(marks))
    return {"nodes": dict(sorted(nodes.items())), "marks": dict(sorted(marks.items()))}


def render() -> str:
    """Return the Python source of ``_spec.py``."""
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    data = build()
    body = pprint.pformat(data, width=100, sort_dicts=True)
    return (
        '"""ADF node and mark table generated from the ADF JSON Schema. Do not edit.\n\n'
        f"Source: {source['package']} {source['version']} ({source['file']}).\n"
        'Regenerate with ``uv run python scripts/generate_spec.py``.\n"""\n\n'
        "# ruff: noqa: E501\n"
        "from typing import Any\n\n"
        f"SCHEMA_SOURCE: dict[str, str] = {source!r}\n\n"
        f"SPEC: dict[str, Any] = {body}\n"
    )


def main() -> int:
    """Write or check the generated module."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the file is stale")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            print(f"{OUTPUT} is stale; run scripts/generate_spec.py", file=sys.stderr)
            return 1
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
