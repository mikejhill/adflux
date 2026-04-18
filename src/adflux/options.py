"""Conversion options.

Options govern how the converter handles nodes that cannot be natively
represented in the target format, and control format-specific behaviors.

Options are generic key=value pairs validated by a central
:class:`OptionRegistry`. Each reader or writer inspects the :class:`Options`
bag to decide its behavior.

Core Options
------------

=================  =====================================  ===========
Name               Choices                                Default
=================  =====================================  ===========
``envelopes``      ``keep``, ``drop``, ``keep-strict``    ``keep``
``jira-strict``    ``true``, ``false``                    ``false``
=================  =====================================  ===========

**Envelopes** are panflute ``Div`` (block) or ``Span`` (inline) nodes whose
CSS class starts with ``adf-*``, representing ADF constructs with no native
counterpart in the target format (panels, macros, mentions, status badges).
Envelopes carry the original ADF node type and attributes so the conversion
is reversible.

- ``keep`` — preserve envelopes for lossless round-tripping (default).
- ``drop`` — silently strip envelopes; block envelopes are replaced by their
  children, inline envelopes collapse to their visible content, and
  content-less envelopes are removed entirely.
- ``keep-strict`` — preserve envelopes, but raise
  :class:`~adflux.errors.UnrepresentableNodeError` on the first envelope
  encountered when writing to a lossy target.

**jira-strict** — when ``true``, ADF serialization rejects node types that
are not part of Jira's description ADF profile (e.g. ``layoutSection``,
``taskList``, ``decisionList``, extensions).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OptionDef:
    """Definition of a single conversion option."""

    name: str
    """Machine-readable key (e.g. ``"envelopes"``)."""

    description: str
    """Human-readable description, shown in CLI ``--help``."""

    choices: tuple[str, ...] | None = None
    """Allowed values, or ``None`` for free-form."""

    default: str = ""
    """Default value when the option is not explicitly set."""


class Options:
    """Immutable bag of validated key=value conversion options.

    Construct via :meth:`OptionRegistry.resolve` or directly from a dict.
    Accessing an unknown key returns the registry default (or ``""`` if the
    key is not registered).
    """

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, str] | None = None) -> None:
        self._data: dict[str, str] = dict(data) if data else {}

    def __getitem__(self, key: str) -> str:
        try:
            return self._data[key]
        except KeyError:
            defn = _REGISTRY.get(key)
            if defn is not None:
                return defn.default
            return ""

    def get(self, key: str, default: str = "") -> str:
        """Return the value for *key*, falling back to *default*."""
        try:
            return self._data[key]
        except KeyError:
            defn = _REGISTRY.get(key)
            if defn is not None:
                return defn.default
            return default

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"Options({self._data!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Options):
            return self._data == other._data
        return NotImplemented

    def items(self) -> list[tuple[str, str]]:
        """Return all explicitly-set option pairs."""
        return list(self._data.items())

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


class OptionRegistry:
    """IoC registry for option definitions.

    Option definitions are registered at import time by format modules.
    The registry validates user-supplied options and provides
    self-documentation for CLI help output.
    """

    def __init__(self) -> None:
        self._defs: dict[str, OptionDef] = {}

    def register(self, defn: OptionDef) -> None:
        """Register an :class:`OptionDef`. Overwrites if name already exists."""
        self._defs[defn.name] = defn

    def get(self, name: str) -> OptionDef | None:
        """Return the definition for *name*, or ``None``."""
        return self._defs.get(name)

    def all(self) -> list[OptionDef]:
        """Return all registered definitions, sorted by name."""
        return sorted(self._defs.values(), key=lambda d: d.name)

    def resolve(self, raw: dict[str, Any] | Options | None = None) -> Options:
        """Validate and resolve *raw* into an :class:`Options` instance.

        Args:
            raw: ``None``, a ``dict[str, str]``, or an existing
                 :class:`Options` instance (returned as-is).

        Returns:
            Validated :class:`Options` with defaults applied.

        Raises:
            ValueError: If a key is unknown or a value is not in choices.
        """
        if raw is None:
            return Options({d.name: d.default for d in self._defs.values()})
        if isinstance(raw, Options):
            return raw

        data: dict[str, str] = {}
        for key, value in raw.items():
            defn = self._defs.get(key)
            if defn is None:
                raise ValueError(
                    f"Unknown option {key!r}. Known options: {', '.join(sorted(self._defs))}"
                )
            val = str(value)
            if defn.choices is not None and val not in defn.choices:
                raise ValueError(
                    f"Invalid value {val!r} for option {key!r}. Allowed: {', '.join(defn.choices)}"
                )
            data[key] = val

        # Apply defaults for unset options.
        for defn in self._defs.values():
            if defn.name not in data:
                data[defn.name] = defn.default

        return Options(data)


# ---------------------------------------------------------------------------
# Global singleton registry
# ---------------------------------------------------------------------------

_REGISTRY = OptionRegistry()


def get_registry() -> OptionRegistry:
    """Return the global :class:`OptionRegistry` singleton."""
    return _REGISTRY


# ---------------------------------------------------------------------------
# Core option definitions
# ---------------------------------------------------------------------------

_REGISTRY.register(
    OptionDef(
        name="envelopes",
        description=(
            "How ADF envelope nodes are handled on lossy targets. "
            "'keep' preserves for lossless round-tripping, "
            "'drop' silently strips envelopes keeping visible content, "
            "'keep-strict' raises on unrepresentable envelopes."
        ),
        choices=("keep", "drop", "keep-strict"),
        default="keep",
    )
)

_REGISTRY.register(
    OptionDef(
        name="jira-strict",
        description=(
            "When 'true', ADF serialization rejects node types not in "
            "Jira's description ADF profile (e.g. layoutSection, "
            "taskList, decisionList, extensions)."
        ),
        choices=("true", "false"),
        default="false",
    )
)
