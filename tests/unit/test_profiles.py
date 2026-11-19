"""Profile inheritance."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from lupaxa.github_intel.config.models import ProfileSpec
from lupaxa.github_intel.config.profiles import resolve_profile
from lupaxa.github_intel.errors import ConfigError


def _profiles() -> dict[str, ProfileSpec]:
    return {
        "base": ProfileSpec(
            releases=True,
            workflows=False,
            issues=False,
        ),
        "maintained": ProfileSpec(
            extends="base",
            workflows=True,
            issues=True,
        ),
        "critical": ProfileSpec(extends="maintained"),
    }


def test_child_false_would_override_parent_true() -> None:
    profiles = _profiles()
    profiles["quiet"] = ProfileSpec(extends="maintained", issues=False)
    resolved = resolve_profile(profiles, "quiet", {})
    assert resolved.enabled["issues"] is False
    assert resolved.sources["issues"] == "quiet"
    assert resolved.enabled["workflows"] is True
    assert resolved.sources["workflows"] == "maintained"


def test_repository_override_is_last() -> None:
    resolved = resolve_profile(_profiles(), "critical", {"workflows": False})
    assert resolved.enabled["workflows"] is False
    assert resolved.sources["workflows"] == "repository"
    assert resolved.chain == ("critical", "maintained", "base")


def test_unknown_profile_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProfileSpec.model_validate({"security": True})


def test_config_defaults_apply_when_a_profile_omits_the_flag() -> None:
    resolved = resolve_profile(
        {"plain": ProfileSpec()},
        "plain",
        {},
        releases=True,
        workflows=False,
        issues=True,
        pull_requests=False,
        quality=True,
    )
    assert resolved.enabled["releases"] is True
    assert resolved.enabled["workflows"] is False
    assert resolved.enabled["issues"] is True
    assert resolved.enabled["pull_requests"] is False
    assert resolved.enabled["quality"] is True
    assert set(resolved.sources.values()) == {"default"}


def test_profile_overrides_a_config_default() -> None:
    resolved = resolve_profile(
        {"custom": ProfileSpec(releases=False, workflows=True)},
        "custom",
        {},
        releases=True,
        workflows=False,
    )
    assert resolved.enabled["releases"] is False
    assert resolved.sources["releases"] == "custom"
    assert resolved.enabled["workflows"] is True
    assert resolved.sources["workflows"] == "custom"


def test_pull_requests_and_quality_default_to_on() -> None:
    resolved = resolve_profile(_profiles(), "base", {})
    assert resolved.enabled["pull_requests"] is True
    assert resolved.enabled["quality"] is True
    assert resolved.sources["pull_requests"] == "default"


def test_profile_can_turn_pull_requests_and_quality_off() -> None:
    profiles = _profiles()
    profiles["quiet"] = ProfileSpec(
        extends="maintained",
        pull_requests=False,
        quality=False,
        issues=False,
    )
    resolved = resolve_profile(profiles, "quiet", {})
    assert resolved.enabled["pull_requests"] is False
    assert resolved.enabled["quality"] is False
    assert resolved.enabled["issues"] is False
    assert resolved.sources["quality"] == "quiet"


def test_circular_inheritance_names_the_chain() -> None:
    profiles = {"a": ProfileSpec(extends="b"), "b": ProfileSpec(extends="a")}
    with pytest.raises(ConfigError, match="Circular profile inheritance"):
        resolve_profile(profiles, "a", {})
