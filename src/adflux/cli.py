"""Typer-based CLI for adflux.

Subcommands:

* ``adflux convert`` — convert between formats.
* ``adflux validate`` — validate a document (currently only ADF).
* ``adflux inspect-ast`` — dump the internal IR as JSON.
* ``adflux list-formats`` — list registered formats.
* ``adflux list-options`` — list available conversion options.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from adflux.api import convert as api_convert
from adflux.api import inspect_ast as api_inspect_ast
from adflux.api import list_formats as api_list_formats
from adflux.api import validate as api_validate
from adflux.errors import AdfluxError
from adflux.logging import configure_logging
from adflux.options import get_registry

app = typer.Typer(
    name="adflux",
    help="Pure-Python Markdown ↔ Atlassian Document Format (ADF) converter.",
    no_args_is_help=True,
    add_completion=False,
)


def _read_input(input_path: Path | None) -> str:
    if input_path is None:
        return sys.stdin.read()
    return input_path.read_text(encoding="utf-8")


def _write_output(text: str, output_path: Path | None) -> None:
    if output_path is None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        output_path.write_text(text, encoding="utf-8")


def _parse_options(raw: list[str] | None) -> dict[str, str]:
    """Parse ``--option key=value`` pairs into a dict."""
    if not raw:
        return {}
    result: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise typer.BadParameter(f"Option must be key=value, got: {item!r}")
        key, value = item.split("=", 1)
        result[key.strip()] = value.strip()
    return result


@app.command("convert")
def convert_cmd(
    input_path: Annotated[
        Path | None,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Input file (or stdin)."),
    ] = None,
    src: Annotated[str, typer.Option("--from", "-f", help="Source format.")] = "md",
    dst: Annotated[str, typer.Option("--to", "-t", help="Target format.")] = "adf",
    option: Annotated[
        list[str] | None,
        typer.Option(
            "--option",
            "-O",
            help="Conversion option as key=value (repeatable).",
        ),
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output file (or stdout).")
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose logging.")] = False,
) -> None:
    """Convert INPUT_PATH (or stdin) from ``--from`` to ``--to``."""
    configure_logging(level=10 if verbose else 20)
    try:
        source = _read_input(input_path)
        opts = _parse_options(option)
        result = api_convert(source, src=src, dst=dst, options=opts)
        _write_output(result, output)
    except AdfluxError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


@app.command("validate")
def validate_cmd(
    input_path: Annotated[
        Path | None,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Input file (or stdin)."),
    ] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="Format to validate.")] = "adf",
    option: Annotated[
        list[str] | None,
        typer.Option(
            "--option",
            "-O",
            help="Validation option as key=value (repeatable).",
        ),
    ] = None,
) -> None:
    """Validate a document (currently only meaningful for ADF)."""
    try:
        source = _read_input(input_path)
        opts = _parse_options(option)
        api_validate(source, fmt=fmt, options=opts)
        typer.secho("ok", fg=typer.colors.GREEN)
    except AdfluxError as exc:
        typer.secho(f"invalid: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command("inspect-ast")
def inspect_ast_cmd(
    input_path: Annotated[
        Path | None,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Input file (or stdin)."),
    ] = None,
    src: Annotated[str, typer.Option("--from", "-f", help="Source format.")] = "md",
) -> None:
    """Parse INPUT_PATH with the ``--from`` reader and dump the internal IR as JSON."""
    try:
        source = _read_input(input_path)
        typer.echo(api_inspect_ast(source, src=src))
    except AdfluxError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


@app.command("list-formats")
def list_formats_cmd() -> None:
    """List registered format identifiers."""
    typer.echo("formats:")
    for fmt in api_list_formats():
        typer.echo(f"  - {fmt}")


@app.command("list-options")
def list_options_cmd() -> None:
    """List available conversion options with descriptions and defaults."""
    registry = get_registry()
    for defn in registry.all():
        choices = ", ".join(defn.choices) if defn.choices else "free-form"
        typer.echo(f"{defn.name}")
        typer.echo(f"  choices:  {choices}")
        typer.echo(f"  default:  {defn.default}")
        typer.echo(f"  {defn.description}")
        typer.echo()


if __name__ == "__main__":
    app()
