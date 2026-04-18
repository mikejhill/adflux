# Fidelity matrix

Per-format support summary. ✅ = native, 📦 = preserved as envelope (round-trips
losslessly through `strict-adf`), ⚠️ = best-effort, ❌ = dropped under
`pretty-md`.

| ADF node             | Markdown      | Notes                                   |
| -------------------- | ------------- | --------------------------------------- |
| paragraph            | ✅            |                                         |
| heading              | ✅            |                                         |
| bulletList           | ✅            |                                         |
| orderedList          | ✅            |                                         |
| listItem             | ✅            |                                         |
| codeBlock            | ✅            | Language attribute preserved.           |
| blockquote           | ✅            |                                         |
| rule                 | ✅            |                                         |
| table                | ✅            | Headers, colspan, rowspan supported.    |
| panel                | ✅ alert      | Rendered as GitHub alert blockquotes.   |
| expand               | ✅ details    | Rendered as `<details>` block.          |
| nestedExpand         | 📦            |                                         |
| taskList / taskItem  | 📦            |                                         |
| decisionList / Item  | 📦            |                                         |
| mediaSingle / Group  | 📦            |                                         |
| media                | 📦            |                                         |
| extension            | 📦            | Macro params kept verbatim (JSON blob). |
| bodiedExtension      | 📦            |                                         |
| inlineExtension      | 📦            |                                         |
| **Inlines**          |               |                                         |
| text                 | ✅            |                                         |
| hardBreak            | ✅            |                                         |
| mention              | 📦            |                                         |
| emoji                | 📦            |                                         |
| status               | 📦            |                                         |
| date                 | 📦            |                                         |
| placeholder          | 📦            |                                         |
| inlineCard           | 📦            |                                         |
| **Marks**            |               |                                         |
| strong               | ✅            |                                         |
| em                   | ✅            |                                         |
| code                 | ✅            |                                         |
| strike               | ✅            |                                         |
| underline            | ✅            | GFM via `commonmark_x`.                 |
| link                 | ✅            |                                         |
| subsup               | ✅            |                                         |
| textColor            | 📦            | Span envelope.                          |
| **Fallback**         |               |                                         |
| *unmapped node type* | 📦 (`adf-raw`)| Original JSON preserved verbatim.       |

## Round-trip guarantees

- **ADF → IR → ADF** under `strict-adf` is **structurally and attributively
  exact** for every node type in `mapping.yaml` and for any unmapped node type
  via `adf-raw`. This is enforced by `tests/roundtrip/test_node_coverage.py`
  and by the Hypothesis property test.
- **MD → ADF → MD** is best-effort. The IR loses some Markdown-specific
  whitespace; ADF has no notion of "the source had two spaces here".
- **ADF → MD → ADF** under `strict-adf` preserves all envelopes (and thus all
  ADF-only constructs) thanks to Markdown's fenced-div attribute syntax.
