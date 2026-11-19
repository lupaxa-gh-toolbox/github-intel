"""Security check placeholder."""

from __future__ import annotations

from lupaxa.github_intel.checks.base import CheckResult

__all__ = ["evaluate_security"]


def evaluate_security(*, enabled: bool) -> CheckResult:
    """
    Report the security check without claiming a repository is secure.

    Args:
        enabled: Whether the resolved profile asked for the check.

    Returns:
        SKIPPED. The check is reserved for a later release.

    """

    if not enabled:
        return CheckResult("security", "SKIPPED", "Security checks are disabled.")
    return CheckResult(
        "security",
        "SKIPPED",
        "Security checks are not implemented yet.",
    )
