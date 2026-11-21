---
type: reference
status: active
authority: informative
criticality: normal
review:
  status: unreviewed
---

# Contributing

Use Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). Run `uv sync`, then
`uv run poe check` before opening a pull request. It runs formatting, lint, strict type
checks, and the unit and round-trip suites with the branch-coverage gate. See
[testing](docs/testing.md) for the suites and gates.

- Use a Conventional Commit title for every pull request (`feat:`, `fix:`, `docs:`, …;
  `!` for breaking changes). CI checks it, squash merges make it the commit message,
  and release-please derives versions and the changelog from it. See
  [releasing](docs/releasing.md).
- Keep 100% coverage of changed lines and never lower the coverage or mutation floors.
- Add a failing regression before changing conversion behavior. A lossless round trip
  is the contract: a new node, mark, or attribute needs a round-trip test, and new
  Markdown syntax needs an example in [`src/adflux/syntax.md`](src/adflux/syntax.md).
- `src/adflux/adf/_spec.py` and `src/adflux/profiles/data/` are generated. Change the
  generators in `scripts/` and rerun them; a test fails when they are stale.
- Never commit credentials or unscrubbed captures from real sites. The live e2e suite
  reads its settings from `.env` (see `.env.example`).
