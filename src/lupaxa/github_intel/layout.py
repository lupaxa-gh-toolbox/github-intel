"""Named list and detail field layouts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lupaxa.github_intel.errors import ConfigError

if TYPE_CHECKING:
    from lupaxa.github_intel.config.models import DisplaySettings
    from lupaxa.github_intel.views import RepositoryView

__all__ = [
    "CATALOGUE",
    "Layout",
    "RIGHT_ALIGNED",
    "hardcoded_list",
    "parse_labels",
    "resolve_layout",
    "view_names",
]

CATALOGUE: tuple[str, ...] = (
    "Organisation",
    "Repository",
    "Visibility",
    "Description",
    "Homepage",
    "Language",
    "Topics",
    "Group",
    "Profile",
    "Tags",
    "Enabled",
    "Status",
    "Cache",
    "Archived",
    "Fork",
    "Forks",
    "Last push",
    "Created",
    "Updated",
    "Synchronised",
    "Default branch",
    "Size",
    "Stars",
    "Watchers",
    "Licence",
    "Version",
    "Release date",
    "Ahead",
    "Pull requests",
    "Issues",
    "Quality",
    "Workflows",
    "Dependabot Alerts",
)

RIGHT_ALIGNED: frozenset[str] = frozenset(
    {
        "Size",
        "Stars",
        "Watchers",
        "Forks",
        "Ahead",
        "Pull requests",
        "Issues",
        "Quality",
        "Dependabot Alerts",
    }
)


@dataclass(frozen=True)
class Layout:
    """Resolved list and detail columns for one view name."""

    list_fields: tuple[str, ...]
    detail_fields: tuple[str, ...] | None


def parse_labels(values: list[str]) -> tuple[str, ...]:
    """Normalize configured field names against the catalogue."""
    if not values:
        message = "a view list must not be empty."
        raise ValueError(message)
    folded = {label.casefold(): label for label in CATALOGUE}
    seen: set[str] = set()
    chosen: list[str] = []
    for raw in values:
        text = raw.strip()
        label = folded.get(text.casefold())
        if label is None:
            message = f"unknown display field {raw!r}."
            raise ValueError(message)
        if label in seen:
            message = f"duplicate display field {label}."
            raise ValueError(message)
        seen.add(label)
        chosen.append(label)
    return tuple(chosen)


def hardcoded_list(views: list[RepositoryView]) -> tuple[str, ...]:
    """Return the default list columns. The repository set does not change them."""
    return (
        "Organisation",
        "Repository",
        "Visibility",
        "Language",
        "Status",
        "Version",
        "Release date",
        "Enabled",
    )


def resolve_layout(
    display: DisplaySettings,
    name: str,
    views: list[RepositoryView],
) -> Layout:
    """Resolve one named view into list and detail columns."""
    if name != "default" and name not in display.views:
        raise ConfigError(f"Unknown view: {name}.")
    entry = display.views.get(name)
    list_fields = (
        hardcoded_list(views) if entry is None or entry.list is None else entry.list
    )
    detail_fields = None if entry is None or entry.detail is None else entry.detail
    return Layout(list_fields, detail_fields)


def view_names(display: DisplaySettings) -> tuple[str, ...]:
    """Return saved view names with default first."""
    others = sorted(
        (name for name in display.views if name != "default"),
        key=str.casefold,
    )
    return ("default", *others)
