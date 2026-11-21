# adflux Markdown

CommonMark + GitHub tables, strikethrough and task lists, plus directives for everything
else in ADF. Every ADF document converts to this Markdown and back without loss; anything
without a friendlier form falls back to a generic directive or raw ADF.

## Text

| Markdown | ADF |
|---|---|
| `**bold**` `*italic*` `~~strike~~` `` `code` `` | strong, em, strike, code marks |
| `<u>under</u>` `<sub>2</sub>` `<sup>2</sup>` | underline, subsup |
| `[text](https://x "title")` | link mark |
| `<https://x>` | inlineCard (smart link) |
| `:span[text]{color=#ff5630 background=#fffae6}` | textColor / backgroundColor |
| line ending in `\` or `<br>` | hardBreak |
| `:smile:` `:check_mark:` | emoji (unknown names stay text) |
| `:emoji[name]{id=... text=...}` | emoji with explicit attrs |
| `:status[DONE]{color=green}` | status (neutral, purple, blue, red, yellow, green) |
| `:date[2025-01-31]` | date |
| `:mention[@Ada]{id=<accountId>}` | mention |

`<strong>` `<em>` `<del>` work too; adflux writes them when `**`/`*`/`~~` would not parse
(emphasis next to punctuation).

## Blocks

| Markdown | ADF |
|---|---|
| `# H1` … `###### H6` | heading |
| `- a` / `1. a` | bulletList / orderedList (`3. a` sets `order`) |
| `- [ ] todo` / `- [x] done` | taskList / taskItem |
| `> quote` | blockquote |
| ```` ```python ```` | codeBlock (`language`) |
| `---` | rule |
| GFM table | table (first row = header cells; `:--` `--:` `:-:` align) |
| `![alt](https://x/img.png)` alone in a paragraph | mediaSingle with external media |
| `> [!INFO]` `> [!NOTE]` `> [!TIP]` `> [!SUCCESS]` `> [!WARNING]` `> [!ERROR]` | panel (`IMPORTANT` → note, `CAUTION` → error) |

## Directives

Containers open with `:::name[label]{attrs}` and close with a line of colons. **An outer
container uses more colons than the containers inside it.** Leaf blocks are one line
`::name[label]{attrs}`; inline ones are `:name[label]{attrs}`. Attribute values with spaces
or symbols are quoted: `{title="Read me" flag}` (a bare key means `true`).

```
:::panel{type=custom color=#e3fcef icon=":rocket:"}
Panel body
:::

:::expand{title="Details"}
Hidden text
:::

:::decisions
- [x] Decided
- [ ] Undecided
:::

:::::layout
::::column{width=50}
Left
::::
::::column{width=50}
Right
::::
:::::

::card{url=https://example.com}
::embed{url=https://example.com layout=wide}
::media[Caption]{type=file id=6e7c7f2c-2bb4-4f4d-9d2b-0d6c1c2f6a11 collection=contentId-123 width=600}
```

Complex tables (merged cells, widths, background colours) use `:::table`, `:::row`,
`:::cell{colspan=2 background=#ffebe6}` and `:::header`.

### Any ADF node

Any ADF node type is a directive named after it, with its attributes:
`:::paragraph{align=center}`, `:::heading{level=2 indent=1}`, `::rule`,
`:placeholder{text="Type here"}`. Block marks are attributes: `align` (center, end),
`indent` (1-6), `breakout` (wide, full-width), and `marks` (raw JSON for anything else).

### Raw ADF

````
```adf
{"type": "someNewNode", "attrs": {}}
```
````

or inline `:adf{json="{\"type\":\"hardBreak\"}"}`.

## Confluence macros (confluence profile)

A macro is a directive named after its macro key. The label fills the default parameter
(or the first required one); other parameters are attributes.

```
::toc{maxLevel=3}
:jira[PROJ-123]
::children{depth=2}
:::excerpt
Reusable text
:::
::recently-updated{max=5 spaces=DOCS}
```

Macros Confluence stores as native ADF become that node: `:::info` / `:::tip` / `:::note` /
`:::warning` → panel, `:::code{language=java}` / `:::noformat` → code block, `:::bgcolor`
→ custom panel. Unknown names (apps installed on a site) still become macros. The generic
form is `::extension{adf.key=<key> adf.type=<extensionType> param=value}`; `adf.params`
holds raw JSON parameters and `adf.body` a plain-text body.

Run `adflux macros` for the catalog and `adflux macros <name>` for one macro's parameters.

## Jira vs Confluence

* Emoji: both products use the same emoji; each profile adds its product's shortcuts
  (Confluence `:tick:` `:information:`, Jira `:tick:` `:cross:` `:info:` `:light-on:` `:yes:`).
* Macros, layouts and decision lists only render in Confluence; the jira profile warns.
* Mentions need an account id (`{id=...}`); codas can resolve `@Name` for you.
