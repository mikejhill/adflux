"""Product profiles (Jira, Confluence, generic), emoji and macro catalogs."""

from adflux.profiles.emoji import Emoji, EmojiIndex
from adflux.profiles.macros import Macro, MacroCatalog, MacroParam
from adflux.profiles.profile import CONFLUENCE, GENERIC, JIRA, Profile, get_profile

__all__ = [
    "CONFLUENCE",
    "GENERIC",
    "JIRA",
    "Emoji",
    "EmojiIndex",
    "Macro",
    "MacroCatalog",
    "MacroParam",
    "Profile",
    "get_profile",
]
