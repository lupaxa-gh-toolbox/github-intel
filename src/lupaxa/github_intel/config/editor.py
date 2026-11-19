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

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from lupaxa.github_intel.config.loader import (
    LoadedConfig,
    load_config,
    repository_key,
    validate_repository_file,
)
from lupaxa.github_intel.config.models import RepositorySpec
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

    def mutate(owners: CommentedSeq | list[Any]) -> None:
        owner, name = _split(repo)
        _reject_duplicate(owners, f"{owner}/{name}")
        block = _find_owner(owners, owner)
        if block is None:
            block = _new_owner(owner, group, profile)
            owners.append(block)
            listed = block["repositories"]
        else:
            listed = _repository_list(block)
        listed.append(_entry(name, block, group, profile, tags))

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

    def mutate(owners: CommentedSeq | list[Any]) -> None:
        owner, name = _split(repo)
        block, index = _find(owners, owner, name)
        del _repository_list(block)[index]
        if len(_repository_list(block)) == 0:
            owners.remove(block)

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

    def mutate(owners: CommentedSeq | list[Any]) -> None:
        owner, name = _split(repo)
        block, index = _find(owners, owner, name)
        listed = _repository_list(block)
        listed[index] = _with_fields(_as_mapping(listed[index], name), fields)

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
        items = document.get("organisations")
        if not isinstance(items, list):
            raise ConfigError(f"{path} organisations must be a list.")
        return document, items
    yaml = _round_trip()
    document = yaml.load(path.read_text(encoding="utf-8"))
    items = None
    if isinstance(document, CommentedMap):
        items = document.get("organisations")
    if not isinstance(items, CommentedSeq):
        raise ConfigError(f"{path} organisations must be a list.")
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


def _split(repo: str) -> tuple[str, str]:
    try:
        canonical = RepositorySpec(repo=repo).repo
    except ValidationError as exc:
        raise ConfigError("repo must be owner/name.") from exc
    owner, _, name = canonical.partition("/")
    return owner, name


def _reject_duplicate(owners: CommentedSeq | list[Any], repo: str) -> None:
    owner, name = _split(repo)
    try:
        _find(owners, owner, name)
    except NotFound:
        return
    raise ConfigError(f"{repo} is already configured.")


def _find(
    owners: CommentedSeq | list[Any],
    owner: str,
    name: str,
) -> tuple[CommentedMap | dict[str, Any], int]:
    wanted = repository_key(f"{owner}/{name}")
    for block in owners:
        if not isinstance(block, dict):
            continue
        raw_owner = block.get("name")
        if not isinstance(raw_owner, str):
            continue
        listed = block.get("repositories")
        if not isinstance(listed, list):
            continue
        for index, item in enumerate(listed):
            if repository_key(f"{raw_owner}/{_item_name(item)}") == wanted:
                return block, index
    raise NotFound(f"{owner}/{name} is not configured.")


def _find_owner(
    owners: CommentedSeq | list[Any],
    owner: str,
) -> CommentedMap | dict[str, Any] | None:
    for block in owners:
        if not isinstance(block, dict):
            continue
        raw_name = block.get("name")
        if isinstance(raw_name, str) and raw_name.casefold() == owner.casefold():
            return cast("dict[str, Any]", block)
    return None


def _new_owner(owner: str, group: str | None, profile: str | None) -> CommentedMap:
    block = CommentedMap()
    block["name"] = owner
    if group is not None:
        block["group"] = group
    if profile is not None:
        block["profile"] = profile
    block["repositories"] = CommentedSeq()
    return block


def _repository_list(block: CommentedMap | dict[str, Any]) -> CommentedSeq | list[Any]:
    listed = block.get("repositories")
    if not isinstance(listed, list):
        raise ConfigError(f"{block.get('name')} repositories must be a list.")
    return listed


def _entry(
    name: str,
    block: CommentedMap | dict[str, Any],
    group: str | None,
    profile: str | None,
    tags: list[str] | None,
) -> str | CommentedMap:
    mapping = CommentedMap()
    mapping["name"] = name
    if group is not None and group != block.get("group"):
        mapping["group"] = group
    if profile is not None and profile != block.get("profile"):
        mapping["profile"] = profile
    if tags:
        mapping["tags"] = list(tags)
    if len(mapping) == 1:
        return name
    return mapping


def _item_name(item: object) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict) and isinstance(item.get("name"), str):
        return cast("str", item["name"])
    raise ConfigError("A repository entry must be a name or an object.")


def _as_mapping(item: object, name: str) -> CommentedMap | dict[str, Any]:
    if isinstance(item, str):
        mapping = CommentedMap()
        mapping["name"] = name
        return mapping
    if isinstance(item, dict):
        return item
    raise ConfigError("A repository entry must be a name or an object.")


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
