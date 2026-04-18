# adflux architecture

## Intermediate representation

adflux uses **panflute AST classes** as its internal representation (IR). These
classes are a well-specified, battle-tested block/inline tree with `Attr` (id,
classes, key-value) on every structural node, originally designed to work with
the Pandoc binary. Here, we use them **purely as Python data structures** — no
Pandoc binary is required or called. This gives us a convenient, pre-existing
tree structure without reinventing an EBNF grammar or bespoke tree.

## Reader / writer registry

Each format registers a reader (`bytes|str -> pf.Doc`) and a writer
(`pf.Doc -> str`) into the module-level registry in `adflux.formats`. The
public `convert()` function looks up both and pipes them through an optional
options filter.

## ADF bridge

ADF is not a native Python format, so adflux ships a custom bridge built on two
declarative artifacts:

- `src/adflux/formats/adf/mapping.yaml` — one entry per ADF node type stating
  what kind of IR node it maps to (block/inline), what attributes exist,
  whether its content is block-level, inline, or empty, and what the envelope
  class is.
- `src/adflux/formats/adf/schema/adf-minimal.schema.json` — JSON Schema used to
  validate ADF documents on both read and write.

The reader and writer are **generic engines** that consult the mapping table to
decide how to translate each node. Adding a new ADF node type is a YAML edit
and a fixture addition — no Python changes.

## Envelope convention

Every ADF construct that has no direct IR analog (panels, status, mentions,
task lists, extensions, …) is encoded as a panflute `Div` (block) or `Span`
(inline) with:

- `class="adf-<nodeType>"` — the marker.
- Scalar attributes stored as flat key-value pairs.
- Complex / nested attributes (dicts, lists) stored under `data-adf-json` as a
  base64-encoded JSON blob.

A universal `adf-raw` fallback envelope captures any node type not present in
`mapping.yaml`, guaranteeing zero data loss even for future ADF extensions.

Because `Div`/`Span` + attrs round-trip through the Markdown reader and writer,
envelopes survive a Markdown hop when the options ask for it.

## Conversion options

| Option         | Choices                       | Default  | Description                                          |
| -------------- | ----------------------------- | -------- | ---------------------------------------------------- |
| `envelopes`    | `keep`, `drop`, `keep-strict` | `keep`   | How ADF envelope nodes are handled on lossy targets. |
| `jira-strict`  | `true`, `false`               | `false`  | Reject non-Jira ADF nodes during serialization.      |

Options are applied by `adflux.ir.profile_filter.apply_options`, which runs
over the IR before it is handed to the target writer.

## Extending

Adding a new ADF node type:

1. Add an entry to `mapping.yaml` (IR kind, attrs, content_kind).
2. Add a round-trip fixture in `tests/roundtrip/test_node_coverage.py`.
3. Run `pytest`.

Adding a format that needs a custom parser:

1. Implement a reader returning `panflute.Doc` and a writer consuming it.
2. Register them. The rest of the pipeline is format-agnostic.
