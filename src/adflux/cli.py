"""``adflux`` command line: convert, validate, and look up macros, emoji and syntax."""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from importlib import resources
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from adflux.adf.model import load
from adflux.adf.validate import validation_issues
from adflux.api import to_adf, to_markdown
from adflux.errors import AdfluxError, AdfValidationError
from adflux.markdown.reader import ConversionWarning
from adflux.profiles import get_profile

PROFILES = ("generic", "jira", "confluence")


def _version() -> str:
    try:
        return version("adflux")
    except PackageNotFoundError:  # pragma: no cover - source checkout
        return "0+unknown"


def _read(path: str | None) -> str:
    if path in (None, "-"):
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _write(text: str, path: str | None) -> None:
    if path in (None, "-"):
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    else:
        Path(path).write_text(text, encoding="utf-8")


def _cmd_to_adf(args: argparse.Namespace) -> int:
    doc = to_adf(_read(args.input), args.profile, strict=args.strict)
    text = json.dumps(doc, ensure_ascii=False, indent=None if args.compact else 2)
    _write(text, args.output)
    return 0


def _cmd_to_md(args: argparse.Namespace) -> int:
    _write(to_markdown(_read(args.input), args.profile, keep_metadata=args.keep_metadata), args.output)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    source = _read(args.input)
    fmt = args.format
    if fmt == "auto":
        fmt = "adf" if source.lstrip().startswith("{") else "markdown"
    if fmt == "markdown":
        to_adf(source, args.profile, strict=args.strict)
        issues = []
    else:
        issues = validation_issues(load(source), schema=not args.no_schema)
    if issues:
        for issue in issues:
            print(f"{issue.path}: {issue.message}", file=sys.stderr)
        return 1
    print("valid", file=sys.stderr)
    return 0


def _example(name: str, info: dict[str, Any]) -> str:
    params = [p for p in info["params"] if p.get("required") and p["name"] != "(default)"]
    attrs = " ".join(f"{p['name']}={p.get('default') or '...'}" for p in params)
    default = next((p for p in info["params"] if p["name"] == "(default)"), None)
    label = "[...]" if default else ""
    tail = label + ("{" + attrs + "}" if attrs else "")
    if info["adf"] == "inlineExtension":
        return f":{name}{tail or '{}'}"
    if info["body"] != "none":
        return f":::{name}{tail}\nbody\n:::"
    return f"::{name}{tail}"


def _cmd_macros(args: argparse.Namespace) -> int:
    catalog = get_profile("confluence").macros
    if args.name:
        macro = catalog.get(args.name)
        if macro is None:
            print(f"unknown macro {args.name!r}; run 'adflux macros' for the list", file=sys.stderr)
            return 1
        info = macro.describe()
        info["markdown"] = _example(macro.name, info)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    rows = [m for m in catalog if args.all or not m.hidden]
    if args.json:
        print(json.dumps([{**m.describe(), "markdown": _example(m.name, m.describe())} for m in rows], indent=2))
        return 0
    for macro in rows:
        info = macro.describe()
        print(f"{macro.name:28} {info['adf']:16} {macro.title}")
    return 0


def _cmd_emoji(args: argparse.Namespace) -> int:
    profile = get_profile(args.profile)
    aliases = {k: v for k, v in profile.emoticons.items() if args.query.lower().strip(":") in k}
    for alias, target in sorted(aliases.items()):
        print(f":{alias}:  -> :{target}:  ({profile.name} shortcut)")
    for emoji in profile.emoji.search(args.query, limit=args.limit):
        print(f":{emoji.short_name}:  {emoji.text}  ({emoji.id})")
    return 0


def _cmd_syntax(args: argparse.Namespace) -> int:
    del args
    sys.stdout.write(resources.files("adflux").joinpath("syntax.md").read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="adflux",
        description="Convert between Markdown and Atlassian Document Format (ADF).",
        epilog="Run 'adflux syntax' for the Markdown dialect.",
    )
    parser.add_argument("--version", action="version", version=f"adflux {_version()}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def common(p: argparse.ArgumentParser, *, output: bool = True) -> None:
        p.add_argument("input", nargs="?", help="input file (default: stdin)")
        p.add_argument("-p", "--profile", choices=PROFILES, default="generic", help="product profile")
        if output:
            p.add_argument("-o", "--output", help="output file (default: stdout)")

    p = sub.add_parser("to-adf", aliases=["md2adf"], help="Markdown -> ADF JSON")
    common(p)
    p.add_argument("--strict", action="store_true", help="fail on conversion warnings")
    p.add_argument("--compact", action="store_true", help="single-line JSON")
    p.set_defaults(func=_cmd_to_adf)

    p = sub.add_parser("to-md", aliases=["adf2md"], help="ADF JSON -> Markdown")
    common(p)
    p.add_argument("--keep-metadata", action="store_true", help="keep macro metadata (adf.meta)")
    p.set_defaults(func=_cmd_to_md)

    p = sub.add_parser("validate", help="validate ADF JSON or adflux Markdown")
    common(p, output=False)
    p.add_argument("-f", "--format", choices=("auto", "adf", "markdown"), default="auto")
    p.add_argument("--strict", action="store_true", help="Markdown: fail on conversion warnings")
    p.add_argument("--no-schema", action="store_true", help="ADF: skip the JSON Schema pass")
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("macros", help="list Confluence macros or show one")
    p.add_argument("name", nargs="?")
    p.add_argument("--all", action="store_true", help="include hidden macros")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_macros)

    p = sub.add_parser("emoji", help="search emoji short names")
    p.add_argument("query")
    p.add_argument("-p", "--profile", choices=PROFILES, default="generic")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.set_defaults(func=_cmd_emoji)

    p = sub.add_parser("syntax", help="print the Markdown dialect reference")
    p.set_defaults(func=_cmd_syntax)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; return the exit code."""
    args = build_parser().parse_args(argv)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConversionWarning)
        try:
            return int(args.func(args))
        except AdfValidationError as error:
            for issue in error.issues:
                print(f"error: {issue.path}: {issue.message}", file=sys.stderr)
            return 1
        except BrokenPipeError:
            return 0
        except (AdfluxError, OSError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        finally:
            for item in caught:
                prefix = "warning" if issubclass(item.category, ConversionWarning) else item.category.__name__
                print(f"{prefix}: {item.message}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
