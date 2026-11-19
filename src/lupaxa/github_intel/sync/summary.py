"""Values shown beside each repository in the list."""

from __future__ import annotations

import re

from lupaxa.github_intel.dates import normalize_instant

__all__ = [
    "ahead_count",
    "codeql_reading",
    "collection_count",
    "dependabot_reading",
    "format_count",
    "issue_count",
    "latest_published",
    "latest_tag",
    "workflow_activity",
    "workflow_definitions",
    "workflow_label",
]

_LAST_PAGE = re.compile(r"""[?&]page=(\d+)[^>]*>;\s*rel="last\"""")


def latest_published(body: object) -> str:
    """
    Return the publish time of the newest published release.

    Args:
        body: Release list from GitHub, newest first.

    Returns:
        An ISO instant, or an empty string when no published release exists.

    """

    if not isinstance(body, list):
        return ""
    for item in body:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        return normalize_instant(item.get("published_at"))
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


def codeql_reading(
    *,
    status: int,
    error: str | None,
    body: object,
    link: str | None,
) -> tuple[int | None, str]:
    """
    Return the open CodeQL count, or a short reason when it is missing.

    Args:
        status: HTTP status. Zero means the request did not complete.
        error: Client error text, or None for a successful response.
        body: JSON body from a successful response.
        link: Link header from a successful response.

    Returns:
        The count and an empty reason, or None and ``No scanning``,
        ``Forbidden``, or ``Unknown``.

    """

    if error is None:
        count = collection_count(body=body, link=link, failed=False)
        if count is None:
            return None, "Unknown"
        return count, ""
    folded = error.casefold()
    if status == 404 or _scanning_is_off(folded):
        return None, "No scanning"
    if status in {401, 403}:
        return None, "Forbidden"
    return None, "Unknown"


def dependabot_reading(
    *,
    status: int,
    error: str | None,
    body: object,
    link: str | None,
) -> tuple[int | None, str]:
    """
    Return the open Dependabot count, or a short reason when it is missing.

    Args:
        status: HTTP status. Zero means the request did not complete.
        error: Client error text, or None for a successful response.
        body: JSON body from a successful response.
        link: Link header from a successful response.

    Returns:
        The count and an empty reason, or None and ``Disabled``,
        ``Forbidden``, or ``Unknown``.

    """

    if error is None:
        count = collection_count(body=body, link=link, failed=False)
        if count is None:
            return None, "Unknown"
        return count, ""
    folded = error.casefold()
    if "disabled" in folded or "not enabled" in folded or "must be enabled" in folded:
        return None, "Disabled"
    if status in {401, 403, 404}:
        return None, "Forbidden"
    return None, "Unknown"


def _scanning_is_off(message: str) -> bool:
    return any(
        phrase in message
        for phrase in (
            "no analysis",
            "not enabled",
            "must be enabled",
            "advanced security",
            "code security",
        )
    )


def issue_count(open_issues_count: object) -> int | None:
    """
    Return GitHub's open issue total.

    Args:
        open_issues_count: Repository field. GitHub includes open pull requests.

    Returns:
        That total, or None when GitHub did not send a count.

    """

    if isinstance(open_issues_count, bool) or not isinstance(open_issues_count, int):
        return None
    return open_issues_count


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


def workflow_activity(state: object) -> str:
    """
    Return a display label for a workflow list entry.

    Args:
        state: GitHub workflow ``state``.

    Returns:
        ``Active``, a specific disabled reason, the state's own words, or
        ``Unknown`` when GitHub sent no state.

    """

    text = str(state or "").strip().casefold()
    if text == "active":
        return "Active"
    if text.startswith("disabled_"):
        reason = text.removeprefix("disabled_").replace("_", " ").title()
        return f"{reason} Disabled"
    if text == "disabled":
        return "Disabled"
    if not text:
        return "Unknown"
    return text.replace("_", " ").title()


def workflow_definitions(items: object) -> tuple[tuple[str, str], ...]:
    """
    Return each workflow's name and activity.

    Args:
        items: The ``workflows`` array from GitHub.

    Returns:
        Name and activity pairs, sorted by name.

    """

    if not isinstance(items, list):
        return ()
    found: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or name == "":
            path = item.get("path")
            workflow_id = item.get("id")
            if isinstance(path, str) and path:
                name = path
            elif isinstance(workflow_id, int) and not isinstance(workflow_id, bool):
                name = f"Workflow {workflow_id}"
            else:
                continue
        found.append((name, workflow_activity(item.get("state"))))
    found.sort(key=lambda item: item[0].casefold())
    return tuple(found)


def workflow_label(body: object, *, failed: bool) -> str:
    """
    Return the workflow-list headline from a stored workflow payload.

    Args:
        body: Workflow list payload.
        failed: The request did not succeed.

    Returns:
        ``Listed``, ``No workflows``, or an empty string.

    """

    if failed or not isinstance(body, dict):
        return ""
    pairs = workflow_definitions(body.get("workflows"))
    if not pairs:
        return "No workflows"
    return "Listed"


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
