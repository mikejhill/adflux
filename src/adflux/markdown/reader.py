"""Markdown -> ADF.

markdown-it turns the text into a token stream (:mod:`adflux.markdown.syntax` adds the
directive and emoji rules); this module folds the tokens into a tree and lowers it to ADF
nodes. Product-specific choices (emoji, macros, mentions) come from the
:class:`~adflux.profiles.Profile`.
"""

from __future__ import annotations

import json
import re
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from adflux.adf.model import Mark, Node, load
from adflux.adf.normalize import normalize
from adflux.adf.spec import NODES, mark_spec, node_spec
from adflux.errors import AdfError, MarkdownError
from adflux.markdown import names
from adflux.markdown.syntax import create_parser
from adflux.profiles.macros import CONFLUENCE_MACRO_TYPE
from adflux.profiles.profile import Profile

ALERT = re.compile(r"^\[!([A-Za-z]+)\][ \t]*(?:\n|$)")
TASK = re.compile(r"^\[([ xX])\](?:[ \t]+|$)")
HTML_TAG = re.compile(r"^<(/?)([A-Za-z][A-Za-z0-9]*)\s*(/?)>$")


class ConversionWarning(UserWarning):
    """A construct was converted with loss or may not render in the target product."""


@dataclass
class _Tree:
    token: Token
    children: list[_Tree] = field(default_factory=list)


def _fold(tokens: list[Token]) -> list[_Tree]:
    root: list[_Tree] = []
    stack: list[_Tree] = []
    for token in tokens:
        if token.nesting == 1:
            item = _Tree(token)
            (stack[-1].children if stack else root).append(item)
            stack.append(item)
        elif token.nesting == -1:
            stack.pop()
        else:
            (stack[-1].children if stack else root).append(_Tree(token))
    return root


@cache
def _parser() -> MarkdownIt:
    return create_parser()


def _local_id() -> str:
    return str(uuid.uuid4())


