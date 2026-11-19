"""Values shown beside each repository in the list."""

from __future__ import annotations

import re

__all__ = [
    "ahead_count",
    "collection_count",
    "format_count",
    "issue_count",
    "latest_published",
    "latest_tag",
    "run_state",
    "workflow_definitions",
    "workflow_label",
]

_LAST_PAGE = re.compile(r"""[?&]page=(\d+)[^>]*>;\s*rel="last\"""")


def latest_published(body: object) -> str:
    """
    Return the calendar date of the newest published release.

    Args:
        body: Release list from GitHub, newest first.

    Returns:
        ``YYYY-MM-DD``, or an empty string when no published release exists.

    """

    if not isinstance(body, list):
        return ""
    for item in body:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        return _calendar_date(item.get("published_at"))
    return ""


def latest_tag(body: object) -> str:
    """
    Return the newest published release tag.

    Args:
        body: Release list from GitHub, newest first.

    Returns:
        Tag text, or an empty string when no published release exists.

    """

    if not isinstance(body, list):
        return ""
    for item in body:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        tag = item.get("tag_name")
        return tag if isinstance(tag, str) else ""
    return ""


def collection_count(*, body: object, link: str | None, failed: bool) -> int | None:
    """
    Return how many items a one-item page represents.

    Args:
        body: JSON list from the first page.
        link: Value of the Link header, if GitHub sent one.
        failed: The request did not succeed.

    Returns:
        The collection size, or None when it cannot be known.

    """

    if failed or not isinstance(body, list):
        return None
    if link:
        match = _LAST_PAGE.search(link)
        if match:
            return int(match.group(1))
        if 'rel="next"' in link:
            return None
    return len(body)


def issue_count(open_issues_count: object, pulls: int | None) -> int | None:
    """
    Return open issues, excluding pull requests.

    Args:
        open_issues_count: Repository field that counts issues and pull requests.
        pulls: Open pull requests, or None when that count is unknown.

    Returns:
        Open issues, or None when the two counts cannot be separated.

    """

    if pulls is None or isinstance(open_issues_count, bool):
        return None
    if not isinstance(open_issues_count, int):
        return None
    return max(0, open_issues_count - pulls)


def ahead_count(body: object) -> int | None:
    """
    Return commits on the default branch that are not in the release.

    Args:
        body: Compare payload from GitHub.

    Returns:
        The ahead count, or None when GitHub did not report one.

    """

    if not isinstance(body, dict):
        return None
    value = body.get("ahead_by")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def workflow_definitions(items: object) -> tuple[tuple[int, str], ...]:
    """
    Return each workflow's id and name.

    Args:
        items: The ``workflows`` array from GitHub.

    Returns:
        Id and display name pairs.

    """

    if not isinstance(items, list):
        return ()
    found: list[tuple[int, str]] = []
    for item in items:
        if not isinstance(item, dict) or isinstance(item.get("id"), bool):
            continue
        workflow_id = item.get("id")
        if not isinstance(workflow_id, int):
            continue
        name = item.get("name")
        if not isinstance(name, str) or name == "":
            path = item.get("path")
            name = path if isinstance(path, str) and path else f"Workflow {workflow_id}"
        found.append((workflow_id, name))
    return tuple(found)


def newest_run(items: object) -> dict[int, dict[str, object]]:
    """
    Keep the first run for each workflow.

    Args:
        items: The ``workflow_runs`` array, newest first.

    Returns:
        Workflow id to that run.

    """

    if not isinstance(items, list):
        return {}
    found: dict[int, dict[str, object]] = {}
    for item in items:
        if not isinstance(item, dict) or isinstance(item.get("workflow_id"), bool):
            continue
        workflow_id = item.get("workflow_id")
        if isinstance(workflow_id, int) and workflow_id not in found:
            found[workflow_id] = item
    return found


def run_state(run: object) -> str:
    """
    Return the result of one workflow run.

    Args:
        run: A workflow run object, or None when that workflow has not run.

    Returns:
        Success, Failure, In progress, or Never run.

    """

    from lupaxa.github_intel.checks.workflows import evaluate_workflows

    if not isinstance(run, dict):
        return "Never run"
    return evaluate_workflows([run], None).status


def workflow_label(body: object, *, failed: bool) -> str:
    """
    Return the newest workflow result on the requested branch.

    Args:
        body: Actions runs payload.
        failed: The request did not succeed.

    Returns:
        Success, Failure, In progress, or Never run.

    """

    from lupaxa.github_intel.checks.workflows import evaluate_workflows

    if failed or not isinstance(body, dict):
        return "Never run"
    raw = body.get("workflow_runs")
    if not isinstance(raw, list):
        return "Never run"
    runs = [item for item in raw if isinstance(item, dict)]
    return evaluate_workflows(runs, None).status


def format_count(value: int | None) -> str:
    """
    Format a count for a table cell.

    Args:
        value: Count, or None when it is unknown.

    Returns:
        Decimal text, or an empty string.

    """

    if value is None:
        return ""
    return str(value)


def _calendar_date(value: object) -> str:
    if not isinstance(value, str) or len(value) < 10:
        return ""
    if value[4] != "-" or value[7] != "-":
        return ""
    return value[:10]
