# Conversion options

Options are key=value pairs that control how the converter handles nodes
during conversion. They replace the former "fidelity profiles" system with
a more flexible, extensible approach.

## Core options

| Option        | Choices                       | Default | Description                                               |
| ------------- | ----------------------------- | ------- | --------------------------------------------------------- |
| `envelopes`   | `keep`, `drop`, `keep-strict` | `keep`  | How ADF envelope nodes are handled on lossy targets.      |
| `jira-strict`  | `true`, `false`              | `false` | Reject non-Jira ADF nodes during serialization.           |

### Envelopes

An **envelope** is a panflute `Div` (block) or `Span` (inline) whose CSS
class starts with `adf-*`, representing an ADF construct with no native
counterpart in the target format (panels, macros, mentions, status badges).
Envelopes carry the original ADF node type and attributes so conversion is
reversible.

- **`keep`** (default) — preserve envelopes for lossless round-tripping.
  The Markdown writer renders them as idiomatic Markdown (GitHub alerts,
  `<details>`, HTML comments) that the reader reconstructs on the way back.
- **`drop`** — silently strip envelopes. Block envelopes are replaced by
  their children, inline envelopes collapse to their visible text, and
  content-less envelopes are removed entirely.
- **`keep-strict`** — preserve envelopes, but raise
  `UnrepresentableNodeError` on the first envelope encountered when writing
  to a lossy target. Useful as a CI gate.

### Jira-strict

When `jira-strict=true`, ADF serialization validates the output against
Jira's description ADF schema, which is stricter than Confluence's. Node
types rejected by Jira include `layoutSection`, `layoutColumn`, `taskList`,
`decisionList`, `extension`, `bodiedExtension`, `inlineExtension`,
`nestedExpand`, `embedCard`, `mediaGroup`, `mediaSingle`, `media`, and
`mediaInline`.

## Discovering options

```bash
adflux list-options
```

This prints every registered option with its choices, default, and
description.

## Worked example

Source ADF (abbreviated):

```json
{ "type": "doc", "version": 1, "content": [
  { "type": "paragraph", "content": [{ "type": "text", "text": "Hello" }] },
  { "type": "panel", "attrs": { "panelType": "info" }, "content": [
    { "type": "paragraph", "content": [{ "type": "text", "text": "Info body" }] }
  ]}
]}
```

### `envelopes=keep` (default)

```markdown
Hello

> [!NOTE]
>
> Info body
```

The Markdown writer renders the panel as a GitHub alert blockquote. The
reader rebuilds the `adf-panel` envelope on the way back, so the
round-trip is lossless.

### `envelopes=drop`

```markdown
Hello

Info body
```

The envelope is dropped silently. Visible body content is preserved.

### `envelopes=keep-strict`

```python
>>> convert(src_json, src="adf", dst="markdown", options={"envelopes": "keep-strict"})
Traceback (most recent call last):
  ...
adflux.errors.UnrepresentableNodeError: Cannot represent ADF node 'panel' in target 'lossy-target'
```

Useful in CI: catch unintended fidelity regressions early.

## Setting options

### CLI

```bash
adflux convert --from adf --to md --option envelopes=drop page.json
adflux convert --from md --to adf --option jira-strict=true doc.md
```

Multiple options can be combined:

```bash
adflux convert --from adf --to md -O envelopes=drop -O jira-strict=true page.json
```

### Library API

```python
from adflux import convert

# Using a dict
md = convert(adf_json, src="adf", dst="md", options={"envelopes": "drop"})

# Using an Options instance
from adflux import Options
opts = Options({"envelopes": "keep", "jira-strict": "true"})
adf = convert(md_text, src="md", dst="adf", options=opts)
```

## Choosing options

| Goal                                                  | Options                    |
| ----------------------------------------------------- | -------------------------- |
| Lossless storage; round-trip via VCS.                 | `envelopes=keep` (default) |
| Human-friendly Markdown that drops ADF-only macros.   | `envelopes=drop`           |
| CI gate ensuring no ADF-only construct slips through. | `envelopes=keep-strict`    |
| Target Jira descriptions (stricter ADF schema).       | `jira-strict=true`         |
