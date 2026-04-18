# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Releases are produced automatically from
[Conventional Commits](https://www.conventionalcommits.org/) by
`go-semantic-release` — see [`.github/workflows/release.yml`](.github/workflows/release.yml).

## [Unreleased]

## [0.3.0] — 2026-04-18

### Added

- `validate` API and CLI now accept `--option` / `options=` for applying
  options during validation (e.g. `jira-strict=true`).
- Full `CHANGELOG.md` covering all releases.

## [0.2.0] — 2026-04-17

### Added

- Flexible key=value **Options** system replacing the former Profile
  dataclass (`envelopes=keep|drop|keep-strict`, `jira-strict=true|false`).
- `adflux list-options` CLI subcommand for self-documenting option
  definitions.
- `--option key=value` (`-O`) repeatable flag on `convert`.
- **Panflute JSON** registered as a first-class input/output format
  (aliases: `panflute`, `pf`).
- `jira-strict` validation gate in the ADF writer rejects node types
  unsupported by Jira's description-field ADF profile.
- New `docs/options.md` with full option documentation.

### Changed

- Losslessness claims updated in `design.md`: MD ↔ ADF round-trips are
  lossless under `envelopes=keep`; only non-semantic whitespace may differ.
- All documentation, examples, and tests migrated from profiles to options.

### Removed

- **BREAKING:** `--profile` CLI flag and `profile=` API parameter removed.
- `profiles.py` module deleted.
- `docs/profiles.md` deleted (replaced by `docs/options.md`).
- All AsciiDoc references and stale Pandoc docstrings removed.

### Fixed

- Mermaid parse error in `docs/e2e-testing.md` (curly braces in URL).
- Losslessness claims corrected in `design.md`.

## [0.1.1] — 2026-04-17

### Fixed

- Stale `DocconvError` import in `usage.md` errors example.
- Mermaid diagrams and table rendering in `design.md` and `usage.md`.

### Changed

- E2E environment variables namespaced with `ADFLUX_E2E_` prefix.
- Expanded Jira E2E fixture coverage.

## [0.1.0] — 2026-04-17

### Added

- Initial public release.
- Pure-Python **Markdown (CommonMark + GFM)** reader (via `markdown-it-py`)
  and writer (hand-rolled CommonMark+GFM serializer).
- Custom bidirectional bridge for **Atlassian Document Format (ADF)** driven
  by a declarative `mapping.yaml` (22+ node types).
- Lossless envelope convention (`Div`/`Span` with `adf-*` classes plus a
  base64-JSON blob attribute) and a universal `adf-raw` fallback.
- Three fidelity profiles: `strict-adf`, `pretty-md`, `fail-loud`.
- Markdown writer renders ADF macros as **idiomatic Markdown** (GitHub
  alerts, `<details>`, autolinks, GFM task lists) with HTML-comment markers
  as a fallback, while preserving lossless MD ↔ ADF round-trips.
- ADF JSON Schema validation on read and write.
- Typer-based CLI (`adflux convert`, `validate`, `inspect-ast`,
  `list-formats`).
- 90+ unit, integration, round-trip, and property-based tests.
- E2E tests against Confluence Cloud and Jira Cloud (parent-page nesting,
  Jira issue creation).
- CI, E2E, and Release GitHub Actions workflows.
- PyPI-ready `pyproject.toml` with Trusted Publisher configuration.

[Unreleased]: https://github.com/mikejhill/adflux/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/mikejhill/adflux/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mikejhill/adflux/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/mikejhill/adflux/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/mikejhill/adflux/releases/tag/v0.1.0
