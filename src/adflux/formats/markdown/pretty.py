"""Markdown-friendly rendering of ADF envelopes.

The default ADF→Markdown path emits panflute Divs and Spans for every
preserved envelope. That syntax is robust for round-trips but renders as
**literal text** in standard Markdown viewers (GitHub, VS Code preview, etc.).

This module rewrites the panflute AST so ADF envelopes come out as either:

1. **Native Markdown idioms** wherever they exist:

   - ``panel``         → GitHub-style alert blockquote
                         (``> [!NOTE]`` / ``[!TIP]`` / ``[!IMPORTANT]`` /
                         ``[!WARNING]`` / ``[!CAUTION]``)
   - ``expand``        → ``<details><summary>title</summary> … </details>``
   - ``inlineCard``    → autolink ``<https://…>``
   - ``blockCard`` /
     ``embedCard``     → autolink on its own line
   - ``emoji``         → its unicode text
   - ``mention``       → ``@text``

2. **HTML comment markers** for everything else:

   - Block:  ``<!--adf:nodeType key="value"-->`` … ``<!--/adf:nodeType-->``
   - Inline: ``<!--adf:nodeType key="value"/-->`` (self-closing)

Markers are invisible in standard renderers but uniquely identify the ADF
node, so :func:`unprettify` rebuilds the original envelope on the read path.
"""

from __future__ import annotations

import contextlib
import html
import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import panflute as pf

# GitHub-flavored alert types map onto Confluence panel types.
_PANEL_TO_ALERT = {
    "info": "NOTE",
    "note": "IMPORTANT",
    "warning": "WARNING",
    "error": "CAUTION",
    "success": "TIP",
}
_ALERT_TO_PANEL = {v: k for k, v in _PANEL_TO_ALERT.items()}

_ENVELOPE_CLASS_PREFIX = "adf-"

# HTML-comment envelope markers. Keep formats tight so they're easy to detect.
_BLOCK_OPEN_RE = re.compile(
    r"<!--\s*adf:(?P<type>[A-Za-z][A-Za-z0-9]*)(?P<attrs>(?:\s[^>]*?)?)\s*-->"
)
_BLOCK_CLOSE_RE = re.compile(r"<!--\s*/adf:(?P<type>[A-Za-z][A-Za-z0-9]*)\s*-->")
_INLINE_VOID_RE = re.compile(
    r"<!--\s*adf:(?P<type>[A-Za-z][A-Za-z0-9]*)(?P<attrs>(?:\s[^>]*?)?)\s*/-->"
)
# attributes inside a marker: key="value" (values double-quoted; html-escaped)
_ATTR_RE = re.compile(r'(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*=\s*"(?P<val>[^"]*)"')


def _attrs_to_marker(attrs: dict[str, str]) -> str:
    if not attrs:
        return ""
    parts = []
    for k, v in attrs.items():
        if v is None:
            continue
        parts.append(f'{k}="{html.escape(str(v), quote=True)}"')
    return (" " + " ".join(parts)) if parts else ""


def _marker_to_attrs(text: str) -> dict[str, str]:
    return {m.group("key"): html.unescape(m.group("val")) for m in _ATTR_RE.finditer(text)}


def _envelope_marker(elem: Any) -> str | None:
    import panflute as pf

    if not isinstance(elem, (pf.Div, pf.Span)):
        return None
    for cls in elem.classes:
        if cls.startswith(_ENVELOPE_CLASS_PREFIX):
            return str(cls)
    return None


def _node_type(elem: pf.Div | pf.Span, marker: str) -> str:
    # Prefer the explicit ``data-adf-type`` attr (carries the canonical
    # camelCase node type for opaque / kebab-case nodes).
    return elem.attributes.get("data-adf-type") or marker[len(_ENVELOPE_CLASS_PREFIX) :]


def _envelope_attrs(elem: pf.Div | pf.Span) -> dict[str, str]:
    """Recover the user-visible ADF attributes from an envelope element."""
    import base64

    attrs: dict[str, str] = {}
    for k, v in elem.attributes.items():
        if k in ("data-adf-type", "data-adf-json"):
            continue
        attrs[k] = v
    blob = elem.attributes.get("data-adf-json")
    if blob:
        try:
            decoded = json.loads(base64.b64decode(blob.encode("ascii")).decode("utf-8"))
        except Exception:
            decoded = None
        if isinstance(decoded, dict):
            for k, v in decoded.items():
                attrs.setdefault(k, json.dumps(v) if not isinstance(v, str) else v)
    if elem.identifier:
        attrs.setdefault("id", elem.identifier)
    return attrs


