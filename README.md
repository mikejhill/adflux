# adflux

[![CI](https://github.com/mikejhill/adflux/actions/workflows/ci.yml/badge.svg)](https://github.com/mikejhill/adflux/actions/workflows/ci.yml)
[![Release](https://github.com/mikejhill/adflux/actions/workflows/release.yml/badge.svg)](https://github.com/mikejhill/adflux/actions/workflows/release.yml)
[![PyPI](https://img.shields.io/pypi/v/adflux.svg)](https://pypi.org/project/adflux/)
[![Python](https://img.shields.io/pypi/pyversions/adflux.svg)](https://pypi.org/project/adflux/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Lossless conversion between Markdown and Atlassian Document Format (ADF), the JSON
document model of Jira and Confluence. Built so people and AI agents can read and write
Jira issues and Confluence pages as Markdown without losing panels, macros, emoji,
mentions, layouts or anything else.

```bash
uvx adflux to-adf page.md -p confluence > page.json
uvx adflux to-md issue.json -p jira
uvx adflux syntax            # the Markdown dialect, for people and agents
uvx adflux macros toc        # a Confluence macro's parameters and Markdown form
```

```python
from adflux import to_adf, to_markdown

doc = to_adf("> [!WARNING]\n> Deploy freeze :status[ACTIVE]{color=red}", "jira")
markdown = to_markdown(doc, "jira")
```

## What it does

| | |
|---|---|
| **Lossless** | Every schema-valid ADF document converts to Markdown and back to the same ADF (up to server-generated ids). Property tests generate random documents to hold this. |
| **Idiomatic** | Plain Markdown wherever it fits: `**bold**`, lists, GFM tables, `- [ ]` tasks, `> [!NOTE]` alerts, `<https://…>` smart links, `:smile:`. Directives (`:::expand{title=…}`, `:status[DONE]{color=green}`) cover the rest. |
| **Complete** | The ADF spec is generated from Atlassian's official JSON Schema, so every node, mark and attribute is known. Any node can be written as a directive named after it; raw ADF (```` ```adf ````) is the last resort. |
| **Product aware** | Profiles for Jira and Confluence: product emoji shortcuts, the Confluence macro catalog (111 macros with their parameters), native macro mapping (`:::info` → panel, `:::code` → code block), and warnings when Jira will not render something. |
| **Validated** | Output is checked against the spec; `adflux validate` adds the full official JSON Schema pass with readable paths. |

## Markdown at a glance

```markdown
# Release 2.4 :rocket:

Owner :mention[@Ada]{id=557058:…}, due :date[2026-12-31], state :status[AT RISK]{color=yellow}.

> [!INFO]
> Feature flags ship off by default.

- [x] Draft notes
- [ ] Sign-off

:::expand{title="Rollout plan"}
| Stage | Users |
|:------|------:|
| Canary | 1% |
| GA | 100% |
:::

::toc{maxLevel=2}
```

The full reference is [`src/adflux/syntax.md`](src/adflux/syntax.md) (also `adflux syntax`).
Design notes: [`docs/design.md`](docs/design.md).

## API

| Function | |
|---|---|
| `to_adf(markdown, profile="generic", strict=False, check=True)` | Markdown → ADF `dict`. `strict` turns warnings into errors. |
| `to_markdown(adf, profile="generic", keep_metadata=False)` | ADF (dict, JSON text, a Confluence `{"representation","value"}` body, or a `Node`) → Markdown. |
| `convert(source, src, dst, profile)` | Either direction by name (`"markdown"`, `"adf"`). |
| `validate(adf)` / `validation_issues(adf)` | Spec + JSON Schema validation. |
| `canonical(adf)` | Comparison form without server noise (`localId`, macro metadata, defaults). |
| `get_profile("jira" \| "confluence" \| "generic")` | Profiles; `profile.with_mentions(resolver)` resolves `@Name` mentions. |

## Development

```bash
uv sync --all-groups
uv run poe check                       # lint + typecheck + tests
HYPOTHESIS_PROFILE=thorough uv run pytest tests/roundtrip   # 2000 random documents
uv run python scripts/generate_spec.py # after updating src/adflux/adf/schema/full.json
uv run python scripts/build_profile_data.py
```

`tests/fixtures/live` holds ADF captured from live Jira and Confluence sites (every node
type as stored by each product, every Confluence macro, Jira wiki conversions). The e2e
suite (`poe test-e2e`, needs `.env`) creates real pages and issues and requires the
products to store adflux output unchanged.

## Releasing

Land Conventional Commits on `main`, then run the **Release** workflow:
`go-semantic-release` picks the version, builds, tags, and publishes to PyPI.

## License

MIT
