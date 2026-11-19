"""
Resolve configuration and cache directories.

macOS and Linux use the XDG paths (``~/.config`` and ``~/.local/share``).
Windows uses platformdirs.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from platformdirs import PlatformDirs
from platformdirs.unix import Unix

__all__ = [
    "config_directory",
    "data_directory",
    "default_config_file",
]


def config_directory() -> Path:
    """
    Return the directory that holds config.yml.

    ``GITHUB_INTEL_CONFIG_DIR`` overrides the platform default.

    Returns:
        Configuration directory. The directory is not created.

    """

    return _configured_directory("GITHUB_INTEL_CONFIG_DIR", "user_config_dir")


def data_directory() -> Path:
    """
    Return the directory that holds the SQLite cache.

    ``GITHUB_INTEL_DATA_DIR`` overrides the platform default.

    Returns:
        Data directory. The directory is not created.

    """

    return _configured_directory("GITHUB_INTEL_DATA_DIR", "user_data_dir")


def default_config_file(directory: Path | None = None) -> Path:
    """
    Return the main configuration file inside ``directory``.

    An existing ``config.yml``, ``config.yaml``, or ``config.json`` wins.
    Otherwise the path is ``config.yml`` even when that file is absent.

    Args:
        directory: Configuration directory. Defaults to :func:`config_directory`.

    Returns:
        Path to the main configuration file.

    """

    root = config_directory() if directory is None else directory
    for name in ("config.yml", "config.yaml", "config.json"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return root / "config.yml"


def _configured_directory(env_name: str, attribute: str) -> Path:
    override = os.environ.get(env_name)
    if override is not None and override.strip() != "":
        return Path(override).expanduser()
    dirs: PlatformDirs | Unix
    if sys.platform == "win32":
        dirs = PlatformDirs(appname="github-intel", appauthor=False)
    else:
        dirs = Unix(appname="github-intel", appauthor=False)
    return Path(getattr(dirs, attribute))
