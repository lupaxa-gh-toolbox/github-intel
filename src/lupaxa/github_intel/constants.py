"""
Project-wide constants for GitHub Intel.

This module contains stable names, version text, and process exit codes.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "API_VERSION",
    "CHECK_NAMES",
    "DEFAULT_PROFILE",
    "EXIT_AUTH",
    "EXIT_CHECKS",
    "EXIT_CONFIG",
    "EXIT_ERROR",
    "EXIT_NOT_FOUND",
    "EXIT_SUCCESS",
    "EXIT_SYNC",
    "PROGRAM_NAME",
    "PROGRAM_VERSION",
    "PROGRAM_VERSION_STRING",
    "PROJECT_NAME",
    "UNGROUPED",
    "USER_AGENT",
]

PROGRAM_NAME: Final[str] = "github-intel"
PROJECT_NAME: Final[str] = "lupaxa-github-intel"
PROGRAM_VERSION: Final[str] = "0.1.0-rc1"
PROGRAM_VERSION_STRING: Final[str] = f"{PROGRAM_NAME} v{PROGRAM_VERSION}"

USER_AGENT: Final[str] = "lupaxa-github-intel"
API_VERSION: Final[str] = "2022-11-28"
DEFAULT_PROFILE: Final[str] = "upstream"
UNGROUPED: Final[str] = "ungrouped"

CHECK_NAMES: Final[tuple[str, ...]] = (
    "releases",
    "workflows",
    "issues",
    "pull_requests",
    "quality",
)

EXIT_SUCCESS: Final[int] = 0
EXIT_ERROR: Final[int] = 1
EXIT_CONFIG: Final[int] = 2
EXIT_AUTH: Final[int] = 3
EXIT_SYNC: Final[int] = 4
EXIT_NOT_FOUND: Final[int] = 5
EXIT_CHECKS: Final[int] = 6
