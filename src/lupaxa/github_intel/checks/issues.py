"""Issue check evaluation."""

from __future__ import annotations

from typing import Any

from lupaxa.github_intel.checks.base import CheckResult

__all__ = ["issue_records", "evaluate_issues"]


def issue_records(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Drop pull requests from a GitHub issues payload.

    Args:
        items: Objects returned by the issues API.

    Returns:
        Issues only.

    """

    return [item for item in items or [] if "pull_request" not in item]


def evaluate_issues(total: int | None, error: str | None) -> CheckResult:
    """
    Summarise open issues.

    Args:
        total: Open issue count, excluding pull requests when known.
        error: Request failure, if any.

    Returns:
        Issue check result. A count alone is not a failure.

    """

    if error:
        return CheckResult("issues", "Error", error, True)
    count = 0 if total is None else total
    noun = "issue" if count == 1 else "issues"
    return CheckResult("issues", "Open", f"{count} open {noun}.")
