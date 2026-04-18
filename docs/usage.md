# Usage

## Installation

```bash
pip install adflux
```

Requires Python ≥ 3.11. Pure Python — no system dependencies.

## Library API

```python
from adflux import convert, validate, inspect_ast, list_formats

# Markdown → ADF JSON
adf_json = convert(open("notes.md").read(), src="md", dst="adf")

# ADF JSON → Markdown, dropping ADF-only constructs
md = convert(adf_json, src="adf", dst="md", options={"envelopes": "drop"})

# Validate ADF input
validate(adf_json, fmt="adf")        # raises InvalidADFError on failure

# Validate for Jira compatibility
validate(adf_json, fmt="adf", options={"jira-strict": "true"})

# Inspect the IR
print(inspect_ast(md, src="md"))

# Discover available formats
print(list_formats())                # ['adf', 'markdown', 'panflute', 'pf']
```

`convert()` keyword arguments:

| Arg       | Type                          | Default   | Notes                                          |
| --------- | ----------------------------- | --------- | ---------------------------------------------- |
| `source`  | `str \| bytes`                | required  | Document text or JSON.                         |
| `src`     | `str`                         | required  | One of `list_formats()`.                       |
| `dst`     | `str`                         | required  | One of `list_formats()`.                       |
| `options` | `dict[str, str] \| Options`   | `None`    | See [`options.md`](options.md).                |

## CLI

The wheel installs an `adflux` script.

```bash
adflux --help
adflux convert  --from md  --to adf      README.md > readme.adf.json
adflux convert  --from adf --to md       input.json
adflux convert  --from adf --to md       --option envelopes=drop  input.json
adflux validate input.adf.json
adflux validate input.adf.json --option jira-strict=true
adflux inspect-ast --from md README.md | jq .
adflux list-formats
adflux list-options
```

Reading from stdin and writing to stdout:

```bash
cat doc.md | adflux convert --from md --to adf > doc.adf.json
```

## Conversion options

| Option         | Choices                        | Default  | Behavior                                             |
| -------------- | ------------------------------ | -------- | ---------------------------------------------------- |
| `envelopes`    | `keep`, `drop`, `keep-strict`  | `keep`   | How ADF envelope nodes are handled on lossy targets. |
| `jira-strict`  | `true`, `false`                | `false`  | Reject non-Jira ADF nodes during serialization.      |

See [`options.md`](options.md) for a worked example of each.

## Errors

```python
from adflux import convert
from adflux.errors import (
    AdfluxError,
    InvalidADFError,
    UnsupportedFormatError,
    UnrepresentableNodeError,
)

try:
    convert("{}", src="adf", dst="md")
except InvalidADFError as exc:
    ...
```

## Extending — add a new ADF node type

1. Open `src/adflux/formats/adf/mapping.yaml`.
2. Add a stanza:

   ```yaml
   blockCard:
     pandoc: Div  # Internal IR node kind (from panflute AST classes)
     kind: block
     envelope_class: adf-block-card
     content_kind: none
     attrs:
       url: string
   ```
3. Add a fixture in `tests/roundtrip/test_node_coverage.py`.
4. `pytest -q` — no Python changes required.

See [`extending.md`](extending.md) for adding entirely new formats.

## Examples

Runnable examples are in [`examples/`](../examples):

- [`md_to_adf.py`](../examples/md_to_adf.py) — minimal library use.
- [`adf_to_markdown.py`](../examples/adf_to_markdown.py) — option selection.
- [`confluence_roundtrip.py`](../examples/confluence_roundtrip.py) — verify
  that a Confluence ADF document survives a round-trip through the internal IR.
- [`sample.adf.json`](../examples/sample.adf.json) — a representative ADF
  document exercising panels, status, code blocks, and tables.
