"""
Single-parent profile inheritance.

Resolution does not depend on the order of profiles in the file.
An explicit false overrides an inherited true.
"""

from __future__ import annotations

from dataclasses import dataclass

from lupaxa.github_intel.config.models import (
    ProfileSpec,
    StandardsOverride,
    StandardsSettings,
)
from lupaxa.github_intel.constants import CHECK_NAMES
from lupaxa.github_intel.errors import ConfigError

__all__ = [
    "ResolvedProfile",
    "resolve_profile",
]


@dataclass(frozen=True)
class ResolvedProfile:
    """Effective check flags and the profile that set each one."""

    name: str
    chain: tuple[str, ...]
    enabled: dict[str, bool]
    sources: dict[str, str]
    standards: StandardsSettings


def resolve_profile(
    profiles: dict[str, ProfileSpec],
    name: str,
    overrides: dict[str, bool] | None = None,
    standards: StandardsSettings | None = None,
    *,
    issues: bool = False,
    pull_requests: bool = True,
    quality: bool = True,
) -> ResolvedProfile:
    """
    Resolve ``name`` including parents and repository overrides.

    Args:
        profiles: Named profile definitions.
        name: Profile to resolve.
        overrides: Repository check overrides applied last.
        standards: Rule defaults. Omitted profile rules keep these values.
        issues: Used when no profile in the chain sets issues.
        pull_requests: Used when no profile in the chain sets pull requests.
        quality: Used when no profile in the chain sets quality.

    Returns:
        Effective flags. The chain runs from the named profile to the root.

    Raises:
        ConfigError: The profile is missing or inheritance is circular.

    """

    chain = _inheritance_chain(profiles, name)
    enabled = dict.fromkeys(CHECK_NAMES, False)
    sources = dict.fromkeys(CHECK_NAMES, "default")
    rules = dict((standards or StandardsSettings()).model_dump())
    for profile_name in reversed(chain):
        spec = profiles[profile_name]
        _apply_profile(spec, profile_name, enabled, sources)
        _apply_standard_rules(spec.standards, rules)
    defaults = {
        "issues": issues,
        "pull_requests": pull_requests,
        "quality": quality,
    }
    for name, value in defaults.items():
        if sources[name] == "default":
            enabled[name] = value
    for check, value in (overrides or {}).items():
        enabled[check] = value
        sources[check] = "repository"
    return ResolvedProfile(
        name=name,
        chain=chain,
        enabled=enabled,
        sources=sources,
        standards=StandardsSettings.model_validate(rules),
    )


def _inheritance_chain(
    profiles: dict[str, ProfileSpec],
    name: str,
) -> tuple[str, ...]:
    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = name
    while current is not None:
        if current in seen:
            cycle = " -> ".join([*chain, current])
            raise ConfigError(f"Circular profile inheritance: {cycle}.")
        spec = profiles.get(current)
        if spec is None:
            raise ConfigError(f"Unknown profile: {current}.")
        seen.add(current)
        chain.append(current)
        current = spec.extends
    return tuple(chain)


def _apply_profile(
    spec: ProfileSpec,
    profile_name: str,
    enabled: dict[str, bool],
    sources: dict[str, str],
) -> None:
    for check in CHECK_NAMES:
        value = getattr(spec, check)
        if isinstance(value, bool):
            enabled[check] = value
            sources[check] = profile_name
        elif value is not None:
            enabled[check] = True
            sources[check] = profile_name


def _apply_standard_rules(
    value: bool | StandardsOverride | None,
    rules: dict[str, bool],
) -> None:
    if not isinstance(value, StandardsOverride):
        return
    for name, flag in value.model_dump().items():
        if isinstance(flag, bool):
            rules[name] = flag
