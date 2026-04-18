"""Fidelity profiles.

Profiles govern how the converter handles nodes that cannot be natively
represented in the target format. A profile is a small immutable record;
readers/writers inspect its fields to decide their behavior.

Profiles
--------

=================  ===================================================================
Name               Behavior on non-representable nodes
=================  ===================================================================
``strict-adf``     Preserve every ADF node via envelope Divs/Spans (default). Lossless.
``pretty-md``      Drop ADF-only constructs when target is MD; emit warnings.
``fail-loud``      Raise :class:`UnrepresentableNodeError` with location.
=================  ===================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProfileName = Literal["strict-adf", "pretty-md", "fail-loud"]


@dataclass(frozen=True, slots=True)
class Profile:
    """Immutable fidelity profile."""

    name: ProfileName
    preserve_envelopes: bool
    """If True, envelope Divs/Spans are written verbatim to lossy targets."""
    drop_unrepresentable: bool
    """If True, silently drop unrepresentable nodes; else emit envelope or raise."""
    fail_on_unrepresentable: bool
    """If True, raise UnrepresentableNodeError on any loss."""


_PROFILES: dict[str, Profile] = {
    "strict-adf": Profile(
        name="strict-adf",
        preserve_envelopes=True,
        drop_unrepresentable=False,
        fail_on_unrepresentable=False,
    ),
    "pretty-md": Profile(
        name="pretty-md",
        preserve_envelopes=False,
        drop_unrepresentable=True,
        fail_on_unrepresentable=False,
    ),
    "fail-loud": Profile(
        name="fail-loud",
        preserve_envelopes=True,
        drop_unrepresentable=False,
        fail_on_unrepresentable=True,
    ),
}


def resolve_profile(profile: str | Profile) -> Profile:
    """Resolve ``profile`` to a :class:`Profile` instance.

    Args:
        profile: Profile name or instance.

    Raises:
        ValueError: If ``profile`` is an unknown name.
    """
    if isinstance(profile, Profile):
        return profile
    try:
        return _PROFILES[profile]
    except KeyError as exc:
        known = ", ".join(sorted(_PROFILES))
        raise ValueError(f"Unknown profile {profile!r}. Known: {known}") from exc


def all_profile_names() -> list[str]:
    """Return the list of known profile names, sorted."""
    return sorted(_PROFILES)
