"""Emoji shortcodes for Atlassian products.

Atlassian documents store an emoji as ``{"shortName": ":grinning:", "id": "1f600", "text":
"😀"}``. Two sets ship with every site: the standard Unicode set (ids are code points) and
the Atlassian set (ids ``atlassian-<name>``, e.g. ``:check_mark:``). Some short names exist
in both (``:warning:``), so the id is what identifies an emoji. Sites can add custom emoji;
pass them to :class:`EmojiIndex` (``extra``) when a coda can list them.

Resolution of ``:name:`` in Markdown: a standard short name, then an Atlassian short name,
then an extra (site) short name, then an id (``:atlassian-warning:``, ``:1f600:``).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from importlib import resources


@dataclass(frozen=True, slots=True)
class Emoji:
    """One emoji as ADF stores it."""

    short_name: str  # without colons
    id: str
    text: str
    hidden: bool = False

    def attrs(self) -> dict[str, str]:
        """Return ADF ``emoji`` node attributes."""
        return {"shortName": f":{self.short_name}:", "id": self.id, "text": self.text}


class EmojiIndex:
    """Look up emoji by short name or id."""

    def __init__(self, groups: Iterable[Iterable[Emoji]]) -> None:
        self._by_name: dict[str, Emoji] = {}
        self._by_id: dict[str, Emoji] = {}
        for group in groups:
            for emoji in group:
                self._by_name.setdefault(emoji.short_name, emoji)
                self._by_id.setdefault(emoji.id, emoji)

    def resolve(self, code: str) -> Emoji | None:
        """Return the emoji ``:code:`` stands for, or ``None``."""
        code = code.strip(":")
        return self._by_name.get(code) or self._by_id.get(code)

    def shortcode(self, short_name: str, emoji_id: str | None) -> str | None:
        """Return the shortest ``name`` such that ``:name:`` resolves to this emoji."""
        name = short_name.strip(":")
        found = self._by_name.get(name)
        if found is not None and (emoji_id is None or found.id == emoji_id):
            return name
        if emoji_id and emoji_id in self._by_id and self._by_name.get(emoji_id) is None:
            return emoji_id
        return None

    def search(self, query: str, limit: int = 20) -> list[Emoji]:
        """Return emoji whose short name contains ``query`` (visible ones first)."""
        query = query.lower().strip(":")
        found = [e for e in self._by_id.values() if query in e.short_name.lower()]
        found.sort(key=lambda e: (e.hidden, not e.short_name.startswith(query), e.short_name))
        return found[:limit]

    def __len__(self) -> int:
        return len(self._by_id)


@cache
def _builtin() -> dict[str, tuple[Emoji, ...]]:
    raw = json.loads(resources.files("adflux.profiles").joinpath("data/emoji.json").read_text(encoding="utf-8"))
    return {group: tuple(Emoji(row[0], row[1], row[2], bool(row[3])) for row in rows) for group, rows in raw.items()}


def standard() -> tuple[Emoji, ...]:
    """Return the standard (Unicode) emoji set."""
    return _builtin()["standard"]


def atlassian() -> tuple[Emoji, ...]:
    """Return the Atlassian emoji set (``:check_mark:``, ``:info:``...)."""
    return _builtin()["atlassian"]


@cache
def default_index() -> EmojiIndex:
    """Return the index both Jira and Confluence use: standard, then Atlassian."""
    return EmojiIndex([standard(), atlassian()])