# --------------------------------------------------------------------------- #
# Writer side: prettify
# --------------------------------------------------------------------------- #


def prettify(doc: pf.Doc) -> pf.Doc:
    """Rewrite envelope Div/Spans into native Markdown idioms or HTML markers.

    Args:
        doc: Panflute document produced by the IR layer.

    Returns:
        The same document with envelope nodes rewritten in place.
    """
    import panflute as pf

    def _walk_block(elem: Any, doc: pf.Doc) -> Any:
        if not isinstance(elem, pf.Div):
            return None
        marker = _envelope_marker(elem)
        if marker is None:
            return None
        node_type = _node_type(elem, marker)
        attrs = _envelope_attrs(elem)
        return _block_replacement(node_type, attrs, list(elem.content))

    def _walk_inline(elem: Any, doc: pf.Doc) -> Any:
        if not isinstance(elem, pf.Span):
            return None
        marker = _envelope_marker(elem)
        if marker is None:
            return None
        node_type = _node_type(elem, marker)
        attrs = _envelope_attrs(elem)
        return _inline_replacement(node_type, attrs)

    doc.walk(_walk_block)
    doc.walk(_walk_inline)
    _tighten_lists(doc)
    return doc


def _tighten_lists(doc: pf.Doc) -> None:
    """Convert single-Para `ListItem`s to single-Plain.

    Panflute emits items wrapping a single ``Para`` as **loose** lists (with
    blank lines between items); items wrapping ``Plain`` come out **tight**.
    Loose-list output looks noisy and unlike typical hand-authored sources,
    so we tighten them on the way out.
    """
    import panflute as pf

    def _walk(elem: Any, doc: pf.Doc) -> Any:
        if isinstance(elem, pf.ListItem) and len(elem.content) == 1:
            only = elem.content[0]
            if isinstance(only, pf.Para):
                elem.content = [pf.Plain(*only.content)]
        return None

    doc.walk(_walk)


def _block_replacement(node_type: str, attrs: dict[str, str], content: list[Any]) -> Any | None:
    import panflute as pf

    if node_type == "panel":
        alert = _PANEL_TO_ALERT.get(attrs.get("panelType", "info"), "NOTE")
        children: list[Any] = list(content) if content else [pf.Para()]
        # Use RawInline with the writer's native format so pandoc passes the
        # alert marker through verbatim (commonmark's writer would otherwise
        # escape the brackets, breaking GitHub alert recognition).
        marker_para = pf.Para(pf.RawInline(f"[!{alert}]", format="gfm"))
        return pf.BlockQuote(marker_para, *children)

    if node_type == "expand":
        title = attrs.get("title", "")
        title_html = html.escape(title)
        open_block = pf.RawBlock(f"<details><summary>{title_html}</summary>", format="html")
        close_block = pf.RawBlock("</details>", format="html")
        body = list(content) if content else [pf.Para()]
        # Use a Div as a transparent group; pandoc serializes its children directly
        # only if it has no classes/attrs. Use a unique throwaway class so we can
        # special-case it in the writer? Simpler: return a list via a Div with a
        # known transparent class — pandoc emits the children inline if classes
        # are empty. Empty-class Div is still wrapped in `<div>...</div>` by
        # pandoc, so instead we splice using a pandoc Null trick? Cleanest: use
        # pf.BlockQuote? No. Use a ListContainer? Walks return single Element.
        # Workaround: wrap in a Div with class `__adf_splice__` and post-process.
        return pf.Div(open_block, *body, close_block, classes=["__adf_splice__"])

    if node_type == "blockCard":
        url = attrs.get("url", "")
        if url:
            return pf.Para(pf.Link(pf.Str(url), url=url))
    # Note: embedCard intentionally falls through to the HTML-marker fallback
    # so it stays distinguishable from blockCard on round-trip (a bare
    # autolink line is otherwise ambiguous).

    if node_type == "taskList":
        items = []
        for child in content:
            if not isinstance(child, pf.Div):
                continue
            child_marker = _envelope_marker(child)
            if child_marker is None:
                continue
            inner_attrs = _envelope_attrs(child)
            checkbox = "[x] " if inner_attrs.get("state", "TODO").upper() == "DONE" else "[ ] "
            inlines = []
            for sub in child.content:
                if isinstance(sub, pf.Plain | pf.Para):
                    inlines.extend(sub.content)
                    inlines.append(pf.SoftBreak())
            if inlines and isinstance(inlines[-1], pf.SoftBreak):
                inlines.pop()
            items.append(pf.ListItem(pf.Plain(pf.Str(checkbox), *inlines)))
        if items:
            return pf.BulletList(*items)

    # Fallback: HTML-comment envelope markers wrapping the original content.
    marker_attrs = _attrs_to_marker(attrs)
    open_marker = pf.RawBlock(f"<!--adf:{node_type}{marker_attrs}-->", format="html")
    close_marker = pf.RawBlock(f"<!--/adf:{node_type}-->", format="html")
    body = list(content) if content else []
    return pf.Div(open_marker, *body, close_marker, classes=["__adf_splice__"])


