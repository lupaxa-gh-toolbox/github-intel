"""Profile inheritance."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from lupaxa.github_intel.config.models import (
    ProfileSpec,
    StandardsOverride,
    StandardsSettings,
)
from lupaxa.github_intel.config.profiles import resolve_profile
from lupaxa.github_intel.errors import ConfigError


def _profiles() -> dict[str, ProfileSpec]:
    return {
        "base": ProfileSpec(
            releases=True,
            workflows=False,
            issues=False,
            standards=False,
            security=False,
        ),
        "maintained": ProfileSpec(
            extends="base",
            workflows=True,
            issues=True,
            standards=True,
        ),
        "critical": ProfileSpec(extends="maintained", security=True),
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
    resolved = resolve_profile(_profiles(), "critical", {"security": False})
    assert resolved.enabled["security"] is False
    assert resolved.sources["security"] == "repository"
    assert resolved.chain == ("critical", "maintained", "base")


def test_profile_standards_override_keeps_omitted_defaults() -> None:
    profiles = _profiles()
    profiles["lupaxa"] = ProfileSpec(
        extends="maintained",
        standards=StandardsOverride(workflows=True, licence=False),
    )
    defaults = StandardsSettings(readme=True, licence=True, gitignore=True)
    resolved = resolve_profile(profiles, "lupaxa", {}, defaults)
    assert resolved.enabled["standards"] is True
    assert resolved.standards.workflows is True
    assert resolved.standards.licence is False
    assert resolved.standards.readme is True
    assert resolved.standards.gitignore is True
    assert resolved.standards.tests is False


def test_child_inherits_parent_standard_rules() -> None:
    profiles = _profiles()
    profiles["parent"] = ProfileSpec(
        standards=StandardsOverride(licence=False, workflows=True),
    )
    profiles["child"] = ProfileSpec(
        extends="parent",
        standards=StandardsOverride(workflows=False),
    )
    resolved = resolve_profile(profiles, "child", {})
    assert resolved.standards.licence is False
    assert resolved.standards.workflows is False
    assert resolved.standards.readme is True


def test_standards_true_does_not_reset_inherited_rules() -> None:
    profiles = {
        "parent": ProfileSpec(standards=StandardsOverride(licence=False)),
        "child": ProfileSpec(extends="parent", standards=True),
    }
    resolved = resolve_profile(profiles, "child", {})
    assert resolved.enabled["standards"] is True
    assert resolved.standards.licence is False


def test_repository_can_disable_standards_without_changing_rules() -> None:
    profiles = {
        "project": ProfileSpec(standards=StandardsOverride(workflows=True)),
    }
    resolved = resolve_profile(profiles, "project", {"standards": False})
    assert resolved.enabled["standards"] is False
    assert resolved.standards.workflows is True
    assert resolved.sources["standards"] == "repository"


def test_unknown_standard_rule_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProfileSpec.model_validate({"standards": {"spelling": True}})


def test_config_defaults_apply_when_a_profile_omits_the_flag() -> None:
    resolved = resolve_profile(
        _profiles(),
        "base",
        {},
        pull_requests=False,
        quality=False,
    )
    assert resolved.enabled["pull_requests"] is False
    assert resolved.enabled["quality"] is False


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
