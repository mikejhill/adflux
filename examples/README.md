# Examples

Runnable scripts demonstrating `adflux` from the library API.

| Script                        | What it shows                                                |
| ----------------------------- | ------------------------------------------------------------ |
| `md_to_adf.py`                | Convert a Markdown file (or stdin) to ADF JSON.              |
| `adf_to_markdown.py`          | Render `sample.adf.json` to Markdown under each profile.     |
| `confluence_roundtrip.py`     | Verify lossless ADF → IR → ADF round-tripping.               |

Run them from the repo root after installing the package:

```bash
pip install -e ".[dev]"

python examples/md_to_adf.py README.md
python examples/adf_to_markdown.py
python examples/confluence_roundtrip.py
```

`sample.adf.json` is a synthetic ADF document covering a representative slice
of the ADF schema: headings, paragraphs with inline marks, a `panel`,
`taskList` items, a `codeBlock` with language, an inline `status`, and a
`table` with headers.
