"""Names shared by the Markdown reader and writer: directive aliases and attribute maps."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# Alerts (GitHub syntax) <-> panel types. GitHub's own five names are accepted too.
PANEL_TO_ALERT = {
    "info": "INFO",
    "note": "NOTE",
    "tip": "TIP",
    "success": "SUCCESS",
    "warning": "WARNING",
    "error": "ERROR",
}
ALERT_TO_PANEL = {v: k for k, v in PANEL_TO_ALERT.items()} | {"IMPORTANT": "note", "CAUTION": "error"}

# Confluence macros that Confluence itself stores as panels (captured from a live site).
MACRO_PANELS = {"info": "info", "tip": "success", "note": "warning", "warning": "error", "panel": "custom"}

# Friendly attribute names on :::panel.
PANEL_ATTRS = {
    "type": "panelType",
    "color": "panelColor",
    "icon": "panelIcon",
    "iconId": "panelIconId",
    "iconText": "panelIconText",
}

# Short directive names -> ADF node types. Any ADF node type name works as well.
BLOCK_ALIASES = {
    "panel": "panel",
    "expand": "expand",
    "decisions": "decisionList",
    "layout": "layoutSection",
    "column": "layoutColumn",
    "row": "tableRow",
    "cell": "tableCell",
    "header": "tableHeader",
    "card": "blockCard",
    "embed": "embedCard",
    "media": "mediaSingle",
    "image": "mediaSingle",
    "extension": "extension",
    "macro": "extension",
    "quote": "blockquote",
}
INLINE_ALIASES = {
    "span": "span",
    "status": "status",
    "date": "date",
    "mention": "mention",
    "emoji": "emoji",
    "card": "inlineCard",
    "adf": "adf",
    "extension": "extension",
    "macro": "extension",
}
# Names a macro cannot use in short form because they mean something else.
RESERVED = frozenset(BLOCK_ALIASES) | frozenset(INLINE_ALIASES) | {"paragraph", "heading", "table"}

# Node types that are never containers / never block leaves in directive form.
LEAF_ONLY = frozenset({"blockCard", "embedCard", "rule", "extension", "media", "mediaSingle"})
INLINE_ONLY = frozenset({"text", "hardBreak", "status", "date", "mention", "emoji", "inlineCard", "placeholder"})

# Block-mark attributes (alignment, indentation, breakout, raw marks) on generic directives.
MARK_ATTRS = frozenset({"align", "indent", "breakout", "breakoutWidth", "marks"})


def rename(attrs: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    """Return ``attrs`` with friendly keys replaced by ADF names."""
    return {mapping.get(key, key): value for key, value in attrs.items()}


def unrename(attrs: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Inverse of :func:`rename`."""
    reverse = {v: k for k, v in mapping.items()}
    return {reverse.get(key, key): value for key, value in attrs.items()}


def label_param(macro: Any) -> str:
    """Return the macro parameter a directive label fills.

    That is the default ("") parameter, else the first required one, else the first one.
    """
    if macro is None or not macro.params:
        return ""
    for param in macro.params:
        if param.name == "":
            return ""
    for param in macro.params:
        if param.required:
            return param.name
    return macro.params[0].name


def date_to_timestamp(label: str) -> str:
    """Turn ``2025-11-21`` (UTC midnight) or an ISO datetime into epoch milliseconds."""
    text = label.strip()
    if text.isdigit():
        return text
    try:
        if len(text) == 10:
            moment = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)
        else:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=UTC)
    except ValueError:
        raise ValueError(f"not a date: {label!r} (use YYYY-MM-DD)") from None
    return str(int(moment.timestamp() * 1000))


def timestamp_to_date(timestamp: str) -> str | None:
    """Return ``YYYY-MM-DD`` when ``timestamp`` is a UTC midnight, else ``None``."""
    try:
        millis = int(timestamp)
    except (TypeError, ValueError):
        return None
    if millis % 86_400_000:
        return None
    return datetime.fromtimestamp(millis / 1000, UTC).strftime("%Y-%m-%d")
