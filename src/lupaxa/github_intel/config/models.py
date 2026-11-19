"""
Configuration models.

Missing optional values receive defaults. Unknown keys and invalid types
are rejected instead of being replaced.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lupaxa.github_intel.constants import CHECK_NAMES, DEFAULT_PROFILE, UNGROUPED
from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT, require_date_format
from lupaxa.github_intel.layout import parse_labels

__all__ = [
    "AppConfig",
    "CacheSettings",
    "DefaultsSettings",
    "DisplaySettings",
    "FileSettings",
    "GitHubSettings",
    "LoggingSettings",
    "ProfileSpec",
    "RepositorySpec",
    "SyncSettings",
    "ViewSettings",
]

_VIEW_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GitHubSettings(_StrictModel):
    """GitHub API location. Credentials are never read from this file."""

    api_url: str = "https://api.github.com"

    @field_validator("api_url")
    @classmethod
    def _api_url(cls, value: str) -> str:
        text = value.strip().rstrip("/")
        if not text.startswith("https://"):
            message = "github.api_url must be an https URL."
            raise ValueError(message)
        return text


class FileSettings(_StrictModel):
    """Paths of the profile and repository files, relative to config.yml."""

    profiles: str = "profiles.yml"
    repositories: str = "repositories.yml"


class CacheSettings(_StrictModel):
    """Per-category freshness windows, in seconds."""

    enabled: bool = True
    metadata_ttl: int = Field(default=3600, ge=0)
    releases_ttl: int = Field(default=1800, ge=0)
    workflows_ttl: int = Field(default=900, ge=0)
    issues_ttl: int = Field(default=1800, ge=0)


class SyncSettings(_StrictModel):
    """Bounded synchronisation settings."""

    concurrency: int = Field(default=10, ge=1)
    timeout: float = Field(default=15, gt=0)
    retries: int = Field(default=3, ge=0)
    interval: int = Field(default=0, ge=0)
    cache: CacheSettings = Field(default_factory=CacheSettings)


class LoggingSettings(_StrictModel):
    """Logging level stored in configuration."""

    level: str = "INFO"

    @field_validator("level")
    @classmethod
    def _level(cls, value: str) -> str:
        text = value.strip().upper()
        if text not in _LOG_LEVELS:
            message = "logging.level must be CRITICAL, ERROR, WARNING, INFO, or DEBUG."
            raise ValueError(message)
        return text


class ProfileSpec(_StrictModel):
    """One monitoring profile. Omitted checks are inherited or taken from defaults."""

    extends: str | None = None
    releases: bool | None = None
    workflows: bool | None = None
    issues: bool | None = None
    pull_requests: bool | None = None
    quality: bool | None = None


class RepositorySpec(_StrictModel):
    """One configured repository."""

    repo: str
    group: str = UNGROUPED
    profile: str | None = None
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    checks: dict[str, bool] = Field(default_factory=dict)

    @field_validator("repo")
    @classmethod
    def _repo(cls, value: str) -> str:
        return _repository_name(value)

    @field_validator("group")
    @classmethod
    def _group(cls, value: str) -> str:
        text = value.strip()
        if text == "":
            message = "group must not be blank."
            raise ValueError(message)
        return text

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            text = tag.strip()
            if text == "":
                message = "tags must not contain a blank value."
                raise ValueError(message)
            cleaned.append(text)
        return cleaned

    @field_validator("checks")
    @classmethod
    def _checks(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = sorted(set(value) - set(CHECK_NAMES))
        if unknown:
            message = f"Unknown check names: {', '.join(unknown)}."
            raise ValueError(message)
        return value


class DefaultsSettings(_StrictModel):
    """Default profile name and the check flags used when no profile sets them."""

    profile: str = DEFAULT_PROFILE
    releases: bool = False
    workflows: bool = False
    issues: bool = False
    pull_requests: bool = True
    quality: bool = True

    @field_validator("profile")
    @classmethod
    def _profile(cls, value: str) -> str:
        text = value.strip()
        if text == "":
            message = "defaults.profile must not be blank."
            raise ValueError(message)
        return text


class ViewSettings(_StrictModel):
    """One named list and/or detail layout."""

    list: tuple[str, ...] | None = None
    detail: tuple[str, ...] | None = None

    @field_validator("list", mode="before")
    @classmethod
    def _list(cls, value: object) -> tuple[str, ...] | None:
        if value is None:
            return None
        if not isinstance(value, (list, tuple)):
            message = "list must be a list of field names."
            raise ValueError(message)
        labels: list[str] = []
        for item in value:
            if not isinstance(item, str):
                message = "list must be a list of field names."
                raise ValueError(message)
            labels.append(item)
        return parse_labels(labels)

    @field_validator("detail", mode="before")
    @classmethod
    def _detail(cls, value: object) -> tuple[str, ...] | None:
        if value is None:
            return None
        if not isinstance(value, (list, tuple)):
            message = "detail must be a list of field names."
            raise ValueError(message)
        labels: list[str] = []
        for item in value:
            if not isinstance(item, str):
                message = "detail must be a list of field names."
                raise ValueError(message)
            labels.append(item)
        return parse_labels(labels)

    @model_validator(mode="after")
    def _requires_a_side(self) -> ViewSettings:
        if self.list is None and self.detail is None:
            message = "a view must define list and/or detail."
            raise ValueError(message)
        return self


class DisplaySettings(_StrictModel):
    """
    How dates are shown, which view is selected, and the named views.

    Attributes:
        date_format: Pattern for dates in tables and reports.
        view: Name of the selected view. ``default`` is always valid.
        views: Named views, each with an optional list and detail.

    """

    date_format: str = DEFAULT_DATE_FORMAT
    view: str = "default"
    views: dict[str, ViewSettings] = Field(default_factory=dict)

    @field_validator("date_format")
    @classmethod
    def _date_format(cls, value: str) -> str:
        return require_date_format(value)

    @field_validator("view")
    @classmethod
    def _view(cls, value: str) -> str:
        return value.strip()

    @field_validator("views")
    @classmethod
    def _views(cls, value: dict[str, ViewSettings]) -> dict[str, ViewSettings]:
        rebuilt: dict[str, ViewSettings] = {}
        for name, entry in value.items():
            text = name.strip()
            if not _VIEW_NAME.match(text):
                message = f"invalid view name {name!r}."
                raise ValueError(message)
            if text in rebuilt:
                message = f"duplicate view name {text!r}."
                raise ValueError(message)
            rebuilt[text] = entry
        return rebuilt

    @model_validator(mode="after")
    def _active_view(self) -> DisplaySettings:
        if self.view != "default" and self.view not in self.views:
            message = f"unknown display view {self.view!r}."
            raise ValueError(message)
        return self


class AppConfig(_StrictModel):
    """The main ``config.yml`` document."""

    version: int
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    files: FileSettings = Field(default_factory=FileSettings)
    defaults: DefaultsSettings = Field(default_factory=DefaultsSettings)
    display: DisplaySettings = Field(default_factory=DisplaySettings)
    sync: SyncSettings = Field(default_factory=SyncSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @field_validator("version")
    @classmethod
    def _version(cls, value: int) -> int:
        if value != 1:
            message = "version must be 1."
            raise ValueError(message)
        return value


def _repository_name(value: str) -> str:
    text = value.strip()
    owner, separator, name = text.partition("/")
    invalid = (
        separator != "/"
        or "/" in name
        or owner in {"", ".", ".."}
        or name in {"", ".", ".."}
        or any(character.isspace() for character in text)
    )
    if invalid or not _segment(owner) or not _segment(name):
        message = "repo must be owner/name."
        raise ValueError(message)
    if name.casefold().endswith(".git"):
        message = "repo must not end with .git."
        raise ValueError(message)
    return f"{owner}/{name}"


def _segment(value: str) -> bool:
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
    return all(character in allowed for character in value)