def _inline_replacement(node_type: str, attrs: dict[str, str]) -> Any | None:
    import panflute as pf

    if node_type == "inlineCard":
        url = attrs.get("url", "")
        if url:
            return pf.Link(pf.Str(url), url=url)

    if node_type == "emoji":
        text = attrs.get("text") or attrs.get("shortName") or ""
        if text:
            return pf.Str(text)

    if node_type == "mention":
        text = attrs.get("text") or attrs.get("displayName") or attrs.get("id", "")
        return pf.Str(f"@{text}" if not str(text).startswith("@") else str(text))

    # Fallback: self-closing inline HTML comment marker.
    marker_attrs = _attrs_to_marker(attrs)
    return pf.RawInline(f"<!--adf:{node_type}{marker_attrs}/-->", format="html")


def splice_transparent_divs(doc: pf.Doc) -> pf.Doc:
    """Inline-splice any helper ``__adf_splice__`` Divs into their parent block list.

    Created by :func:`prettify` so it can return a *list* of replacement blocks
    from a single-element walk callback.
    """
    import panflute as pf

    def _walk(elem: Any, doc: pf.Doc) -> Any:
        if not hasattr(elem, "content"):
            return None
        children = getattr(elem, "content", None)
        if children is None:
            return None
        # Only splice block lists.
        new_children: list[Any] = []
        changed = False
        for child in list(children):
            if isinstance(child, pf.Div) and "__adf_splice__" in child.classes:
                new_children.extend(child.content)
                changed = True
            else:
                new_children.append(child)
        if changed:
            try:
                elem.content = new_children
            except Exception:
                return None
        return None

    doc.walk(_walk)
    return doc


# --------------------------------------------------------------------------- #
# Reader side: unprettify
# --------------------------------------------------------------------------- #


_PANDOC_ALERT_TO_PANEL = {
    "note": "info",
    "tip": "success",
    "important": "note",
    "warning": "warning",
    "caution": "error",
}


def unprettify(doc: pf.Doc) -> pf.Doc:
    """Recognise prettified idioms and rebuild the original envelope nodes.

    Counterpart of :func:`prettify`. Idempotent: a doc that's already been
    unprettified is returned unchanged.
    """
    import panflute as pf

    from adflux.ir.envelope import pack_envelope

    def _walk(elem: Any, doc: pf.Doc) -> Any:
        # markdown-it-py natively converts GitHub alert blockquotes into
        # Div(classes=["note"|"tip"|...]) containing a title Div + body
        # blocks. Map those back to panel envelopes.
        if isinstance(elem, pf.Div):
            panel = _try_parse_pandoc_alert(elem)
            if panel is not None:
                panel_type, body = panel
                return pack_envelope(
                    "panel",
                    kind="block",
                    attrs={"panelType": panel_type},
                    children=body,
                )

        # Fallback: blockquote-with-[!NOTE] (when the reader didn't natively
        # promote it to a Div, e.g. plain commonmark without alert support).
        if isinstance(elem, pf.BlockQuote):
            panel = _try_parse_alert(elem)
            if panel is not None:
                panel_type, body = panel
                return pack_envelope(
                    "panel",
                    kind="block",
                    attrs={"panelType": panel_type},
                    children=body,
                )

        return None

    doc.walk(_walk)

    # Block-list-level passes for constructs that span multiple sibling blocks:
    # <details>... </details>, comment-marker pairs, GFM task lists, autolink-only paras.
    _absorb_inline_void_blocks(doc)
    _splice_block_lists(doc)
    _splice_inline_lists(doc)
    return doc


