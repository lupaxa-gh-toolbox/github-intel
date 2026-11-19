"""
Configuration models.

Missing optional values receive defaults. Unknown keys and invalid types
are rejected instead of being replaced.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lupaxa.github_intel.constants import CHECK_NAMES, DEFAULT_PROFILE, UNGROUPED
from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT, require_date_format

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
    "StandardsOverride",
    "StandardsSettings",
    "SyncSettings",
]

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


class StandardsSettings(_StrictModel):
    """
    Which standards rules run when a profile enables ``standards``.

    A third-party profile leaves ``standards`` false, so these rules are
    not applied to it.
    """

    readme: bool = True
    licence: bool = True
    gitignore: bool = True
    workflows: bool = False
    python_packaging: bool = False
    mkdocs: bool = False
    tests: bool = False


class StandardsOverride(_StrictModel):
    """
    Standards rules set on one profile.

    Omitted rules keep the value inherited from the config default or a
    parent profile. A mapping turns the standards check on.
    """

    readme: bool | None = None
    licence: bool | None = None
    gitignore: bool | None = None
    workflows: bool | None = None
    python_packaging: bool | None = None
    mkdocs: bool | None = None
    tests: bool | None = None


class CacheSettings(_StrictModel):
    """Per-category freshness windows, in seconds."""

    enabled: bool = True
    metadata_ttl: int = Field(default=3600, ge=0)
    releases_ttl: int = Field(default=1800, ge=0)
    workflows_ttl: int = Field(default=900, ge=0)
    issues_ttl: int = Field(default=1800, ge=0)
    standards_ttl: int = Field(default=86400, ge=0)


class SyncSettings(_StrictModel):
    """Bounded synchronisation settings."""

    concurrency: int = Field(default=10, ge=1)
    timeout: float = Field(default=15, gt=0)
    retries: int = Field(default=3, ge=0)
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
    """One monitoring profile. Omitted checks are inherited or default to false."""

    extends: str | None = None
    releases: bool | None = None
    workflows: bool | None = None
    issues: bool | None = None
    pull_requests: bool | None = None
    quality: bool | None = None
    standards: bool | StandardsOverride | None = None
    security: bool | None = None


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
    """Default profile name and the standards rules used when standards are on."""

    profile: str = DEFAULT_PROFILE
    issues: bool = False
    pull_requests: bool = True
    quality: bool = True
    standards: StandardsSettings = Field(default_factory=StandardsSettings)

    @field_validator("profile")
    @classmethod
    def _profile(cls, value: str) -> str:
        text = value.strip()
        if text == "":
            message = "defaults.profile must not be blank."
            raise ValueError(message)
        return text


class DisplaySettings(_StrictModel):
    """How dates are shown in tables and reports."""

    date_format: str = DEFAULT_DATE_FORMAT

    @field_validator("date_format")
    @classmethod
    def _date_format(cls, value: str) -> str:
        return require_date_format(value)


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
