"""
Atomic edits of the repository file.

YAML comments, key order, and unrelated content are preserved. The original
file is replaced only after the edited document validates. A file that
changes under us is left untouched.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
from typing import Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from lupaxa.github_intel.config.loader import (
    LoadedConfig,
    load_config,
    repository_key,
    validate_repository_file,
)
from lupaxa.github_intel.errors import ConfigError, NotFound

__all__ = [
    "add_repository",
    "remove_repository",
    "set_repository_fields",
]


def add_repository(
    config_path: Path,
    repo: str,
    *,
    group: str | None = None,
    profile: str | None = None,
    tags: list[str] | None = None,
) -> None:
    """
    Append one repository if it is not already configured.

    Args:
        config_path: Main configuration file.
        repo: ``owner/name`` identifier.
        group: Optional group. Omitted uses ``ungrouped``.
        profile: Optional profile. Omitted uses the configured default.
        tags: Optional tags.

    Raises:
        ConfigError: The identifier, profile, or resulting file is invalid.
        NotFound: Never. Raised by the other editors.

    """

    def mutate(items: CommentedSeq | list[Any]) -> None:
        _reject_duplicate(items, repo)
        entry: dict[str, Any] = {"repo": repo}
        if group is not None:
            entry["group"] = group
        if profile is not None:
            entry["profile"] = profile
        if tags:
            entry["tags"] = list(tags)
        items.append(entry)

    _edit(config_path, mutate)


def remove_repository(config_path: Path, repo: str) -> None:
    """
    Remove one repository from configuration. Cache rows are left in place.

    Args:
        config_path: Main configuration file.
        repo: ``owner/name`` identifier.

    Raises:
        NotFound: The repository is not configured.

    """

    def mutate(items: CommentedSeq | list[Any]) -> None:
        index = _find(items, repo)
        del items[index]

    _edit(config_path, mutate)


def set_repository_fields(
    config_path: Path,
    repo: str,
    **fields: bool | str | None,
) -> None:
    """
    Set fields on one configured repository.

    A string entry is promoted to an object when a field must be stored.

    Args:
        config_path: Main configuration file.
        repo: ``owner/name`` identifier.
        fields: Keys such as ``enabled``, ``profile``, or ``group``.

    Raises:
        NotFound: The repository is not configured.
        ConfigError: The edited file does not validate.

    """

    def mutate(items: CommentedSeq | list[Any]) -> None:
        index = _find(items, repo)
        items[index] = _with_fields(_as_mapping(items[index]), fields)

    _edit(config_path, mutate)


def _edit(
    config_path: Path,
    mutate: Callable[[CommentedSeq | list[Any]], None],
) -> None:
    loaded = load_config(config_path)
    path = loaded.repositories_path
    before = path.read_bytes()
    document, items = _load_editable(path)
    mutate(items)
    _write_validated(loaded, path, document, before)


def _load_editable(path: Path) -> tuple[Any, CommentedSeq | list[Any]]:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        document = json.loads(path.read_text(encoding="utf-8"))
        items = document.get("repositories")
        if not isinstance(items, list):
            raise ConfigError(f"{path} repositories must be a list.")
        return document, items
    yaml = _round_trip()
    document = yaml.load(path.read_text(encoding="utf-8"))
    items = document.get("repositories") if isinstance(document, CommentedMap) else None
    if not isinstance(items, CommentedSeq):
        raise ConfigError(f"{path} repositories must be a list.")
    return document, items


def _write_validated(
    loaded: LoadedConfig,
    path: Path,
    document: CommentedMap | dict[str, Any],
    before: bytes,
) -> None:
    temporary = path.with_name(path.name + ".part")
    try:
        _dump(path, temporary, document)
        if path.read_bytes() != before:
            raise ConfigError(f"{path} changed while it was being edited.")
        validate_repository_file(
            temporary,
            loaded.config.defaults.profile,
            loaded.profiles,
        )
        if path.read_bytes() != before:
            raise ConfigError(f"{path} changed while it was being edited.")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _dump(path: Path, temporary: Path, document: CommentedMap | dict[str, Any]) -> None:
    if path.suffix.casefold() == ".json":
        text = json.dumps(document, indent=2) + "\n"
        temporary.write_text(text, encoding="utf-8")
        return
    yaml = _round_trip()
    with temporary.open("w", encoding="utf-8") as handle:
        yaml.dump(document, handle)


def _round_trip() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _reject_duplicate(items: CommentedSeq | list[Any], repo: str) -> None:
    key = repository_key(repo)
    for item in items:
        if repository_key(_identity(item)) == key:
            raise ConfigError(f"{repo} is already configured.")


def _find(items: CommentedSeq | list[Any], repo: str) -> int:
    key = repository_key(repo)
    for index, item in enumerate(items):
        if repository_key(_identity(item)) == key:
            return index
    raise NotFound(f"{repo} is not configured.")


def _identity(item: object) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict) and isinstance(item.get("repo"), str):
        return cast("str", item["repo"])
    raise ConfigError("A repository entry must be owner/name or an object.")


def _as_mapping(item: object) -> CommentedMap | dict[str, Any]:
    if isinstance(item, str):
        mapping = CommentedMap()
        mapping["repo"] = item
        return mapping
    if isinstance(item, dict):
        return item
    raise ConfigError("A repository entry must be owner/name or an object.")


def _with_fields(
    mapping: CommentedMap | dict[str, Any],
    fields: dict[str, Any],
) -> CommentedMap | dict[str, Any]:
    for key, value in fields.items():
        if value is None:
            mapping.pop(key, None)
        else:
            mapping[key] = value
    return mapping
