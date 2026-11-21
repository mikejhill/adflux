"""Product profiles: what differs between Jira, Confluence and plain ADF.

Both products store any schema-valid ADF, but they differ in what renders and in what text
shortcuts mean:

* **Macros** exist only in Confluence (``extension`` nodes of type
  ``com.atlassian.confluence.macro.core``). In the Confluence profile an unknown directive
  such as ``::recently-updated{max=5}`` becomes a macro; in Jira it is an error.
* **Emoticon aliases** follow each product's own shortcuts: Confluence emoticon names
  (``:tick:``, ``:information:``) and Jira wiki emoticon names (``:(/):`` is not valid
  Markdown, so the Jira aliases use words: ``:tick:``, ``:cross:``, ``:info:``...).
* **Rendering gaps**: Jira does not render layouts or Confluence macros; converting such
  nodes for Jira produces a warning, not an error, because Jira still stores them.
* **Mentions** need an account id; a profile can carry a resolver that turns ``@Name`` or
  an email into one (codas plug in a user search).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from adflux.profiles.emoji import EmojiIndex, default_index
from adflux.profiles.macros import MacroCatalog, confluence_catalog, empty_catalog

MentionResolver = Callable[[str], dict[str, Any] | None]
"""Turns ``@Name``/email text into ADF mention attrs (``{"id": ..., "text": "@Name"}``)."""

# How each product turns its own emoticon names into emoji (captured from live sites).
CONFLUENCE_EMOTICONS = {
    "smile": "slight_smile",
    "sad": "slight_frown",
    "cheeky": "stuck_out_tongue",
    "laugh": "grinning",
    "wink": "wink",
    "tick": "atlassian-check_mark",
    "cross": "atlassian-cross_mark",
    "information": "atlassian-info",
    "warning": "atlassian-warning",
    "question": "atlassian-question_mark",
    "plus": "heavy_plus_sign",
    "minus": "heavy_minus_sign",
    "thumbs-up": "thumbsup",
    "thumbs-down": "thumbsdown",
    "light-on": "atlassian-light_bulb_on",
    "light-off": "atlassian-light_bulb_off",
    "yellow-star": "atlassian-yellow_star",
    "red-star": "atlassian-red_star",
    "green-star": "atlassian-green_star",
    "blue-star": "atlassian-blue_star",
    "heart": "heart",
    "broken-heart": "broken_heart",
}
JIRA_EMOTICONS = {
    # Jira wiki markup emoticons: (/) (x) (!) (?) (i) (on) (off) (*) (y) (n)
    "tick": "atlassian-check_mark",
    "cross": "atlassian-cross_mark",
    "warning": "atlassian-warning",
    "question": "atlassian-question_mark",
    "info": "atlassian-info",
    "light-on": "atlassian-light_bulb_on",
    "light-off": "atlassian-light_bulb_off",
    "star": "atlassian-yellow_star",
    "yes": "thumbsup",
    "no": "thumbsdown",
}

CONFLUENCE_ONLY = frozenset(
    {"extension", "bodiedExtension", "inlineExtension", "layoutSection", "layoutColumn", "syncBlock", "bodiedSyncBlock"}
)


@dataclass(frozen=True)
class Profile:
    """Product-specific conversion settings."""

    name: str
    emoji: EmojiIndex = field(default_factory=default_index)
    emoticons: dict[str, str] = field(default_factory=dict)
    macros: MacroCatalog = field(default_factory=empty_catalog)
    unknown_directives_are_macros: bool = False
    unsupported: frozenset[str] = frozenset()
    mention_resolver: MentionResolver | None = None

    def resolve_emoji(self, code: str) -> dict[str, str] | None:
        """Return emoji attrs for ``:code:`` (aliases first), or ``None``."""
        code = code.strip(":")
        found = self.emoji.resolve(code)
        if found is None and code in self.emoticons:
            found = self.emoji.resolve(self.emoticons[code])
        return found.attrs() if found else None

    def emoji_code(self, attrs: dict[str, Any]) -> str | None:
        """Return ``name`` so that ``:name:`` reproduces ``attrs``, or ``None``."""
        short = str(attrs.get("shortName") or "")
        emoji_id = attrs.get("id")
        found = self.emoji.resolve(short) if short else None
        if found is not None and emoji_id not in (None, found.id):
            found = None
        if found is not None:
            expected = found.attrs()
            if attrs.get("text") not in (None, expected["text"]):
                return None
            return short.strip(":")
        if emoji_id:
            by_id = self.emoji.resolve(str(emoji_id))
            if (
                by_id is not None
                and by_id.id == emoji_id
                and self.emoji.resolve(by_id.id) is by_id
                and f":{by_id.short_name}:" == short
                and attrs.get("text") in (None, by_id.text)
            ):
                return by_id.id
        return None

    def with_mentions(self, resolver: MentionResolver) -> Profile:
        """Return a copy that resolves mentions with ``resolver``."""
        return replace(self, mention_resolver=resolver)


GENERIC = Profile("generic", macros=confluence_catalog())
JIRA = Profile("jira", emoticons=JIRA_EMOTICONS, unsupported=CONFLUENCE_ONLY)
CONFLUENCE = Profile(
    "confluence",
    emoticons=CONFLUENCE_EMOTICONS,
    macros=confluence_catalog(),
    unknown_directives_are_macros=True,
)

PROFILES = {"generic": GENERIC, "jira": JIRA, "confluence": CONFLUENCE}


def get_profile(profile: str | Profile | None) -> Profile:
    """Return a profile by name (``jira``, ``confluence``, ``generic``) or pass one through."""
    if isinstance(profile, Profile):
        return profile
    try:
        return PROFILES[(profile or "generic").lower()]
    except KeyError:
        raise ValueError(f"unknown profile {profile!r}; use jira, confluence or generic") from None
