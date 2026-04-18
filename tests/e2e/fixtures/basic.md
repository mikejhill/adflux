# Basic Markdown Smoke Test

This page exercises the core CommonMark + GFM constructs that adflux maps
directly onto ADF: headings, paragraphs, inline marks, links, code blocks,
lists, blockquotes, tables, and horizontal rules.

## Inline formatting

Plain paragraph with **bold**, *italic*, `inline code`, ~~strikethrough~~,
and a [link to adflux](https://github.com/mikejhill/adflux).

## Lists

- bullet one
- bullet two
  - nested bullet
- bullet three

1. ordered one
2. ordered two
3. ordered three

## Code block

```python
def greet(name: str) -> str:
    return f"hello, {name}"
```

## Table

| Column A | Column B | Column C |
| -------- | -------- | -------- |
| 1        | alpha    | x        |
| 2        | beta     | y        |
| 3        | gamma    | z        |

## Blockquote

> This is a blockquote with **bold** text inside.

## Horizontal rule

---

End of basic fixture.
