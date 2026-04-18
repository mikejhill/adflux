# Extending adflux

## Adding an ADF node type

Most additions are pure config.

1. Edit `src/adflux/formats/adf/mapping.yaml`. Pick the right `kind`
   (block or inline) and `content_kind` (block / inline / none).

   ```yaml
   blockCard:
     pandoc: Div
     kind: block
     envelope_class: adf-block-card
     content_kind: none
     attrs:
       url: string
   ```

2. Add a minimal fixture to `tests/roundtrip/test_node_coverage.py`. The
   round-trip test will fail loudly if any node advertised in `mapping.yaml`
   has no fixture, so this is enforced.

3. Run `pytest`. If the round-trip is exact, you're done.

If the node has unusual structure (e.g., its children are a mix of block and
inline content), you may need to adjust `reader.py` or `writer.py`. The
existing `taskItem` / `decisionItem` paths are good references for inline
content under a block envelope.

## Adding a new format

If you need to support a custom format (not Markdown or ADF):

1. Implement a reader: `(source: str | bytes, *, profile, options) -> pf.Doc`.
2. Implement a writer: `(doc: pf.Doc, *, profile, options) -> str`.
3. Register both with `register_reader` / `register_writer`.

The IR (`panflute.Doc`) is the only contract. The ADF bridge itself is a
worked example of this approach — read it first.

## Adding a fidelity profile

Profiles are immutable dataclass records in `src/adflux/profiles.py`. To
add a new one:

1. Append a `Profile(...)` instance to the `_PROFILES` dict.
2. Pick semantics from the four boolean fields. If the existing fields are
   not enough, add a new field and consume it in
   `adflux.ir.profile_filter`.

## Releasing

Releases are automated via `.github/workflows/release.yml`:

1. Land changes on `main` using [Conventional Commits].
2. Run the **Release** workflow from the Actions tab.
3. `go-semantic-release` computes the next version, bumps `pyproject.toml`,
   builds sdist + wheel, creates a tagged GitHub Release, and publishes to
   PyPI via OIDC trusted publishing.

[Conventional Commits]: https://www.conventionalcommits.org/
