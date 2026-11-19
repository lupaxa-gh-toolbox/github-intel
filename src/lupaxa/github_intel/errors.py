"""
Application errors and the exit codes they map to.
"""

from __future__ import annotations

from lupaxa.github_intel.constants import (
    EXIT_AUTH,
    EXIT_CHECKS,
    EXIT_CONFIG,
    EXIT_ERROR,
    EXIT_NOT_FOUND,
    EXIT_SYNC,
)

__all__ = [
    "AuthError",
    "ChecksFailed",
    "ConfigError",
    "IntelError",
    "NotFound",
    "SyncIncomplete",
]


class IntelError(Exception):
    """
    Base error for failures reported to the operator.

    Attributes:
        exit_code: Process exit code for this failure.

    """

    exit_code = EXIT_ERROR


class ConfigError(IntelError):
    """The configuration or command arguments are invalid."""

    exit_code = EXIT_CONFIG


class AuthError(IntelError):
    """GitHub rejected the credentials used for the API."""

    exit_code = EXIT_AUTH


class SyncIncomplete(IntelError):
    """Synchronisation finished with failures or was cancelled."""

    exit_code = EXIT_SYNC


class NotFound(IntelError):
    """The named repository is not in the configuration."""

    exit_code = EXIT_NOT_FOUND


class ChecksFailed(IntelError):
    """An explicit failure-on-check run found failing checks."""

    exit_code = EXIT_CHECKS
