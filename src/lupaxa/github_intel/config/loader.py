"""
Load YAML or JSON configuration and apply environment overrides.

CLI code applies its own overrides after this loader. Environment values
win over the file. Invalid environment values are errors.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError

from lupaxa.github_intel.config.models import (
    AppConfig,
    ProfileSpec,
    RepositorySpec,
)
from lupaxa.github_intel.config.paths import default_config_file
from lupaxa.github_intel.errors import ConfigError

__all__ = [
    "LoadedConfig",
    "load_config",
    "repository_key",
    "validate_repository_file",
]

ModelT = TypeVar("ModelT", AppConfig, ProfileSpec, RepositorySpec)


@dataclass(frozen=True)
class LoadedConfig:
    """A validated configuration and the repository records it names."""

    path: Path
    config: AppConfig
    profiles: dict[str, ProfileSpec]
    repositories: tuple[RepositorySpec, ...]
    profiles_path: Path
    repositories_path: Path


def load_config(path: Path | None = None) -> LoadedConfig:
    """
    Load the main file plus the profile and repository files it names.

    Args:
        path: Main configuration file. Defaults to the XDG config file.

    Returns:
        Validated configuration.

    Raises:
        ConfigError: A file is missing, unreadable, or invalid.

    """

    config_path = _main_path(path)
    document = _read_document(config_path)
    config = _parse_model(AppConfig, document, str(config_path))
    config = _apply_environment(config)
    root = config_path.parent
    profiles_path = _resolve_file(root, config.files.profiles)
    repositories_path = _resolve_file(root, config.files.repositories)
    profiles = _load_profiles(profiles_path)
    repositories = _load_repositories(repositories_path, config.defaults.profile)
    _require_known_profiles(profiles, repositories, config.defaults.profile)
    return LoadedConfig(
        path=config_path,
        config=config,
        profiles=profiles,
        repositories=repositories,
        profiles_path=profiles_path,
        repositories_path=repositories_path,
    )


def validate_repository_file(
    path: Path,
    default_profile: str,
    profiles: dict[str, ProfileSpec],
) -> tuple[RepositorySpec, ...]:
    """
    Validate a repository file against the already loaded profiles.

    Args:
        path: Repository YAML or JSON file.
        default_profile: Profile used when an entry omits one.
        profiles: Known profiles.

    Returns:
        Parsed repositories.

    Raises:
        ConfigError: The file or a profile reference is invalid.

    """

    repositories = _load_repositories(path, default_profile)
    _require_known_profiles(profiles, repositories, default_profile)
    return repositories


def repository_key(name: str) -> str:
    """
    Return the case-insensitive identity of an ``owner/name`` string.

    Args:
        name: Repository identifier.

    Returns:
        Folded identifier used to detect duplicates.

    """

    owner, _, repo = name.partition("/")
    return f"{owner.casefold()}/{repo.casefold()}"


def _main_path(path: Path | None) -> Path:
    if path is not None:
        return path.expanduser()
    env = os.environ.get("GITHUB_INTEL_CONFIG")
    if env is not None and env.strip() != "":
        return Path(env).expanduser()
    return default_config_file()


def _resolve_file(root: Path, reference: str) -> Path:
    candidate = Path(reference).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate


def _read_document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    suffix = _format_suffix(path)
    if suffix in {".yml", ".yaml"}:
        return _read_yaml(path)
    if suffix == ".json":
        return _read_json(path)
    raise ConfigError(f"Unsupported configuration file: {path.name}")


def _read_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    yaml.allow_duplicate_keys = False
    try:
        loaded = yaml.load(path.read_text(encoding="utf-8"))
    except DuplicateKeyError as exc:
        raise ConfigError(f"Duplicate key in {path}: {exc}") from exc
    except Exception as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    return _as_mapping(loaded, path)


def _read_json(path: Path) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ConfigError(f"Duplicate key in {path}: {key}")
            result[key] = value
        return result

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except ConfigError:
        raise
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    return _as_mapping(loaded, path)


def _format_suffix(path: Path) -> str:
    name = path.name[: -len(".part")] if path.name.endswith(".part") else path.name
    return Path(name).suffix.casefold()


def _as_mapping(loaded: object, path: Path) -> dict[str, Any]:
    if not isinstance(loaded, dict):
        raise ConfigError(f"{path} must contain an object.")
    return cast("dict[str, Any]", loaded)


def _parse_model(
    model: type[ModelT],
    document: dict[str, Any],
    label: str,
) -> ModelT:
    try:
        return model.model_validate(document)
    except ValidationError as exc:
        raise ConfigError(_validation_message(label, exc)) from exc


def _validation_message(label: str, exc: ValidationError) -> str:
    lines = [f"Invalid configuration in {label}:"]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        lines.append(f"  {location}: {error['msg']}")
    return "\n".join(lines)


def _apply_environment(config: AppConfig) -> AppConfig:
    updates: dict[str, Any] = {}
    concurrency = _env_int("GITHUB_INTEL_CONCURRENCY", minimum=1)
    if concurrency is not None:
        updates["sync"] = config.sync.model_copy(update={"concurrency": concurrency})
    api_url = os.environ.get("GITHUB_INTEL_API_URL")
    if api_url is not None and api_url.strip() != "":
        try:
            updates["github"] = type(config.github).model_validate(
                {"api_url": api_url.strip()},
            )
        except ValidationError as exc:
            raise ConfigError(_validation_message("GITHUB_INTEL_API_URL", exc)) from exc
    level = os.environ.get("GITHUB_INTEL_LOG_LEVEL")
    if level is not None and level.strip() != "":
        try:
            updates["logging"] = type(config.logging).model_validate({"level": level})
        except ValidationError as exc:
            raise ConfigError(
                _validation_message("GITHUB_INTEL_LOG_LEVEL", exc),
            ) from exc
    if not updates:
        return config
    return config.model_copy(update=updates)


def _env_int(name: str, *, minimum: int) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    if not raw.strip().isdigit() or int(raw.strip()) < minimum:
        raise ConfigError(f"{name} must be an integer >= {minimum}.")
    return int(raw.strip())


def _load_profiles(path: Path) -> dict[str, ProfileSpec]:
    document = _read_document(path)
    raw = document.get("profiles")
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a profiles object.")
    profiles: dict[str, ProfileSpec] = {}
    for name, body in raw.items():
        if not isinstance(name, str) or name.strip() == "":
            raise ConfigError(f"Profile names in {path} must be strings.")
        if not isinstance(body, dict):
            raise ConfigError(f"Profile {name} must be an object.")
        profiles[name] = _parse_model(ProfileSpec, body, f"{path} profile {name}")
    return profiles


def _load_repositories(path: Path, default_profile: str) -> tuple[RepositorySpec, ...]:
    document = _read_document(path)
    raw = document.get("repositories", [])
    if not isinstance(raw, list):
        raise ConfigError(f"{path} repositories must be a list.")
    repositories: list[RepositorySpec] = []
    seen: dict[str, str] = {}
    for index, item in enumerate(raw):
        spec = _one_repository(item, path, index, default_profile)
        key = repository_key(spec.repo)
        if key in seen:
            raise ConfigError(
                f"Duplicate repository {spec.repo} (already listed as {seen[key]})."
            )
        seen[key] = spec.repo
        repositories.append(spec)
    return tuple(repositories)


def _one_repository(
    item: object,
    path: Path,
    index: int,
    default_profile: str,
) -> RepositorySpec:
    label = f"{path} repositories[{index}]"
    if isinstance(item, str):
        return _parse_model(
            RepositorySpec,
            {"repo": item, "profile": default_profile},
            label,
        )
    if isinstance(item, dict):
        body = dict(item)
        body.setdefault("profile", default_profile)
        return _parse_model(RepositorySpec, body, label)
    raise ConfigError(f"{label} must be owner/name or an object.")


def _require_known_profiles(
    profiles: dict[str, ProfileSpec],
    repositories: tuple[RepositorySpec, ...],
    default_profile: str,
) -> None:
    if default_profile not in profiles:
        raise ConfigError(
            f"defaults.profile references unknown profile {default_profile}.",
        )
    for repository in repositories:
        name = repository.profile or default_profile
        if name not in profiles:
            raise ConfigError(f"{repository.repo} references unknown profile {name}.")