class Reader:
    """Convert one Markdown document to an ADF ``doc`` node."""

    def __init__(self, profile: Profile, *, strict: bool = False) -> None:
        self.profile = profile
        self.strict = strict
        self.md = _parser()
        self._lines: list[str] | None = None
        self._warned: set[str] = set()

    # -- entry points ---------------------------------------------------------------
    def read(self, source: str) -> Node:
        """Return the ADF document for ``source``."""
        env: dict[str, Any] = {"profile": self.profile}
        tokens = self.md.parse(source, env)
        self._lines = source.split("\n")
        doc = Node("doc", content=[], extra={"version": 1})
        doc.content = self._blocks(_fold(tokens), "doc")
        for node in doc.walk():
            if node.type in self.profile.unsupported:
                self._warn(f"{self.profile.name} does not render {node.type!r} nodes")
        return normalize(doc)

    def inline(self, source: str, parent: str = "paragraph") -> list[Node]:
        """Return inline ADF nodes for an inline Markdown fragment (directive labels)."""
        env: dict[str, Any] = {"profile": self.profile}
        tokens = self.md.parseInline(source, env)
        children = tokens[0].children if tokens else []
        nodes = self._inlines(children or [], parent)
        holder = normalize(Node("paragraph", content=nodes))
        return holder.content or []

    def plain(self, label: str | None) -> str | None:
        """Return the plain text of a directive label (escapes and entities resolved)."""
        if label is None:
            return None
        parts: list[str] = []
        for node in self.inline(label):
            parts.append("\n" if node.type == "hardBreak" else node.text_content())
        return "".join(parts)

    # -- helpers ------------------------------------------------------------------------
    def _warn(self, message: str, line: int | None = None) -> None:
        where = f"line {line + 1}: " if line is not None else ""
        if self.strict:
            raise MarkdownError(message, line)
        if message in self._warned:
            return
        self._warned.add(message)
        warnings.warn(where + message, ConversionWarning, stacklevel=4)

    @staticmethod
    def _line(tree: _Tree) -> int | None:
        return tree.token.map[0] if tree.token.map else None

    def _fits(self, parent: str, child: str) -> bool:
        spec = NODES.get(parent)
        return spec is None or child in spec.content

    # -- blocks ---------------------------------------------------------------------------
    def _blocks(self, trees: list[_Tree], parent: str) -> list[Node]:
        out: list[Node] = []
        for tree in trees:
            try:
                out.extend(self._block(tree, parent))
            except (ValueError, TypeError, json.JSONDecodeError, AdfError) as error:
                if isinstance(error, MarkdownError):
                    raise
                raise MarkdownError(str(error), self._line(tree)) from None
        return out

    def _block(self, tree: _Tree, parent: str) -> list[Node]:
        token = tree.token
        kind = token.type
        if kind == "paragraph_open":
            return self._paragraph(tree, parent)
        if kind == "heading_open":
            level = int(token.tag[1])
            return [Node("heading", {"level": level}, self._inline_of(tree, "heading"))]
        if kind == "bullet_list_open":
            return self._bullet_list(tree, parent)
        if kind == "ordered_list_open":
            attrs = {"order": int(token.attrs.get("start", 1))}
            items = [self._list_item(item) for item in tree.children]
            return [Node("orderedList", attrs, items)]
        if kind == "blockquote_open":
            return self._blockquote(tree, parent)
        if kind in ("fence", "code_block"):
            return self._code(token)
        if kind == "hr":
            return [Node("rule")]
        if kind == "table_open":
            return [self._table(tree)]
        if kind == "html_block":
            text = token.content.rstrip("\n")
            return [Node("paragraph", content=[Node("text", text=text)])] if text else []
        if kind == "directive_open":
            return self._container(tree, parent)
        if kind == "directive_leaf":
            return self._leaf(tree, parent)
        self._warn(f"unsupported Markdown construct {kind!r}", self._line(tree))
        return []

    def _inline_of(self, tree: _Tree, parent: str) -> list[Node]:
        inline = next((c for c in tree.children if c.token.type == "inline"), None)
        if inline is None:
            return []
        return self._inlines(inline.token.children or [], parent)

    def _paragraph(self, tree: _Tree, parent: str) -> list[Node]:
        inline = next((c for c in tree.children if c.token.type == "inline"), None)
        children = (inline.token.children or []) if inline else []
        significant = [t for t in children if not (t.type == "text" and not t.content.strip())]
        if len(significant) == 1 and significant[0].type == "image" and self._fits(parent, "mediaSingle"):
            image = significant[0]
            media = {"type": "external", "url": image.attrs.get("src", "")}
            alt = _plain_tokens(image.children or [])
            if alt:
                media["alt"] = alt
            return [Node("mediaSingle", {"layout": "center"}, [Node("media", media)])]
        content = self._inlines(children, "paragraph")
        return [Node("paragraph", content=content)]

    def _bullet_list(self, tree: _Tree, parent: str) -> list[Node]:
        items = tree.children
        if items and all(self._task_marker(item) is not None for item in items):
            return [self._task_list(items, "taskList")]
        return [Node("bulletList", content=[self._list_item(item) for item in items])]

    def _task_marker(self, item: _Tree) -> str | None:
        first = item.children[0] if item.children else None
        if first is None or first.token.type != "paragraph_open":
            return None
        inline = next((c for c in first.children if c.token.type == "inline"), None)
        if inline is None:
            return None
        match = TASK.match(inline.token.content)
        return match.group(1) if match else None

    def _strip_task(self, item: _Tree) -> list[Node]:
        first = item.children[0]
        inline = next(c for c in first.children if c.token.type == "inline")
        source = TASK.sub("", inline.token.content, count=1)
        return self.inline(source, "taskItem")

    def _task_list(self, items: list[_Tree], kind: str, line: int | None = None) -> Node:
        item_type, list_type = ("decisionItem", "decisionList") if kind == "decisionList" else ("taskItem", "taskList")
        content: list[Node] = []
        for item in items:
            marker = self._task_marker(item)
            if marker is None:
                where = self._line(item) if self._line(item) is not None else line
                raise MarkdownError(f"each {list_type} item needs a [ ] or [x] marker and text", where)
            done = marker in ("x", "X")
            state = ("DECIDED" if done else "UNDECIDED") if kind == "decisionList" else "DONE" if done else "TODO"
            first = self._strip_task(item)
            extras = item.children[1:]
            blocks = [e for e in extras if e.token.type != "bullet_list_open"]
            if kind == "taskList" and blocks and all(e.token.type == "paragraph_open" for e in blocks):
                # more paragraphs under the item: a block task item keeps them
                paragraphs = [Node("paragraph", content=first)]
                rest = [e for e in extras if e.token.type == "paragraph_open"]
                paragraphs.extend(n for e in rest for n in self._paragraph(e, "blockTaskItem"))
                content.append(Node("blockTaskItem", {"localId": _local_id(), "state": state}, paragraphs))
                extras = [e for e in extras if e.token.type == "bullet_list_open"]
            else:
                content.append(Node(item_type, {"localId": _local_id(), "state": state}, first or None))
            for extra in extras:
                if extra.token.type == "bullet_list_open" and kind == "taskList":
                    nested = extra.children
                    if nested and all(self._task_marker(n) is not None for n in nested):
                        content.append(self._task_list(nested, "taskList"))
                        continue
                self._warn(f"only text and nested task lists fit in a {list_type} item", self._line(extra))
        return Node(list_type, {"localId": _local_id()}, content)

    def _list_item(self, item: _Tree) -> Node:
        return Node("listItem", content=self._blocks(item.children, "listItem"))

    def _blockquote(self, tree: _Tree, parent: str) -> list[Node]:
        first = tree.children[0] if tree.children else None
        if first is not None and first.token.type == "paragraph_open":
            inline = next((c for c in first.children if c.token.type == "inline"), None)
            match = ALERT.match(inline.token.content) if inline else None
            if match and inline is not None:
                panel_type = names.ALERT_TO_PANEL.get(match.group(1).upper())
                if panel_type is None:
                    self._warn(f"unknown alert [!{match.group(1)}]; using info", self._line(first))
                    panel_type = "info"
                rest = inline.token.content[match.end() :]
                blocks: list[Node] = []
                if rest.strip():
                    blocks.append(Node("paragraph", content=self.inline(rest, "paragraph")))
                blocks.extend(self._blocks(tree.children[1:], "panel"))
                return [Node("panel", {"panelType": panel_type}, blocks or [Node("paragraph", content=[])])]
        return [Node("blockquote", content=self._blocks(tree.children, "blockquote"))]

    def _code(self, token: Token) -> list[Node]:
        info = (token.info or "").strip()
        body = token.content[:-1] if token.content.endswith("\n") else token.content
        language, _, rest = info.partition(" ")
        if token.type == "fence" and language == "adf":
            return self._raw_blocks(body, token.map[0] if token.map else None)
        attrs: dict[str, Any] = {}
        if language:
            attrs["language"] = language
        rest = rest.strip()
        if rest.startswith("{"):
            from adflux.markdown.attrs import parse_attrs

            extra, _ = parse_attrs(rest)
            spec = node_spec("codeBlock")
            for key, value in extra.items():
                attrs[key] = spec.attr(key).coerce(value)
        content = [Node("text", text=body)] if body else []
        return [Node("codeBlock", attrs, content)]

    def _raw_blocks(self, body: str, line: int | None) -> list[Node]:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as error:
            raise MarkdownError(f"```adf block is not valid JSON: {error.msg}", line) from None
        items = data if isinstance(data, list) else [data]
        try:
            nodes = [Node.from_json(item) for item in items]
        except AdfError as error:
            raise MarkdownError(f"```adf block: {error}", line) from None
        if len(nodes) == 1 and nodes[0].type == "doc":
            return nodes[0].children
        return nodes

    # -- tables ---------------------------------------------------------------------------
    def _table(self, tree: _Tree) -> Node:
        rows: list[Node] = []
        for section in tree.children:  # thead / tbody
            for row in section.children:
                cells = []
                for cell in row.children:
                    kind = "tableHeader" if cell.token.type == "th_open" else "tableCell"
                    content = self._inline_of(cell, "paragraph")
                    paragraph = Node("paragraph", content=content)
                    style = cell.token.attrs.get("style") or ""
                    align = {"text-align:center": "center", "text-align:right": "end"}.get(str(style))
                    if align:
                        paragraph.marks.append(Mark("alignment", {"align": align}))
                    cells.append(Node(kind, {}, [paragraph]))
                rows.append(Node("tableRow", content=cells))
        return Node("table", {}, rows)

    # -- directives -------------------------------------------------------------------
    def _container(self, tree: _Tree, parent: str) -> list[Node]:
        meta = tree.token.meta
        name: str = meta["name"]
        attrs: dict[str, str] = dict(meta["attrs"])
        line = self._line(tree)
        canonical = names.BLOCK_ALIASES.get(name, name)
        body = tree.children
        if canonical == "panel":
            node_attrs = self._typed("panel", names.rename(attrs, names.PANEL_ATTRS), line)
            node_attrs.setdefault("panelType", "info")
            panel = Node("panel", node_attrs, self._blocks(body, "panel") or [Node("paragraph", content=[])])
            panel.marks = self._block_marks(attrs, line)
            return [panel]
        if canonical in ("expand", "nestedExpand"):
            kind = canonical
            if canonical == "expand" and not self._fits(parent, "expand") and self._fits(parent, "nestedExpand"):
                kind = "nestedExpand"
            node_attrs = self._typed(kind, attrs, line)
            node_attrs.setdefault("title", "")
            expand = Node(kind, node_attrs, self._blocks(body, kind) or [Node("paragraph", content=[])])
            expand.marks = self._block_marks(attrs, line)
            return [expand]
        if canonical == "decisionList" and name == "decisions":
            lists = [c for c in body if c.token.type == "bullet_list_open"]
            if len(lists) != 1 or len(body) != 1:
                raise MarkdownError(":::decisions must contain exactly one list", line)
            return [self._task_list(lists[0].children, "decisionList", line)]
        if canonical == "extension":
            return [self._extension(attrs, meta.get("label"), body, "bodiedExtension", line, meta.get("body"))]
        if canonical in NODES and canonical not in names.LEAF_ONLY:
            return [self._generic(canonical, attrs, body, line, parent)]
        macro = self.profile.macros.get(name)
        if macro is not None or self.profile.unknown_directives_are_macros:
            return [
                self._extension(
                    dict(attrs, **{"adf.key": name}),
                    meta.get("label"),
                    body,
                    "bodiedExtension",
                    line,
                    meta.get("body"),
                )
            ]
        raise MarkdownError(f"unknown directive :::{name} for profile {self.profile.name}", line)

    def _leaf(self, tree: _Tree, parent: str) -> list[Node]:
        meta = tree.token.meta
        name: str = meta["name"]
        attrs: dict[str, str] = dict(meta["attrs"])
        label: str | None = meta.get("label")
        line = self._line(tree)
        canonical = names.BLOCK_ALIASES.get(name, name)
        if canonical == "blockCard":
            return [Node("blockCard", self._typed("blockCard", attrs, line))]
        if canonical == "embedCard":
            return [Node("embedCard", self._typed("embedCard", attrs, line))]
        if canonical == "mediaSingle":
            if not self._fits(parent, "mediaSingle") and self._fits(parent, "media"):
                return [self._generic("media", attrs, [], line, parent)]  # inside mediaGroup
            return [self._media_single(attrs, label, line)]
        if canonical == "extension":
            return self._wrap_inline(self._extension(attrs, label, None, "extension", line), parent)
        if canonical in NODES and canonical not in names.INLINE_ONLY:
            return [self._generic(canonical, attrs, [], line, parent, label)]
        macro = self.profile.macros.get(name)
        if macro is not None or self.profile.unknown_directives_are_macros:
            node = self._extension(dict(attrs, **{"adf.key": name}), label, None, "extension", line)
            return self._wrap_inline(node, parent)
        raise MarkdownError(f"unknown directive ::{name} for profile {self.profile.name}", line)

    def _wrap_inline(self, node: Node, parent: str) -> list[Node]:
        if node.type == "inlineExtension":
            return [Node("paragraph", content=[node])]
        return [node]

    def _typed(self, kind: str, attrs: dict[str, str], line: int | None) -> dict[str, Any]:
        spec = node_spec(kind)
        out: dict[str, Any] = {}
        for key, value in attrs.items():
            if key in names.MARK_ATTRS:
                continue
            try:
                out[key] = spec.attr(key).coerce(value)
            except ValueError as error:
                raise MarkdownError(f"{kind}: {error}", line) from None
        return out

    def _block_marks(self, attrs: dict[str, str], line: int | None) -> list[Mark]:
        marks: list[Mark] = []
        if "align" in attrs:
            marks.append(Mark("alignment", {"align": attrs["align"]}))
        if "indent" in attrs:
            marks.append(Mark("indentation", {"level": int(attrs["indent"])}))
        if "breakout" in attrs:
            breakout: dict[str, Any] = {"mode": attrs["breakout"]}
            if "breakoutWidth" in attrs:
                breakout["width"] = float(attrs["breakoutWidth"])
                if float(breakout["width"]).is_integer():
                    breakout["width"] = int(breakout["width"])
            marks.append(Mark("breakout", breakout))
        if "marks" in attrs:
            try:
                raw = json.loads(attrs["marks"])
                marks.extend(Mark.from_json(m) for m in raw)
            except (json.JSONDecodeError, AdfError, TypeError) as error:
                raise MarkdownError(f"bad marks JSON: {error}", line) from None
        return marks

    def _generic(
        self,
        kind: str,
        attrs: dict[str, str],
        body: list[_Tree],
        line: int | None,
        parent: str,
        label: str | None = None,
    ) -> Node:
        if kind == "expand" and not self._fits(parent, "expand") and self._fits(parent, "nestedExpand"):
            kind = "nestedExpand"
        spec = node_spec(kind)
        node = Node(kind, self._typed(kind, attrs, line))
        node.marks = self._block_marks(attrs, line)
        local_id = spec.attrs.get("localId")
        if local_id is not None and local_id.required and "localId" not in node.attrs:
            node.attrs["localId"] = _local_id()
        if spec.leaf:
            return node
        inline_content = bool(spec.content) and all(NODES.get(c) is None or NODES[c].inline for c in spec.content)
        if inline_content:
            if label is not None:
                node.content = self.inline(label, kind)
            else:
                paragraphs = [t for t in body if t.token.type == "paragraph_open"]
                if len(paragraphs) != len(body) or len(paragraphs) > 1:
                    raise MarkdownError(f":::{kind} holds one paragraph of text", line)
                node.content = self._inline_of(paragraphs[0], kind) if paragraphs else []
        else:
            node.content = self._blocks(body, kind)
        if kind == "layoutSection":
            self._fix_layout(node, line)
        return node

    @staticmethod
    def _fix_layout(section: Node, line: int | None) -> None:
        stray = [c.type for c in section.children if c.type != "layoutColumn"]
        if stray:
            raise MarkdownError(
                "::::layout may only hold :::column blocks (found "
                + ", ".join(sorted(set(stray)))
                + "); give each outer container more colons than the ones inside it",
                line,
            )
        missing = [c for c in section.children if "width" not in c.attrs]
        if missing:
            taken = sum(float(c.attrs["width"]) for c in section.children if "width" in c.attrs)
            share = round(max(100.0 - taken, 0.0) / len(missing), 2)
            for column in missing:
                column.attrs["width"] = int(share) if share == int(share) else share

    def _media_single(self, attrs: dict[str, str], label: str | None, line: int | None) -> Node:
        single_attrs: dict[str, str] = {}
        media_attrs: dict[str, str] = {}
        for key, value in attrs.items():
            if key.startswith("single."):
                single_attrs[key[len("single.") :]] = value
            elif key in ("layout",):
                single_attrs[key] = value
            else:
                media_attrs[key] = value
        media_attrs.setdefault("type", "external" if "url" in media_attrs else "file")
        single = Node("mediaSingle", self._typed("mediaSingle", single_attrs, line))
        single.attrs.setdefault("layout", "center")
        single.content = [Node("media", self._typed("media", media_attrs, line))]
        if label:
            single.content.append(Node("caption", content=self.inline(label, "caption")))
        return single

    def _extension(
        self,
        attrs: dict[str, str],
        label: str | None,
        body: list[_Tree] | None,
        default_kind: str,
        line: int | None,
        raw: str | None = None,
    ) -> Node:
        key = attrs.pop("adf.key", None) or attrs.pop("key", None)
        if not key:
            raise MarkdownError("an extension needs adf.key", line)
        ext_type = attrs.pop("adf.type", None) or self.profile.macros.extension_type or CONFLUENCE_MACRO_TYPE
        macro = self.profile.macros.get(key) if ext_type == self.profile.macros.extension_type else None
        kind = default_kind
        if body is None and macro is not None and macro.node == "inlineExtension":
            kind = "inlineExtension"
        if macro is not None and macro.native and not any(k.startswith("adf.") for k in attrs):
            native = self._native(macro, attrs, label, body, raw, line)
            if native is not None:
                return native
        return self._make_extension(kind, key, ext_type, attrs, label, body, macro, line)

    def _native(
        self,
        macro: Any,
        attrs: dict[str, str],
        label: str | None,
        body: list[_Tree] | None,
        raw: str | None,
        line: int | None,
    ) -> Node | None:
        """Build the native ADF node Confluence stores for a macro (``:::info`` -> panel)."""
        text = self.plain(label)
        params = dict(attrs)
        if text is not None and names.label_param(macro):
            params.setdefault(names.label_param(macro), text)

        def dropped(*kept: str) -> None:
            extra = sorted(set(params) - set(kept))
            if extra:
                self._warn(f"Confluence drops {', '.join(extra)} on the {macro.name} macro", line)

        if macro.node == "panel" and body is not None:
            content = self._blocks(body, "panel") or [Node("paragraph", content=[])]
            if macro.name in ("panel", "bgcolor"):
                color = params.get("bgColor") or params.get("color")
                dropped("bgColor", "color")
                return Node("panel", {"panelType": "custom", **({"panelColor": color} if color else {})}, content)
            dropped()
            return Node("panel", {"panelType": names.MACRO_PANELS.get(macro.name, "info")}, content)
        if macro.node == "codeBlock" and body is not None:
            language = params.get("language")
            dropped("language")
            code = raw if raw is not None else "\n".join(t.text_content() for t in self._blocks(body, "doc"))
            return Node(
                "codeBlock", {"language": language} if language else {}, [Node("text", text=code)] if code else []
            )
        if macro.node == "expand" and body is not None:
            dropped("title")
            return Node(
                "expand",
                {"title": params.get("title", "")},
                self._blocks(body, "expand") or [Node("paragraph", content=[])],
            )
        if macro.node == "status":
            dropped("title", "colour")
            colour = params.get("colour", "Grey").lower()
            color = {"grey": "neutral", "gray": "neutral"}.get(colour, colour)
            return Node("status", {"text": params.get("title", ""), "color": color})
        return None

    def _make_extension(
        self,
        kind: str,
        key: str,
        ext_type: str,
        attrs: dict[str, str],
        label: str | None,
        body: list[_Tree] | None,
        macro: Any,
        line: int | None,
    ) -> Node:
        node_attrs: dict[str, Any] = {"extensionType": ext_type, "extensionKey": key}
        reserved = {k: attrs.pop(k) for k in list(attrs) if k.startswith("adf.")}
        if "adf.params" in reserved:
            try:
                parameters_value = json.loads(reserved.pop("adf.params"))
            except json.JSONDecodeError as error:
                raise MarkdownError(f"adf.params is not JSON: {error.msg}", line) from None
            if parameters_value is not None:  # null: the node has no parameters
                node_attrs["parameters"] = parameters_value
        else:
            params: dict[str, Any] = {}
            if label is not None:
                params[names.label_param(macro)] = {"value": self.plain(label)}
            for name, value in attrs.items():
                params[name] = {"value": value}
            if "adf.body" in reserved:
                params["__bodyContent"] = {"value": reserved.pop("adf.body")}
            parameters: dict[str, Any] = {"macroParams": params}
            if "adf.meta" in reserved:
                try:
                    parameters["macroMetadata"] = json.loads(reserved.pop("adf.meta"))
                except json.JSONDecodeError as error:
                    raise MarkdownError(f"adf.meta is not JSON: {error.msg}", line) from None
            node_attrs["parameters"] = parameters
        for name in ("layout", "localId", "text"):
            if f"adf.{name}" in reserved:
                node_attrs[name] = reserved.pop(f"adf.{name}")
        if reserved:
            unknown = ", ".join(sorted(reserved))
            raise MarkdownError(f"unknown extension attributes: {unknown}", line)
        node = Node(kind, node_attrs)
        if kind == "bodiedExtension":
            node.content = self._blocks(body or [], "bodiedExtension") or [Node("paragraph", content=[])]
        return node

    # -- inline -----------------------------------------------------------------------
    def _inlines(self, tokens: list[Token], parent: str, base: list[Mark] | None = None) -> list[Node]:
        out: list[Node] = []
        marks: list[Mark] = list(base or [])
        index = 0
        while index < len(tokens):
            token = tokens[index]
            kind = token.type
            if kind == "text":
                if token.content:
                    out.append(Node("text", text=token.content, marks=list(marks)))
            elif kind == "softbreak":
                out.append(Node("text", text=" ", marks=list(marks)))
            elif kind == "hardbreak":
                out.append(Node("hardBreak"))
            elif kind in ("strong_open", "em_open", "s_open"):
                marks.append(Mark({"strong_open": "strong", "em_open": "em", "s_open": "strike"}[kind]))
            elif kind in ("strong_close", "em_close", "s_close"):
                self._pop(marks, {"strong_close": "strong", "em_close": "em", "s_close": "strike"}[kind])
            elif kind == "code_inline":
                code_marks = [m for m in marks if m.type == "link"] + [Mark("code")]
                if token.content:
                    out.append(Node("text", text=token.content, marks=code_marks))
            elif kind == "link_open":
                if token.markup == "autolink" and token.info == "auto":
                    url = str(token.attrs.get("href", ""))
                    # skip text and close: autolinks become smart links (inlineCard)
                    while index < len(tokens) and tokens[index].type != "link_close":
                        index += 1
                    if url.startswith("mailto:"):
                        out.append(
                            Node("text", text=url[len("mailto:") :], marks=[*marks, Mark("link", {"href": url})])
                        )
                    else:
                        out.append(_marked(Node("inlineCard", {"url": url}), marks))
                else:
                    link: dict[str, Any] = {"href": str(token.attrs.get("href", ""))}
                    if token.attrs.get("title"):
                        link["title"] = str(token.attrs["title"])
                    marks.append(Mark("link", link))
            elif kind == "link_close":
                self._pop(marks, "link")
            elif kind == "image":
                alt = _plain_tokens(token.children or [])
                src = str(token.attrs.get("src", ""))
                self._warn("inline images become links (ADF has no inline external image)")
                out.append(Node("text", text=alt or src, marks=[*marks, Mark("link", {"href": src})]))
            elif kind == "html_inline":
                self._html(token.content, marks, out)
            elif kind == "emoji":
                out.append(_marked(Node("emoji", dict(token.meta["attrs"])), marks))
            elif kind == "directive_inline_open":
                depth = 1
                end = index + 1
                while end < len(tokens):
                    if tokens[end].type == "directive_inline_open":
                        depth += 1
                    elif tokens[end].type == "directive_inline_close":
                        depth -= 1
                        if depth == 0:
                            break
                    end += 1
                inner = tokens[index + 1 : end]
                try:
                    made = self._inline_directive(token.meta, inner, marks, parent)
                except (ValueError, TypeError, json.JSONDecodeError, AdfError) as error:
                    if isinstance(error, MarkdownError):
                        raise
                    raise MarkdownError(f":{token.meta['name']}: {error}") from None
                out.extend(n if n.type == "text" else _marked(n, marks) for n in made)
                index = end
            index += 1
        return out

    @staticmethod
    def _pop(marks: list[Mark], kind: str) -> None:
        for i in range(len(marks) - 1, -1, -1):
            if marks[i].type == kind:
                del marks[i]
                return

    def _html(self, raw: str, marks: list[Mark], out: list[Node]) -> None:
        match = HTML_TAG.match(raw.strip())
        tag = match.group(2).lower() if match else ""
        closing = bool(match and match.group(1))
        if tag == "br":
            out.append(Node("hardBreak"))
            return
        mapping = {
            "u": ("underline", None),
            "ins": ("underline", None),
            "sub": ("subsup", "sub"),
            "sup": ("subsup", "sup"),
            "strong": ("strong", None),
            "b": ("strong", None),
            "em": ("em", None),
            "i": ("em", None),
            "del": ("strike", None),
            "s": ("strike", None),
        }
        if tag in mapping:
            kind, sub = mapping[tag]
            if closing:
                self._pop(marks, kind)
            else:
                marks.append(Mark(kind, {"type": sub} if sub else {}))
            return
        out.append(Node("text", text=raw, marks=list(marks)))

    def _inline_directive(self, meta: dict[str, Any], inner: list[Token], marks: list[Mark], parent: str) -> list[Node]:
        name: str = meta["name"]
        attrs: dict[str, str] = dict(meta["attrs"])
        raw_label: str | None = meta.get("label")
        canonical = names.INLINE_ALIASES.get(name, name)
        if canonical == "span":
            return self._inlines(inner, parent, list(marks) + self._span_marks(attrs))
        label = _plain_tokens(inner) if raw_label is not None else None
        if canonical == "status":
            node_attrs = self._typed("status", attrs, None)
            node_attrs["text"] = label or node_attrs.get("text", "")
            node_attrs.setdefault("color", "neutral")
            return [Node("status", node_attrs)]
        if canonical == "date":
            node_attrs = self._typed("date", attrs, None)
            if label:
                node_attrs["timestamp"] = names.date_to_timestamp(label)
            return [Node("date", node_attrs)]
        if canonical == "mention":
            node_attrs = self._typed("mention", attrs, None)
            if label is not None and "text" not in node_attrs:
                node_attrs["text"] = label if label.startswith("@") else "@" + label
            if "id" not in node_attrs:
                resolved = self.profile.mention_resolver(label or "") if self.profile.mention_resolver else None
                if not resolved:
                    self._warn(f"mention {label!r} has no id; kept as text")
                    return [Node("text", text=node_attrs.get("text", label or ""), marks=list(marks))]
                node_attrs = {**node_attrs, **resolved}
            return [Node("mention", node_attrs)]
        if canonical == "emoji":
            # a label is authoring shorthand that the profile completes; attributes are exact
            resolved = self.profile.resolve_emoji(label) if label else None
            node_attrs = dict(resolved or {})
            node_attrs.update(self._typed("emoji", attrs, None))
            if label and "shortName" not in attrs:
                node_attrs["shortName"] = label if label.startswith(":") else f":{label}:"
            return [Node("emoji", node_attrs)]
        if canonical == "inlineCard":
            return [Node("inlineCard", self._typed("inlineCard", attrs, None))]
        if canonical == "adf":
            try:
                data = json.loads(attrs.get("json", "null"))
                return [Node.from_json(item) for item in (data if isinstance(data, list) else [data])]
            except (json.JSONDecodeError, AdfError) as error:
                raise MarkdownError(f":adf json: {error}") from None
        if canonical == "extension":
            return [self._extension(attrs, raw_label, None, "inlineExtension", None)]
        if canonical in NODES and NODES[canonical].inline:
            node = Node(canonical, self._typed(canonical, attrs, None))
            if label and not NODES[canonical].leaf:
                node.content = self._inlines(inner, canonical, marks)
            return [node]
        macro = self.profile.macros.get(name)
        if macro is not None or self.profile.unknown_directives_are_macros:
            return [self._extension(dict(attrs, **{"adf.key": name}), raw_label, None, "inlineExtension", None)]
        self._warn(f"unknown inline directive :{name}; kept as text")
        return [Node("text", text=str(meta.get("source") or f":{name}"), marks=list(marks))]

    @staticmethod
    def _span_marks(attrs: dict[str, str]) -> list[Mark]:
        marks: list[Mark] = []
        if "color" in attrs:
            marks.append(Mark("textColor", {"color": attrs["color"]}))
        if "background" in attrs:
            marks.append(Mark("backgroundColor", {"color": attrs["background"]}))
        if "size" in attrs:
            marks.append(Mark("fontSize", {"fontSize": attrs["size"]}))
        if "marks" in attrs:
            try:
                raw_marks = json.loads(attrs["marks"])
            except json.JSONDecodeError as error:
                raise MarkdownError(f"marks must be a JSON array: {error.msg}") from None
            if not isinstance(raw_marks, list):
                raise MarkdownError("marks must be a JSON array")
            for raw in raw_marks:
                found = Mark.from_json(raw)
                spec = mark_spec(found.type)
                found.attrs = {k: v for k, v in found.attrs.items() if spec.attr(k)}
                marks.append(found)
        return marks


