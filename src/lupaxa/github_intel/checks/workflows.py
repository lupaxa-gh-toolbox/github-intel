"""Workflow check evaluation."""

from __future__ import annotations

from typing import Any

from lupaxa.github_intel.checks.base import CheckResult

__all__ = ["evaluate_workflows"]


def evaluate_workflows(
    workflows: list[dict[str, Any]] | None,
    error: str | None,
) -> CheckResult:
    """
    Summarise the workflow list.

    Args:
        workflows: Workflow name and activity pairs already prepared for display.
        error: Request failure, if any.

    Returns:
        Workflow check result. Listing workflows is not a failure.

    """

    if error:
        return CheckResult("workflows", "Error", error, True)
    count = 0 if workflows is None else len(workflows)
    if count == 0:
        return CheckResult("workflows", "No workflows", "No workflows are configured.")
    noun = "workflow" if count == 1 else "workflows"
    return CheckResult("workflows", "Listed", f"{count} {noun}.")
