# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Releases are produced automatically from
[Conventional Commits](https://www.conventionalcommits.org/) by
`go-semantic-release` — see [`.github/workflows/release.yml`](.github/workflows/release.yml).

## [Unreleased]

### Added
- Initial public release.
- Pure-Python **Markdown (CommonMark + GFM)** reader (via `markdown-it-py`) and
  writer (hand-rolled CommonMark+GFM serializer).
- Custom bidirectional bridge for **Atlassian Document Format (ADF)** driven by
  a declarative `mapping.yaml` (22+ node types).
- Lossless envelope convention (`Div`/`Span` with `adf-*` classes plus a
  base64-JSON blob attribute) and a universal `adf-raw` fallback.
- Three fidelity profiles: `strict-adf`, `pretty-md`, `fail-loud`.
- Markdown writer renders ADF macros as **idiomatic Markdown** (GitHub
  alerts, `<details>`, autolinks, GFM task lists) with HTML-comment
  markers as a fallback, while preserving lossless `MD ↔ ADF` round-trips.
- ADF JSON Schema validation on read and write.
- Typer-based CLI (`adflux convert`, `validate`, `inspect-ast`, `list-formats`).
- 90+ unit, integration, round-trip, and property-based tests.
