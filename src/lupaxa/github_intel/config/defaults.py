"""
Default configuration files created the first time a repository is added.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
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
  issues: false
  pull_requests: true
  quality: true
  standards:
    readme: true
    licence: true
    gitignore: true
    workflows: false
    python_packaging: false
    mkdocs: false
    tests: false

display:
  date_format: DD/MM/YYYY

sync:
  concurrency: 10
  timeout: 15
  retries: 3
  cache:
    enabled: true
    metadata_ttl: 3600
    releases_ttl: 1800
    workflows_ttl: 900
    issues_ttl: 1800
    standards_ttl: 86400

logging:
  level: INFO
"""

_PROFILES = """\
profiles:
  base:
    releases: true
    workflows: false
    issues: false
    standards: false
    security: false

  maintained:
    extends: base
    workflows: true
    issues: true
    standards: true

  upstream:
    extends: base

  watchlist:
    extends: upstream
    issues: true

  critical:
    extends: maintained
    security: true
"""

_REPOSITORIES = """\
repositories: []
"""


def write_default_files(directory: Path) -> Path:
    """
    Create the default YAML files when the directory has no config.yml.

    Args:
        directory: Configuration directory.

    Returns:
        Path to ``config.yml``. Existing files are left unchanged.

    """

    created = not directory.exists()
    directory.mkdir(parents=True, exist_ok=True)
    if created:
        _restrict(directory)
    config = directory / "config.yml"
    _write_new(config, _CONFIG)
    _write_new(directory / "profiles.yml", _PROFILES)
    _write_new(directory / "repositories.yml", _REPOSITORIES)
    return config


def _write_new(path: Path, text: str) -> None:
    if path.exists():
        return
    path.write_text(text, encoding="utf-8")
    _restrict(path)


def _restrict(path: Path) -> None:
    if path.is_dir():
        path.chmod(0o700)
    else:
        path.chmod(0o600)
