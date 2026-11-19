"""
Default configuration files created the first time a repository is added.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "generate_default_files",
    "write_default_files",
]

_CONFIG = """\
# GitHub Intel configuration.
# Authentication uses the GitHub CLI login (`gh auth token`), the same
# GitHub account used for SSH. Tokens are not stored in this file.

version: 1

github:
  api_url: https://api.github.com

files:
  profiles: profiles.yml
  repositories: repositories.yml

defaults:
  profile: upstream
  releases: false
  workflows: false
  issues: false
  pull_requests: true
  quality: true

display:
  date_format: DD/MM/YYYY HH:mm UTC
  view: default
  views:
    popularity:
      list:
        - Organisation
        - Repository
        - Stars
        - Watchers
        - Forks

sync:
  concurrency: 10
  timeout: 15
  retries: 3
  interval: 0
  cache:
    enabled: true
    metadata_ttl: 3600
    releases_ttl: 1800
    workflows_ttl: 900
    issues_ttl: 1800

logging:
  level: INFO
"""

_PROFILES = """\
profiles:
  base:
    releases: true
    workflows: false
    issues: false

  maintained:
    extends: base
    workflows: true
    issues: true

  upstream:
    extends: base

  watchlist:
    extends: upstream
    issues: true

  critical:
    extends: maintained
"""

_REPOSITORIES = """\
organisations: []
"""


def write_default_files(directory: Path) -> Path:
    """
    Create the default YAML files when the directory has no config.yml.

    Args:
        directory: Configuration directory.

    Returns:
        Path to ``config.yml``. Existing files are left unchanged.

    """

    config = directory / "config.yml"
    generate_default_files(
        (config, directory / "profiles.yml", directory / "repositories.yml"),
        force=False,
    )
    return config


def generate_default_files(
    paths: tuple[Path, Path, Path],
    *,
    force: bool,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """
    Write the shipped config, profiles, and repositories files.

    Args:
        paths: ``config.yml``, ``profiles.yml``, and ``repositories.yml``.
        force: Replace files that already exist.

    Returns:
        The paths written, then the paths left unchanged.

    """

    directory = paths[0].parent
    created = not directory.exists()
    directory.mkdir(parents=True, exist_ok=True)
    if created:
        _restrict(directory)
    written: list[Path] = []
    kept: list[Path] = []
    for path, text in zip(paths, (_CONFIG, _PROFILES, _REPOSITORIES), strict=True):
        if path.exists() and not force:
            kept.append(path)
            continue
        path.write_text(text, encoding="utf-8")
        _restrict(path)
        written.append(path)
    return tuple(written), tuple(kept)


def _restrict(path: Path) -> None:
    if path.is_dir():
        path.chmod(0o700)
    else:
        path.chmod(0o600)
