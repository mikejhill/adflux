"""markdown-it extensions for the adflux Markdown dialect.

The dialect is CommonMark + GFM tables, strikethrough and task lists, plus the generic
directive syntax (https://talk.commonmark.org/t/generic-directives-plugins-syntax/444):

* container: a line ``:::name[label]{attrs}`` opens, a line of at least as many colons
  closes. An outer container uses more colons than the containers inside it.
* leaf: one line ``::name[label]{attrs}``.
* inline: ``:name[label]{attrs}`` (label or attributes required).

and emoji shortcodes ``:name:`` (only names the active profile knows; anything else stays
text). Labels are inline Markdown. Tokens produced: ``directive_open``/``directive_close``
(container), ``directive_leaf``, ``directive_inline_open``/``directive_inline_close`` and
``emoji``; each carries ``meta = {"name", "attrs", "label"}``.
"""

from __future__ import annotations

import re
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock
from markdown_it.rules_inline import StateInline

from adflux.errors import MarkdownError
from adflux.markdown.attrs import parse_attrs

NAME = r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z][A-Za-z0-9_-]*)*"
_BLOCK_OPEN = re.compile(rf"^(:{{2,}})({NAME})")
_CLOSE = re.compile(r"^(:{3,})\s*$")
_INLINE_NAME = re.compile(rf":({NAME})(?=[\[{{])")
_EMOJI = re.compile(r":([A-Za-z0-9_+\-]+(?:-[A-Za-z0-9_]+)*):")


def _label_end(source: str, start: int) -> int:
    """Return the index of the ``]`` matching ``source[start] == "["`` (or -1)."""
    depth = 0
    pos = start
    while pos < len(source):
        char = source[pos]
        if char == "\\":
            pos += 2
            continue
        if char == "`":
            # skip code spans so brackets inside them do not count
            run = len(source[pos:]) - len(source[pos:].lstrip("`"))
            close = source.find("`" * run, pos + run)
            pos = close + run if close != -1 else pos + run
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return pos
        pos += 1
    return -1


def parse_tail(text: str, pos: int, line: int | None = None) -> tuple[str | None, dict[str, str], int]:
    """Parse ``[label]{attrs}`` starting at ``pos``; return label, attrs and end index."""
    label: str | None = None
    attrs: dict[str, str] = {}
    if pos < len(text) and text[pos] == "[":
        end = _label_end(text, pos)
        if end == -1:
            raise MarkdownError("unterminated directive label (missing ']')", line)
        label = text[pos + 1 : end]
        pos = end + 1
    if pos < len(text) and text[pos] == "{":
        try:
            attrs, pos = parse_attrs(text, pos)
        except MarkdownError as error:
            raise MarkdownError(str(error), line) from None
    return label, attrs, pos


def directive_block(state: StateBlock, start_line: int, end_line: int, silent: bool) -> bool:
    """Block rule for container (``:::``) and leaf (``::``) directives."""
    if state.sCount[start_line] - state.blkIndent >= 4:
        return False
    pos = state.bMarks[start_line] + state.tShift[start_line]
    maximum = state.eMarks[start_line]
    line = state.src[pos:maximum]
    match = _BLOCK_OPEN.match(line)
    if not match:
        return False
    colons = len(match.group(1))
    name = match.group(2)
    label, attrs, end = parse_tail(line, match.end(), start_line)
    if line[end:].strip():
        return False  # trailing text: not a directive line
    if silent:
        return True
    meta: dict[str, Any] = {"name": name, "attrs": attrs, "label": label}
    if colons == 2:
        token = state.push("directive_leaf", "", 0)
        token.meta = meta
        token.map = [start_line, start_line + 1]
        token.markup = "::"
        state.line = start_line + 1
        return True
    next_line = start_line
    closed = False
    while True:
        next_line += 1
        if next_line >= end_line:
            break
        line_start = state.bMarks[next_line] + state.tShift[next_line]
        line_end = state.eMarks[next_line]
        if line_start < line_end and state.sCount[next_line] < state.blkIndent:
            break  # a less indented line ends the parent block (list item...)
        if state.sCount[next_line] - state.blkIndent >= 4:
            continue
        close = _CLOSE.match(state.src[line_start:line_end])
        if close and len(close.group(1)) >= colons:
            closed = True
            break
    old_parent = state.parentType
    old_line_max = state.lineMax
    state.parentType = "directive"  # type: ignore[assignment]
    state.lineMax = next_line
    token = state.push("directive_open", "div", 1)
    token.meta = meta
    token.markup = ":" * colons
    token.block = True
    token.map = [start_line, next_line]
    state.md.block.tokenize(state, start_line + 1, next_line)
    token = state.push("directive_close", "div", -1)
    token.markup = ":" * colons
    token.block = True
    state.parentType = old_parent
    state.lineMax = old_line_max
    state.line = next_line + (1 if closed else 0)
    return True


def directive_inline(state: StateInline, silent: bool) -> bool:
    """Inline rule for ``:name[label]{attrs}``."""
    if state.src[state.pos] != ":":
        return False
    match = _INLINE_NAME.match(state.src, state.pos)
    if not match:
        return False
    try:
        label, attrs, end = parse_tail(state.src, match.end())
    except MarkdownError:
        return False
    if end > state.posMax:
        return False
    if not silent:
        token = state.push("directive_inline_open", "span", 1)
        token.meta = {"name": match.group(1), "attrs": attrs, "label": label}
        if label:
            label_start = match.end() + 1
            old_pos, old_max = state.pos, state.posMax
            state.pos = label_start
            state.posMax = label_start + len(label)
            state.md.inline.tokenize(state)
            state.pos, state.posMax = old_pos, old_max
        close = state.push("directive_inline_close", "span", -1)
        close.meta = token.meta
    state.pos = end
    return True


def emoji_inline(state: StateInline, silent: bool) -> bool:
    """Inline rule for ``:shortcode:`` resolved by the profile in ``env["profile"]``."""
    if state.src[state.pos] != ":":
        return False
    match = _EMOJI.match(state.src, state.pos)
    if not match or match.end() > state.posMax:
        return False
    profile = state.env.get("profile")
    attrs = profile.resolve_emoji(match.group(1)) if profile is not None else None
    if attrs is None:
        return False
    if not silent:
        token = state.push("emoji", "", 0)
        token.meta = {"attrs": attrs}
        token.content = match.group(0)
    state.pos = match.end()
    return True


def create_parser() -> MarkdownIt:
    """Return the markdown-it parser for the adflux dialect."""
    md = MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    md.block.ruler.before(
        "fence",
        "directive",
        directive_block,
        {"alt": ["paragraph", "reference", "blockquote", "list"]},
    )
    md.inline.ruler.before("emphasis", "directive_inline", directive_inline)
    md.inline.ruler.before("directive_inline", "emoji", emoji_inline)
    return md