def _absorb_inline_void_blocks(doc: pf.Doc) -> None:
    """Merge stray block-level self-closing markers back into surrounding paragraphs.

    A self-closing comment like ``<!--adf:status …/-->`` on its own line
    (a common authoring pattern when the marker happens to fall at a soft
    line break) is parsed by pandoc as a block-level ``RawBlock``, which
    breaks the surrounding paragraph in two. We splice it back inline so
    the marker is treated as the inline envelope it represents.
    """
    import panflute as pf

    def _is_void_block(b: Any) -> tuple[str, str] | None:
        """Match a RawBlock that *starts* with a self-closing comment marker.

        Returns ``(marker_text, trailing_text)`` where ``trailing_text`` is
        the rest of the block after the marker (often pandoc's CommonMark
        parser greedily absorbs trailing inline text into the same Type-2
        HTML block). The trailing portion is reparsed as inline content.
        """
        import panflute as pf

        if not isinstance(b, pf.RawBlock) or b.format != "html":
            return None
        text = b.text.strip("\r\n")
        # Try a marker followed by trailing inline text.
        m = re.match(
            r"\s*(<!--\s*adf:[A-Za-z][A-Za-z0-9]*(?:\s[^>]*?)?\s*/-->)(.*)$", text, re.DOTALL
        )
        if not m:
            return None
        return m.group(1), m.group(2)

    def _process(blocks: list[Any]) -> list[Any]:
        out: list[Any] = list(blocks)
        i = 0
        while i < len(out):
            b = out[i]
            match = _is_void_block(b)
            if match is not None and i > 0:
                marker, trailing = match
                prev = out[i - 1]
                if isinstance(prev, pf.Para):
                    raw_inline = pf.RawInline(marker, format="html")
                    trailing_inlines = _inlines_from_text(trailing)
                    nxt_inlines: list[Any] = []
                    consumed_next = False
                    if i + 1 < len(out) and isinstance(out[i + 1], pf.Para):
                        nxt_inlines = [pf.SoftBreak(), *out[i + 1].content]
                        consumed_next = True
                    merged = pf.Para(
                        *prev.content,
                        pf.SoftBreak(),
                        raw_inline,
                        *trailing_inlines,
                        *nxt_inlines,
                    )
                    end = i + 2 if consumed_next else i + 1
                    out[i - 1 : end] = [merged]
                    i = max(i - 1, 0)
                    continue
            # Recurse into block containers.
            for attr in ("content",):
                children = getattr(b, attr, None)
                if isinstance(children, pf.ListContainer) and len(children) > 0:
                    sample = children[0]
                    if isinstance(sample, pf.Block):
                        new = _process(list(children))
                        with contextlib.suppress(Exception):
                            setattr(b, attr, new)
            i += 1
        return out

    doc.content = _process(list(doc.content))


def _inlines_from_text(text: str) -> list[Any]:
    """Convert a fragment of plain text into panflute inlines.

    Splits on whitespace to produce ``Str`` / ``Space`` / ``SoftBreak``
    sequence so the merged paragraph reads naturally.
    """
    import panflute as pf

    out: list[Any] = []
    if not text:
        return out
    # Split preserving line breaks as SoftBreak, runs of spaces as Space.
    for line_idx, line in enumerate(text.split("\n")):
        if line_idx > 0:
            out.append(pf.SoftBreak())
        for token in re.split(r"(\s+)", line):
            if token == "":
                continue
            if token.isspace():
                out.append(pf.Space())
            else:
                out.append(pf.Str(token))
    # Trim a trailing SoftBreak that would re-introduce the marker's own newline.
    while out and isinstance(out[-1], pf.SoftBreak):
        out.pop()
    return out


def _try_parse_pandoc_alert(div: pf.Div) -> tuple[str, list[Any]] | None:
    """Recognise pandoc's native GitHub-alert Div structure.

    commonmark_x reader emits ``Div(classes=[note|tip|important|warning|caution])``
    whose first child is a ``Div(classes=["title"])`` (the alert label) and
    whose remaining children are the alert body.
    """
    import panflute as pf

    if not div.classes:
        return None
    panel_type: str | None = None
    for cls in div.classes:
        if cls in _PANDOC_ALERT_TO_PANEL:
            panel_type = _PANDOC_ALERT_TO_PANEL[cls]
            break
    if panel_type is None:
        return None
    body = list(div.content)
    # Strip the leading title Div if present.
    if body and isinstance(body[0], pf.Div) and "title" in body[0].classes:
        body = body[1:]
    return panel_type, body


