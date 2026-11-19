"""Configurable repository standards checks."""

from __future__ import annotations

from lupaxa.github_intel.checks.base import CheckResult
from lupaxa.github_intel.config.models import StandardsSettings

__all__ = [
    "STANDARD_PATHS",
    "evaluate_standards",
    "tree_statuses",
]

STANDARD_PATHS: dict[str, tuple[str, ...]] = {
    "readme": ("README.md", "README.rst", "README.txt", "README"),
    "licence": ("LICENCE", "LICENSE", "LICENCE.md", "LICENSE.md", "COPYING"),
    "gitignore": (".gitignore",),
    "workflows": (".github/workflows",),
    "python_packaging": ("pyproject.toml", "setup.py", "setup.cfg"),
    "mkdocs": ("mkdocs.yml", "mkdocs.yaml"),
    "tests": ("tests", "test"),
}


def tree_statuses(body: object, paths: tuple[str, ...]) -> dict[str, int | None] | None:
    """
    Map standards paths to 200 or 404 from one recursive git tree.

    Args:
        body: GitHub git tree response.
        paths: File and directory paths the rules care about.

    Returns:
        Status by path, or None when the tree is missing or truncated.

    """

    if not isinstance(body, dict) or body.get("truncated") is True:
        return None
    entries = body.get("tree")
    if not isinstance(entries, list):
        return None
    present = {
        item["path"]
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    statuses: dict[str, int | None] = {}
    for path in paths:
        prefix = f"{path}/"
        found = path in present or any(entry.startswith(prefix) for entry in present)
        statuses[path] = 200 if found else 404
    return statuses


def evaluate_standards(
    settings: StandardsSettings,
    statuses: dict[str, int | None],
) -> list[CheckResult]:
    """
    Evaluate each enabled standards rule.

    Args:
        settings: Which rules are required.
        statuses: Path to HTTP status. None means the request failed.

    Returns:
        One result per rule. Disabled rules are SKIPPED.

    """

    results: list[CheckResult] = []
    for name, paths in STANDARD_PATHS.items():
        if not getattr(settings, name):
            results.append(
                CheckResult(f"standards:{name}", "SKIPPED", f"{name} is not required."),
            )
            continue
        results.append(_one_rule(name, paths, statuses))
    return results


def _one_rule(
    name: str,
    paths: tuple[str, ...],
    statuses: dict[str, int | None],
) -> CheckResult:
    saw_error = False
    for path in paths:
        status = statuses.get(path)
        if status == 200:
            return CheckResult(f"standards:{name}", "PASS", f"{path} exists.")
        if status is None or status not in {404, 200}:
            saw_error = True
    if saw_error:
        return CheckResult(
            f"standards:{name}",
            "ERROR",
            f"Could not verify {name}.",
            True,
        )
    return CheckResult(f"standards:{name}", "FAIL", f"No {name} file was found.", True)
