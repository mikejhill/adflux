"""Typer-based CLI for adflux.

Subcommands:

* ``adflux convert`` — convert between formats.
* ``adflux validate`` — validate a document (currently only ADF).
* ``adflux inspect-ast`` — dump the internal IR as JSON.
* ``adflux list-formats`` — list registered formats and profiles.
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
from adflux.profiles import all_profile_names

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


@app.command("convert")
def convert_cmd(
    input_path: Annotated[
        Path | None,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Input file (or stdin)."),
    ] = None,
    src: Annotated[str, typer.Option("--from", "-f", help="Source format.")] = "md",
    dst: Annotated[str, typer.Option("--to", "-t", help="Target format.")] = "adf",
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help=f"Fidelity profile: {', '.join(all_profile_names())}.",
        ),
    ] = "strict-adf",
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output file (or stdout).")
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose logging.")] = False,
) -> None:
    """Convert INPUT_PATH (or stdin) from ``--from`` to ``--to``."""
    configure_logging(level=10 if verbose else 20)
    try:
        source = _read_input(input_path)
        result = api_convert(source, src=src, dst=dst, profile=profile)
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
) -> None:
    """Validate a document (currently only meaningful for ADF)."""
    try:
        source = _read_input(input_path)
        api_validate(source, fmt=fmt)
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
    """List registered formats and fidelity profiles."""
    typer.echo("formats:")
    for fmt in api_list_formats():
        typer.echo(f"  - {fmt}")
    typer.echo("profiles:")
    for name in all_profile_names():
        typer.echo(f"  - {name}")


if __name__ == "__main__":
    app()