def _try_parse_alert(bq: pf.BlockQuote) -> tuple[str, list[Any]] | None:
    import panflute as pf

    if not bq.content:
        return None
    first = bq.content[0]
    if not isinstance(first, pf.Para | pf.Plain) or not first.content:
        return None
    head = first.content[0]
    if not isinstance(head, pf.Str):
        return None
    m = re.fullmatch(r"\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", head.text)
    if not m:
        return None
    panel_type = _ALERT_TO_PANEL.get(m.group(1))
    if not panel_type:
        return None
    rest_inlines = list(first.content[1:])
    # Trim a leading SoftBreak, if present.
    while rest_inlines and isinstance(rest_inlines[0], pf.SoftBreak | pf.Space):
        rest_inlines.pop(0)
    new_blocks: list[Any] = []
    if rest_inlines:
        new_blocks.append(pf.Para(*rest_inlines))
    new_blocks.extend(bq.content[1:])
    return panel_type, new_blocks


def _try_parse_details_open(text: str) -> str | None:
    m = re.match(r"\s*<details>\s*<summary>(?P<title>.*?)</summary>\s*$", text, re.DOTALL)
    if not m:
        return None
    return html.unescape(m.group("title"))


def _is_details_close(elem: Any) -> bool:
    import panflute as pf

    if not isinstance(elem, pf.RawBlock) or elem.format != "html":
        return False
    return bool(re.match(r"\s*</details>\s*$", elem.text))


def _is_block_open_marker(elem: Any) -> tuple[str, dict[str, str]] | None:
    import panflute as pf

    if not isinstance(elem, pf.RawBlock) or elem.format != "html":
        return None
    m = _BLOCK_OPEN_RE.fullmatch(elem.text.strip())
    if not m:
        return None
    return m.group("type"), _marker_to_attrs(m.group("attrs") or "")


def _is_block_close_marker(elem: Any, expected_type: str) -> bool:
    import panflute as pf

    if not isinstance(elem, pf.RawBlock) or elem.format != "html":
        return False
    m = _BLOCK_CLOSE_RE.fullmatch(elem.text.strip())
    return m is not None and m.group("type") == expected_type


def _splice_block_lists(doc: pf.Doc) -> None:
    """Combine multi-block constructs (`<details>...</details>`, comment markers)."""
    import panflute as pf

    from adflux.ir.envelope import pack_envelope

    def _process(blocks: list[Any]) -> list[Any]:
        out: list[Any] = []
        i = 0
        while i < len(blocks):
            b = blocks[i]
            # <details>...</details>
            if isinstance(b, pf.RawBlock) and b.format == "html":
                title = _try_parse_details_open(b.text)
                if title is not None:
                    j = i + 1
                    while j < len(blocks) and not _is_details_close(blocks[j]):
                        j += 1
                    if j < len(blocks):
                        body = blocks[i + 1 : j]
                        out.append(
                            pack_envelope(
                                "expand",
                                kind="block",
                                attrs={"title": title},
                                children=body,
                            )
                        )
                        i = j + 1
                        continue
            # HTML-comment envelope: <!--adf:type ...-->...<!--/adf:type-->
            opener = _is_block_open_marker(b)
            if opener is not None:
                node_type, attrs = opener
                # Find the matching close marker, accounting for nested
                # same-type envelopes (depth counter).
                depth = 1
                j = i + 1
                while j < len(blocks):
                    inner = _is_block_open_marker(blocks[j])
                    if inner is not None and inner[0] == node_type:
                        depth += 1
                    elif _is_block_close_marker(blocks[j], node_type):
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                if j < len(blocks):
                    # Recurse so nested envelopes (e.g. taskItem inside
                    # taskList) are packed before we wrap the parent.
                    body = _process(list(blocks[i + 1 : j]))
                    out.append(
                        pack_envelope(
                            node_type,
                            kind="block",
                            attrs=attrs,
                            children=body,
                        )
                    )
                    i = j + 1
                    continue
            # Self-closing block marker (no body).
            if (
                isinstance(b, pf.RawBlock)
                and b.format == "html"
                and (m := _INLINE_VOID_RE.fullmatch(b.text.strip()))
            ):
                node_type = m.group("type")
                attrs = _marker_to_attrs(m.group("attrs") or "")
                out.append(pack_envelope(node_type, kind="block", attrs=attrs, children=[]))
                i += 1
                continue
            # Bare-autolink-only paragraph -> blockCard
            if isinstance(b, pf.Para) and len(b.content) == 1 and isinstance(b.content[0], pf.Link):
                link = b.content[0]
                if _link_is_autolink(link):
                    out.append(
                        pack_envelope(
                            "blockCard",
                            kind="block",
                            attrs={"url": link.url},
                            children=[],
                        )
                    )
                    i += 1
                    continue
            # GFM task list -> taskList envelope
            if isinstance(b, pf.BulletList) and _bullet_list_is_tasklist(b):
                out.append(_bulletlist_to_tasklist(b))
                i += 1
                continue
            # Recurse into nested block containers.
            _recurse(b)
            out.append(b)
            i += 1
        return out

    def _recurse(elem: Any) -> None:
        # Generic block-children attrs panflute exposes.
        for attr in ("content",):
            children = getattr(elem, attr, None)
            if children is None or not isinstance(children, pf.ListContainer):
                continue
            sample = children[0] if len(children) > 0 else None
            if sample is None or not isinstance(sample, pf.Block):
                continue
            new = _process(list(children))
            with contextlib.suppress(Exception):
                setattr(elem, attr, new)

    doc.content = _process(list(doc.content))


