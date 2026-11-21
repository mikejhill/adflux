---
type: reference
status: active
authority: normative
criticality: normal
review:
  status: unreviewed
---

# Testing

adflux promises lossless round trips between Markdown and ADF. A conversion bug silently
damages Jira issues and Confluence pages, so each suite below catches a different class of
loss, and the gates keep the suites running.

## Suites

| Suite | Directory / marker | What it proves | Runs |
| --- | --- | --- | --- |
| Unit | `tests/unit`, `unit` | Each module against hand-built inputs: reader, writer, attributes, validation, profiles, CLI, every syntax-guide example | every PR, every OS and Python |
| Live captures | `tests/roundtrip/test_live.py`, `roundtrip` | ADF stored by real Jira and Confluence sites (every node, all Confluence macros, Jira wiki conversions) round-trips unchanged | every PR |
| Property | `tests/roundtrip/test_property.py`, `roundtrip` | Random schema-valid documents (`tests/strategies.py`) round-trip in every profile | every PR (100 examples), nightly (2000) |
| Generated files | `tests/unit/test_spec.py` | `adf/_spec.py` and profile data match their generators | every PR |
| End to end | `tests/e2e`, `e2e` | Jira and Confluence store adflux output unchanged, and their stored ADF round-trips | nightly (needs credentials) |
| Mutation | `mutmut`, 3 parallel shards | Tests notice behavior changes in `src/adflux` | after merge to main, weekly |

Suite markers come from the directory (`tests/conftest.py`); a new file needs no marker.
The e2e suite skips when credentials are absent, so it never fails a local run or a PR;
the nightly job fails instead when any live test skips (`scripts/require_no_skips.py`).

## Gates

| Gate | Threshold | Where |
| --- | --- | --- |
| Branch coverage, whole package | 84% (baseline 84.8%; raise, never lower) | `poe test`, every CI cell |
| Coverage of changed lines | 100% | `coverage` job (`diff-cover` against the base branch) |
| Strict types | every `ty` rule is an error, minus the documented exceptions | `poe typecheck` |
| Mutation score, per shard | reader 77%, writer 70%, core 60% (baseline 71.0% overall; raise, never lower) | `mutation` workflow |
| Built wheel | installs into a clean environment and converts a document | `check` job |

A mutation run that crashes, times out, or leaves mutants unchecked fails as an execution
failure; it never counts as a score result. Code that genuinely cannot run in tests takes
`# pragma: no cover` with a reason, reviewed like any other change.

## Running locally

```sh
uv run poe check             # format, lint, types, unit + round-trip suites with coverage
uv run poe test-unit         # or test-roundtrip
uv run poe test-deep         # 2000 random documents per property
uv run poe test-e2e          # live Jira and Confluence; copy .env.example to .env first
uv sync --group mutation && uv run poe mutation && uv run poe mutation-score
```

mutmut does not run on Windows; use WSL or let the workflow run it.

## Adding tests

- Bug fix: a failing regression in the narrowest suite first.
- New node, mark, or attribute: extend `tests/strategies.py` so the property tests draw it,
  and capture how Jira and Confluence store it in `tests/fixtures/live` (scrubbed).
- New Markdown syntax: add an example to `src/adflux/syntax.md`; `test_syntax_doc.py`
  converts every example both ways.
