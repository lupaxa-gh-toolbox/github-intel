"""JSON, CSV, and Markdown reports."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import io
import json

from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT, format_date, format_timestamp
from lupaxa.github_intel.sync.summary import format_count
from lupaxa.github_intel.views import (
    RepositoryView,
    metric_cells,
    metric_columns,
    split_identifier,
)

__all__ = ["render_report"]


def render_report(
    views: list[RepositoryView],
    report_format: str,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> str:
    """
    Render repository rows.

    Args:
        views: Rows to export.
        report_format: ``json``, ``csv``, or ``markdown``.
        date_format: Pattern used by the Markdown table.

    Returns:
        Report text.

    Raises:
        ValueError: The format is not supported.

    """

    if report_format == "json":
        return json.dumps([_row(view) for view in views], indent=2) + "\n"
    if report_format == "csv":
        return _csv(views)
    if report_format == "markdown":
        return _markdown(views, date_format)
    message = f"Unsupported report format: {report_format}"
    raise ValueError(message)


def _row(view: RepositoryView) -> dict[str, object]:
    return {
        "repo": view.repo,
        "group": view.group,
        "profile": view.profile,
        "tags": list(view.tags),
        "enabled": view.enabled,
        "description": view.description,
        "visibility": view.visibility,
        "status": view.status,
        "version": view.version,
        "open_pulls": view.open_pulls,
        "open_issues": view.open_issues,
        "codeql": view.codeql,
        "archived": view.archived,
        "last_push": view.last_push,
        "stars": view.stars,
        "licence": view.licence,
        "release_date": view.release_date,
        "ahead": view.ahead,
        "workflow": view.workflow,
        "workflows": None
        if view.workflows is None
        else [{"name": name, "status": status} for name, status in view.workflows],
        "dependencies": view.dependencies,
        "statuses": list(view.statuses),
        "updated_at": _stamp(view.updated_at),
        "metadata_error": view.metadata_error,
        "checks": [
            {
                "name": item.name,
                "status": item.status,
                "summary": item.summary,
                "failure": item.failure,
            }
            for item in view.checks
        ],
    }


def _csv(views: list[RepositoryView]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "repo",
            "group",
            "profile",
            "status",
            "version",
            "open_pulls",
            "open_issues",
            "codeql",
            "enabled",
            "updated_at",
            "description",
        ],
    )
    writer.writeheader()
    for view in views:
        writer.writerow(
            {
                "repo": view.repo,
                "group": view.group,
                "profile": view.profile,
                "status": view.status,
                "version": view.version,
                "open_pulls": format_count(view.open_pulls),
                "open_issues": format_count(view.open_issues),
                "codeql": format_count(view.codeql),
                "enabled": view.enabled,
                "updated_at": _stamp(view.updated_at),
                "description": view.description,
            }
        )
    return buffer.getvalue()


def _markdown(views: list[RepositoryView], date_format: str) -> str:
    columns = metric_columns(views)
    heading = (
        "| Org | Repo | Visibility | Group | Profile | Status | Version "
        "| Last push | Release date | " + " | ".join(columns) + " | Updated |"
    )
    separator = "| " + " | ".join("---" for _ in range(9 + len(columns) + 1)) + " |"
    lines = ["# GitHub Intel Report", "", heading, separator]
    for view in views:
        updated = format_timestamp(view.updated_at, date_format)
        org, name = split_identifier(view.repo)
        cells = (
            org,
            name,
            view.visibility,
            view.group,
            view.profile,
            view.status,
            view.version,
            format_date(view.last_push, date_format),
            format_date(view.release_date, date_format),
            *metric_cells(view, columns),
            updated,
        )
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def _stamp(value: float | None) -> str:
    if value is None:
        return ""
    return datetime.fromtimestamp(value, UTC).strftime("%Y-%m-%d %H:%M UTC")
