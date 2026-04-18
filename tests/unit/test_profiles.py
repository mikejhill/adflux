"""Tests for fidelity-profile resolution."""

from __future__ import annotations

import pytest

from adflux.profiles import Profile, all_profile_names, resolve_profile


def test_all_profile_names_nonempty():
    names = all_profile_names()
    assert "strict-adf" in names
    assert "pretty-md" in names
    assert "fail-loud" in names


@pytest.mark.parametrize("name", ["strict-adf", "pretty-md", "fail-loud"])
def test_resolve_profile_by_name(name):
    profile = resolve_profile(name)
    assert isinstance(profile, Profile)
    assert profile.name == name


def test_resolve_profile_passthrough_instance():
    p = resolve_profile("strict-adf")
    assert resolve_profile(p) is p


def test_resolve_profile_unknown():
    with pytest.raises(ValueError, match="Unknown profile"):
        resolve_profile("nope")


def test_strict_adf_preserves_envelopes():
    p = resolve_profile("strict-adf")
    assert p.preserve_envelopes is True
    assert p.drop_unrepresentable is False
    assert p.fail_on_unrepresentable is False


def test_fail_loud_fails():
    assert resolve_profile("fail-loud").fail_on_unrepresentable is True


def test_pretty_md_drops():
    p = resolve_profile("pretty-md")
    assert p.drop_unrepresentable is True
    assert p.preserve_envelopes is False
