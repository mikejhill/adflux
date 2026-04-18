"""ADF JSON-schema validation.

We bundle a lightweight schema describing ADF's top-level shape (``version``,
``type == "doc"``, ``content`` list of objects with a ``type`` field) plus a
recursive node structure that permits arbitrary node types. This is *not* a
strict schema for every ADF node; Atlassian's canonical schemas are large and
evolve. Strict per-node validation is available via the mapping table and is
layered on top as future work.

If ``ADFLUX_ADF_SCHEMA`` env var is set, that path is used instead; this lets
users pin to a specific upstream schema version.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema import exceptions as jsex

from adflux.errors import InvalidADFError

_SCHEMA_PATH = Path(__file__).with_name("schema") / "adf-minimal.schema.json"


def _load_schema() -> dict[str, Any]:
    override = os.environ.get("ADFLUX_ADF_SCHEMA")
    path = Path(override) if override else _SCHEMA_PATH
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise InvalidADFError(f"schema file {path} is not a JSON object")
    return data


_validator: Draft202012Validator | None = None


def _get_validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        _validator = Draft202012Validator(_load_schema())
    return _validator


def validate_adf(doc: str | bytes | dict[str, Any]) -> None:
    """Validate an ADF document. Raises :class:`InvalidADFError` on failure."""
    if isinstance(doc, (str, bytes)):
        try:
            parsed = json.loads(doc)
        except json.JSONDecodeError as exc:
            raise InvalidADFError(f"invalid JSON: {exc}") from exc
    else:
        parsed = doc

    validator = _get_validator()
    errors = sorted(validator.iter_errors(parsed), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    first = errors[0]
    pointer = "/" + "/".join(str(p) for p in first.absolute_path)
    raise InvalidADFError(
        f"ADF schema violation at {pointer}: {first.message}",
        pointer=pointer,
        validator_errors=[_summarize(err) for err in errors],
    )


def _summarize(err: jsex.ValidationError) -> dict[str, Any]:
    return {
        "path": "/" + "/".join(str(p) for p in err.absolute_path),
        "message": err.message,
        "validator": err.validator,
    }
