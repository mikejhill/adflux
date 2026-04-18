# Fidelity profiles

A *profile* is an immutable record telling the writer how to handle ADF-only
constructs when they cannot be expressed natively in the target format.

## Decision matrix

| Profile        | `preserve_envelopes` | `drop_unrepresentable` | `fail_on_unrepresentable` |
| -------------- | -------------------- | ---------------------- | ------------------------- |
| `strict-adf`   | true                 | false                  | false                     |
| `pretty-md`    | false                | true                   | false                     |
| `fail-loud`    | true                 | false                  | true                      |

The profile fields drive a small AST-walking filter
(`adflux.ir.profile_filter.apply_profile`) that runs before the target
writer.

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

### `strict-adf` (default)

```markdown
Hello

> [!NOTE]
>
> Info body
```

The default Markdown writer renders ADF macros as idiomatic Markdown — see
[Markdown rendering](../README.md#markdown-rendering) for the full mapping
table — and the reader rebuilds the original `adf-panel` envelope on the
way back, so the round-trip is lossless.

### `pretty-md`

```markdown
Hello

Info body
```

The envelope is dropped silently. Visible body content is preserved. Useful
when emitting Markdown for a non-Confluence destination where the macro
semantics are irrelevant.

### `fail-loud`

```python
>>> convert(src_json, src="adf", dst="markdown", profile="fail-loud")
Traceback (most recent call last):
  ...
adflux.errors.UnrepresentableNodeError: Cannot represent ADF node 'panel' in target 'lossy-target'
```

Useful in CI: catch unintended fidelity regressions early.

## Choosing a profile

| Goal                                                  | Profile      |
| ----------------------------------------------------- | ------------ |
| Lossless storage; round-trip via VCS.                 | `strict-adf` |
| Human-friendly Markdown that drops ADF-only macros.   | `pretty-md`  |
| CI gate ensuring no ADF-only construct slips through. | `fail-loud`  |