def _link_is_autolink(link: pf.Link) -> bool:
    import panflute as pf

    if not link.url:
        return False
    if len(link.content) != 1:
        return False
    inner = link.content[0]
    return isinstance(inner, pf.Str) and inner.text == link.url


def _bullet_list_is_tasklist(blist: pf.BulletList) -> bool:
    import panflute as pf

    if not blist.content:
        return False
    for item in blist.content:
        if not isinstance(item, pf.ListItem) or not item.content:
            return False
        first = item.content[0]
        if not isinstance(first, pf.Plain | pf.Para) or not first.content:
            return False
        head = first.content[0]
        if not isinstance(head, pf.Str):
            return False
        if not re.match(r"^\[[ xX]\]$", head.text):
            return False
    return True


def _bulletlist_to_tasklist(blist: pf.BulletList) -> pf.Div:
    import panflute as pf

    from adflux.ir.envelope import pack_envelope

    items: list[Any] = []
    for li in blist.content:
        first = li.content[0]
        head = first.content[0]
        state = "DONE" if head.text.strip("[]").strip().lower() == "x" else "TODO"
        rest = list(first.content[1:])
        while rest and isinstance(rest[0], pf.Space | pf.SoftBreak):
            rest.pop(0)
        body_blocks: list[Any] = []
        if rest:
            body_blocks.append(pf.Para(*rest))
        body_blocks.extend(li.content[1:])
        items.append(
            pack_envelope(
                "taskItem",
                kind="block",
                attrs={"state": state},
                children=body_blocks,
            )
        )
    return pack_envelope("taskList", kind="block", attrs={}, children=items)


def _splice_inline_lists(doc: pf.Doc) -> None:
    """Inline pass: self-closing comment markers + autolinks -> envelope spans."""
    import panflute as pf

    from adflux.ir.envelope import pack_envelope

    def _walk(elem: Any, doc: pf.Doc) -> Any:
        if isinstance(elem, pf.RawInline) and elem.format == "html":
            m = _INLINE_VOID_RE.fullmatch(elem.text.strip())
            if m:
                node_type = m.group("type")
                attrs = _marker_to_attrs(m.group("attrs") or "")
                return pack_envelope(node_type, kind="inline", attrs=attrs, children=[])
        # An inline autolink — `<https://…>` in CommonMark — represents an ADF
        # `inlineCard`. (Block-level bare autolinks are converted to blockCard
        # in `_splice_block_lists` before this pass runs.)
        if isinstance(elem, pf.Link) and _link_is_autolink(elem):
            return pack_envelope(
                "inlineCard",
                kind="inline",
                attrs={"url": elem.url},
                children=[],
            )
        return None

    doc.walk(_walk)
