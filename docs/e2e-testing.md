# End-to-end Confluence tests

The `tests/e2e/` suite verifies adflux against a **live Confluence Cloud
site** by uploading converted ADF, downloading it back, and asserting both
the ADF structure and the round-tripped Markdown survive the trip.

## What it covers

The flow per fixture is:

```mermaid
flowchart LR
  MD[Markdown fixture] -->|adflux MD->ADF| ADF1[ADF JSON]
  ADF1 -->|POST /wiki/api/v2/pages| Conf{{Confluence}}
  Conf -->|GET /wiki/api/v2/pages/{id}| ADF2[ADF JSON downloaded]
  ADF2 -->|adflux ADF->MD| MD2[Markdown round-trip]
  ADF1 -. structural compare .-> ADF2
  MD -. word-bag compare .-> MD2
```

Fixtures live under `tests/e2e/fixtures/`:

| File         | Exercises                                                   |
| ------------ | ----------------------------------------------------------- |
| `basic.md`   | Headings, marks, lists, tables, code, blockquote, hr.       |
| `panels.md`  | All five Confluence panel macros (info/note/warning/...).   |
| `mixed.md`   | Inline `status` macros, `expand` blocks, multi-language code. |

## Configuration

The suite reads `.env` at the project root (gitignored). Copy the template:

```bash
cp .env.example .env
$EDITOR .env
```

Required keys:

| Variable                | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `CONFLUENCE_SITE`       | Cloud hostname, e.g. `acme.atlassian.net`            |
| `CONFLUENCE_EMAIL`      | Atlassian account email (Basic-auth user)            |
| `CONFLUENCE_API_TOKEN`  | API token from id.atlassian.com                      |
| `CONFLUENCE_SPACE_KEY`  | Space to create test pages in (or `..._SPACE_ID`)    |
| `ADFLUX_E2E_KEEP_PAGES`| `true` keeps pages after each test (default deletes) |

If any required key is missing, or the credentials don't authenticate, the
whole module **skips cleanly** — it never fails CI when un-configured.

## Running

The repository's [poethepoet](https://poethepoet.natn.io/) tasks wrap
the most common invocations:

```bash
poe test-e2e     # tests/e2e -v
poe test         # everything except e2e
poe test-all     # everything, including e2e
```

Or invoke `pytest` directly:

```bash
pytest tests/e2e -v
pytest -m e2e
pytest --ignore=tests/e2e   # skip live tests
```

Each test creates a uniquely-named page (`adflux E2E [<run-id>] <fixture>`),
verifies it, and deletes it on teardown. Set `ADFLUX_E2E_KEEP_PAGES=true`
in `.env` to leave pages on the site for manual inspection.

## What the assertions guarantee

For every fixture the test guarantees:

1. `adflux` produces ADF that **passes the JSON-schema validator**.
2. The ADF contains the **required node types** for the fixture (e.g.
   `panel` must appear in the panels fixture).
3. **Confluence accepts the upload** (no 4xx from
   `POST /wiki/api/v2/pages` with `representation=atlas_doc_format`).
4. The ADF **fetched back** still contains every required node type — i.e.
   Confluence didn't drop the macro.
5. The ordered text content of the uploaded ADF equals the fetched ADF
   after stripping volatile attributes (`localId`, etc.).
6. `adflux` ADF→MD on the fetched document is **token-equivalent** to the
   original Markdown (allowing per-fixture ignores for envelope syntax and
   Confluence's known language-alias normalization, e.g. `bash`↔`shell`).

## CI

E2E tests run on demand only — they need a real Confluence site and
network access. The default `ci.yml` workflow runs
`pytest --ignore=tests/e2e`. A separate workflow (or manual `poe test-e2e`
invocation) can be wired up once secrets are stored in the repo's GitHub
Actions environment.

## Macro coverage

The current fixtures exercise the following ADF macro families:

| Fixture                        | Nodes covered                                                              |
| ------------------------------ | -------------------------------------------------------------------------- |
| `basic.md`                     | headings, paragraphs, lists, code blocks, tables, blockquotes, rules       |
| `panels.md`                    | `panel` (info / note / warning / success / error)                          |
| `mixed.md`                     | `panel` + `expand` + inline `status` + multi-language code blocks          |
| `inline-macros.md`             | `status` (all colors), `date`, `emoji`, `inlineCard`                       |
| `task-decision-lists.md`       | `taskList` / `taskItem` (TODO/DONE), `decisionList` / `decisionItem`       |
| `layouts.md`                   | `layoutSection` / `layoutColumn` (2- and 3-column layouts)                 |
| `smart-cards.md`               | `inlineCard`, `blockCard`, `embedCard`                                     |

`extension` / `bodiedExtension` / `inlineExtension` are demonstrated in
`examples/extensions.md` but **not** included in the live E2E suite —
Confluence's REST API rejects extension nodes whose `extensionKey` /
`extensionType` aren't backed by an installed Forge or Connect app.
