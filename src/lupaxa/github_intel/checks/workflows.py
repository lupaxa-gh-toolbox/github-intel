"""Workflow check evaluation."""

from __future__ import annotations

from typing import Any

from lupaxa.github_intel.checks.base import CheckResult

__all__ = ["evaluate_workflows"]


def evaluate_workflows(
    runs: list[dict[str, Any]] | None,
    error: str | None,
) -> CheckResult:
    """
    Summarise the newest workflow run.

    Args:
        runs: Workflow run objects, newest first.
        error: Request failure, if any.

    Returns:
        Workflow check result.

    """

    if error:
        return CheckResult("workflows", "Error", error, True)
    if not runs:
        return CheckResult("workflows", "Never run", "No workflow runs were found.")
    latest = runs[0]
    name = str(latest.get("name") or "workflow")
    state = str(latest.get("status") or "")
    if state != "completed":
        return CheckResult(
            "workflows",
            "In progress",
            f"{name} is {state or 'in progress'}.",
        )
    conclusion = str(latest.get("conclusion") or "completed")
    failed = conclusion in {"failure", "timed_out", "startup_failure"}
    label = "Failure" if failed else "Success"
    return CheckResult(
        "workflows",
        label,
        f"{name} finished with {conclusion}.",
        failed,
    )
