"""Release check evaluation."""

from __future__ import annotations

from typing import Any

from lupaxa.github_intel.checks.base import CheckResult

__all__ = ["evaluate_releases"]


def evaluate_releases(
    releases: list[dict[str, Any]] | None,
    *,
    compare_status: str | None,
    ahead_by: int | None,
    compare_error: str | None,
    fetch_error: str | None,
) -> CheckResult:
    """
    Classify the latest published release against the default branch.

    Args:
        releases: Release objects from the GitHub API.
        compare_status: Compare API status, when the call succeeded.
        ahead_by: Commits on the default branch after the tag.
        compare_error: Compare call failure, if any.
        fetch_error: Release list failure, if any.

    Returns:
        Release check result. A tag that is not an ancestor is Unknown.

    """

    if fetch_error and not releases:
        return CheckResult("releases", "Error", fetch_error, True)
    published = [item for item in releases or [] if not item.get("draft")]
    if not published:
        return CheckResult("releases", "No releases", "No published releases found.")
    tag = str(published[0].get("tag_name") or "")
    if compare_error:
        return CheckResult("releases", "Unknown", compare_error)
    if compare_status == "diverged":
        return CheckResult(
            "releases",
            "Unknown",
            f"{tag} is not an ancestor of the default branch.",
        )
    if ahead_by is not None and ahead_by > 0:
        return CheckResult(
            "releases",
            f"{ahead_by} Ahead",
            f"{ahead_by} commits on the default branch after {tag}.",
        )
    return CheckResult(
        "releases",
        "Current",
        f"{tag} has no newer commits on the default branch.",
    )
