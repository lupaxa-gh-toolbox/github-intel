"""
Resolve a GitHub API token from the existing GitHub CLI login.

github-repo-sync authenticates with SSH and stores no token. The REST API
cannot use an SSH key, so the token is read from ``gh auth token`` for that
same GitHub account. The value is never written to config, cache, or logs.
"""

from __future__ import annotations

import subprocess

__all__ = [
    "github_cli_token",
]


def github_cli_token() -> str | None:
    """
    Return the current ``gh`` token, or None when gh is not logged in.

    Returns:
        Token text, or None when the GitHub CLI cannot provide one.

    """

    try:
        completed = subprocess.run(  # noqa: S603
            ["gh", "auth", "token"],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    token = completed.stdout.strip()
    return token or None