def _marked(node: Node, marks: list[Mark]) -> Node:
    """Give an inline node the active marks its type allows (a link around an inline card)."""
    allowed = node_spec(node.type).marks
    node.marks = [*node.marks, *(m for m in marks if m.type in allowed and m not in node.marks)]
    return node


def _plain_tokens(tokens: list[Token]) -> str:
    """Return the text of inline tokens with Markdown escapes and entities resolved.

    A nested directive contributes its source text.
    """
    parts: list[str] = []
    depth = 0
    for token in tokens:
        if token.type == "directive_inline_open":
            if depth == 0:
                parts.append(str(token.meta.get("source", "")))
            depth += 1
        elif token.type == "directive_inline_close":
            depth -= 1
        elif depth:
            continue
        elif token.type in ("text", "code_inline", "html_inline", "emoji"):
            parts.append(token.content)
        elif token.type == "softbreak":
            parts.append(" ")
        elif token.type == "hardbreak":
            parts.append("\n")
        elif token.children:
            parts.append(_plain_tokens(token.children))
    return "".join(parts)


def timestamp_now() -> str:
    """Return the current time as an ADF date timestamp (milliseconds)."""
    return str(int(datetime.now(UTC).timestamp() * 1000))


def markdown_to_adf(source: str, profile: Profile, *, strict: bool = False) -> Node:
    """Convert Markdown to an ADF document."""
    return Reader(profile, strict=strict).read(source)


def parse_adf_text(value: str) -> Node:
    """Parse ADF JSON text (helper for symmetry with :func:`markdown_to_adf`)."""
    return load(value)
