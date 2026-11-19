"""Repository rows shared by the CLI, reports, and TUI."""

from __future__ import annotations

from dataclasses import dataclass
import time

from lupaxa.github_intel.config.loader import LoadedConfig
from lupaxa.github_intel.config.models import RepositorySpec
from lupaxa.github_intel.config.profiles import resolve_profile
from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT, format_date
from lupaxa.github_intel.storage.database import Document, StoredCheck
from lupaxa.github_intel.sync.summary import (
    ahead_count,
    format_count,
    latest_published,
    workflow_label,
)

__all__ = [
    "RepositoryView",
    "build_view",
    "detail_rows",
    "metric_cells",
    "metric_columns",
    "select_repositories",
    "split_identifier",
    "status_style",
]


@dataclass(frozen=True)
class RepositoryView:
    """One repository as shown in lists and reports."""

    repo: str
    group: str
    profile: str
    tags: tuple[str, ...]
    enabled: bool
    description: str
    visibility: str
    status: str
    statuses: tuple[str, ...]
    updated_at: float | None
    checks: tuple[StoredCheck, ...]
    metadata_error: str | None
    version: str
    open_pulls: int | None
    open_issues: int | None
    codeql: int
    archived: bool
    last_push: str
    stars: int | None
    licence: str
    release_date: str
    ahead: int | None
    workflow: str
    workflows: tuple[tuple[str, str], ...] | None
    workflows_enabled: bool
    issues_enabled: bool
    pull_requests_enabled: bool
    quality_enabled: bool
    dependencies: int


def build_view(
    loaded: LoadedConfig,
    repository: RepositorySpec,
    documents: list[Document],
    checks: list[StoredCheck],
) -> RepositoryView:
    """
    Combine configuration with cached documents.

    Args:
        loaded: Configuration, used for the metadata TTL.
        repository: Configured repository.
        documents: Cached payloads.
        checks: Stored check rows.

    Returns:
        Display row.

    """

    metadata = _document(documents, "metadata")
    body = {} if metadata is None else metadata.json_body()
    description = ""
    if isinstance(body, dict) and isinstance(body.get("description"), str):
        description = body["description"]
    updated = None if metadata is None else metadata.fetched_at
    statuses = _statuses(repository, metadata, loaded.config.sync.cache.metadata_ttl)
    summary = _summary(documents)
    profile_name = repository.profile or loaded.config.defaults.profile
    resolved = resolve_profile(
        loaded.profiles,
        profile_name,
        repository.checks,
        loaded.config.defaults.standards,
        issues=loaded.config.defaults.issues,
        pull_requests=loaded.config.defaults.pull_requests,
        quality=loaded.config.defaults.quality,
    )
    ahead = _ahead(summary, documents)
    return RepositoryView(
        repo=repository.repo,
        group=repository.group,
        profile=profile_name,
        tags=tuple(repository.tags),
        enabled=repository.enabled,
        description=description,
        visibility=_visibility(body),
        status=_release_label(_headline(repository, metadata, checks), ahead),
        statuses=tuple(sorted(statuses)),
        updated_at=updated,
        checks=tuple(checks),
        metadata_error=None if metadata is None else metadata.error,
        version=_text(summary, "version"),
        open_pulls=_whole(summary, "open_pulls"),
        open_issues=_whole(summary, "open_issues"),
        codeql=_quality(summary),
        archived=_archived(body),
        last_push=_last_push(body),
        stars=_stars(body),
        licence=_licence(body),
        release_date=_release_date(summary, documents),
        ahead=ahead,
        workflow=_workflow(summary, documents),
        workflows=_workflows(summary),
        workflows_enabled=resolved.enabled["workflows"],
        issues_enabled=resolved.enabled["issues"],
        pull_requests_enabled=resolved.enabled["pull_requests"],
        quality_enabled=resolved.enabled["quality"],
        dependencies=_dependencies(summary),
    )


def detail_rows(
    view: RepositoryView,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> tuple[tuple[str, str], ...]:
    """
    Return the field and value rows for one repository.

    Args:
        view: Repository to describe.
        date_format: Pattern such as ``DD/MM/YYYY``.

    Returns:
        Ordered pairs for the detail table.

    """

    org, name = split_identifier(view.repo)
    status, checks = _status_and_checks(view)
    rows = [
        ("Org", org),
        ("Repo", name),
        ("Visibility", view.visibility),
        ("Description", view.description or "No description"),
        ("Group", view.group),
        ("Profile", view.profile),
        ("Status", status),
        ("Archived", "yes" if view.archived else "no"),
        ("Last push", format_date(view.last_push, date_format)),
        ("Stars", format_count(view.stars)),
        ("Licence", view.licence),
        ("Version", view.version),
        ("Release date", format_date(view.release_date, date_format)),
        ("Ahead", format_count(view.ahead)),
        _count_row(
            "Pull requests",
            view.pull_requests_enabled,
            view.open_pulls,
            "Pull request checks are disabled.",
        ),
        _count_row(
            "Issues",
            view.issues_enabled,
            view.open_issues,
            "Issue checks are disabled.",
        ),
        _count_row(
            "Quality",
            view.quality_enabled,
            view.codeql,
            "Quality checks are disabled.",
        ),
        *_workflow_rows(view),
        ("Dependencies", str(view.dependencies)),
        *checks,
    ]
    return tuple(rows)


def status_style(value: str) -> str:
    """
    Choose a terminal colour for a status.

    Args:
        value: Status text, or a detail value that starts with one.

    Returns:
        ``green``, ``yellow``, ``red``, ``dim``, or an empty string.

    """

    label = value.split(" — ", 1)[0].strip().casefold()
    if label in {"current", "healthy", "success"}:
        return "green"
    if label.endswith(" ahead") or label in {"no releases", "unknown", "in progress"}:
        return "yellow"
    if label in {"fail", "error", "failure", "unavailable"}:
        return "red"
    if label in {"disabled", "not synchronised", "never run"} or label.startswith(
        "skipped",
    ):
        return "dim"
    return ""


def split_identifier(identifier: str) -> tuple[str, str]:
    """
    Split ``owner/name`` into the organisation and the repository name.

    Args:
        identifier: GitHub repository identifier.

    Returns:
        Organisation and repository name.

    """

    org, separator, name = identifier.partition("/")
    if separator != "/":
        return "", identifier
    return org, name


def select_repositories(
    loaded: LoadedConfig,
    *,
    group: str | None = None,
    profile: str | None = None,
    tag: str | None = None,
    repo: str | None = None,
    enabled_only: bool = False,
) -> tuple[RepositorySpec, ...]:
    """
    Filter the configured collection.

    Args:
        loaded: Configuration.
        group: Required group, if any.
        profile: Required profile, if any.
        tag: Required tag, compared without case.
        repo: One repository identifier.
        enabled_only: Drop disabled repositories.

    Returns:
        Matching repositories.

    """

    chosen: list[RepositorySpec] = []
    for repository in loaded.repositories:
        if enabled_only and not repository.enabled:
            continue
        if group is not None and repository.group != group:
            continue
        name = repository.profile or loaded.config.defaults.profile
        if profile is not None and name != profile:
            continue
        if tag is not None and tag.casefold() not in {
            item.casefold() for item in repository.tags
        }:
            continue
        if repo is not None and repository.repo.casefold() != repo.casefold():
            continue
        chosen.append(repository)
    return tuple(chosen)


def _statuses(
    repository: RepositorySpec,
    metadata: Document | None,
    ttl: int,
) -> set[str]:
    statuses = {"enabled" if repository.enabled else "disabled"}
    if metadata is None or metadata.fetched_at is None:
        statuses.add("not-synchronised")
        return statuses
    statuses.add("cached")
    if metadata.error and "404" in metadata.error:
        statuses.add("unavailable")
    elif metadata.error:
        statuses.add("error")
    if time.time() - metadata.fetched_at >= ttl:
        statuses.add("stale")
    return statuses


def _headline(
    repository: RepositorySpec,
    metadata: Document | None,
    checks: list[StoredCheck],
) -> str:
    if not repository.enabled:
        return "Disabled"
    if metadata is None or metadata.fetched_at is None:
        return "Not synchronised"
    if metadata.error and "404" in metadata.error:
        return "Unavailable"
    if metadata.error:
        return "Error"
    for check in checks:
        if check.name == "releases" and check.status == "No releases":
            return check.status
    for check in checks:
        if check.failure:
            return check.status
    for check in checks:
        if check.name == "releases":
            return check.status
    return "Healthy"


def _release_label(status: str, ahead: int | None) -> str:
    if status == "Unreleased changes" and ahead is not None and ahead > 0:
        return f"{ahead} Ahead"
    return status


def _summary(documents: list[Document]) -> dict[str, object]:
    document = _document(documents, "summary")
    if document is None or document.error:
        return {}
    body = document.json_body()
    return body if isinstance(body, dict) else {}


def _text(summary: dict[str, object], key: str) -> str:
    value = summary.get(key)
    return value if isinstance(value, str) else ""


def _archived(body: object) -> bool:
    return isinstance(body, dict) and body.get("archived") is True


def _last_push(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    # GitHub sets pushed_at when it creates an empty repository.
    if body.get("size") == 0:
        return ""
    return _calendar_day(body.get("pushed_at"))


def _visibility(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    visibility = body.get("visibility")
    if visibility in {"public", "private", "internal"}:
        return str(visibility)
    if body.get("private") is True:
        return "private"
    if body.get("private") is False:
        return "public"
    return ""


def _stars(body: object) -> int | None:
    if not isinstance(body, dict):
        return None
    value = body.get("stargazers_count")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _licence(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    license_info = body.get("license")
    if not isinstance(license_info, dict):
        return ""
    spdx = license_info.get("spdx_id")
    if not isinstance(spdx, str) or spdx in {"", "NOASSERTION"}:
        return ""
    return spdx


def _release_date(summary: dict[str, object], documents: list[Document]) -> str:
    if "release_date" in summary:
        return _text(summary, "release_date")
    releases = _document(documents, "releases")
    if releases is None or releases.error:
        return ""
    return latest_published(releases.json_body())


def _ahead(summary: dict[str, object], documents: list[Document]) -> int | None:
    if "ahead" in summary:
        return _whole(summary, "ahead")
    for document in documents:
        if document.category.startswith("compare:") and document.error is None:
            return ahead_count(document.json_body())
    return None


def _workflows(summary: dict[str, object]) -> tuple[tuple[str, str], ...] | None:
    if "workflows" not in summary:
        return None
    value = summary["workflows"]
    if not isinstance(value, list):
        return None
    rows: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        status = item.get("status")
        if isinstance(name, str) and name and isinstance(status, str):
            rows.append((name, status))
    return tuple(rows)


def metric_columns(views: list[RepositoryView]) -> tuple[str, ...]:
    """
    Return the numeric list columns that at least one repository shows.

    Args:
        views: Rows about to be printed. An empty list keeps the default columns.

    Returns:
        Column headings, starting with Stars.

    """

    columns = ["Stars"]
    for label, enabled, default in (
        ("Pull requests", "pull_requests_enabled", True),
        ("Issues", "issues_enabled", False),
        ("Quality", "quality_enabled", True),
    ):
        shown = default if not views else any(getattr(view, enabled) for view in views)
        if shown:
            columns.append(label)
    return tuple(columns)


def metric_cells(view: RepositoryView, columns: tuple[str, ...]) -> tuple[str, ...]:
    """
    Return the numeric cells for one row.

    Args:
        view: Repository row.
        columns: Headings from :func:`metric_columns`.

    Returns:
        One cell per heading. A disabled check is blank.

    """

    values = {
        "Stars": format_count(view.stars),
        "Pull requests": (
            format_count(view.open_pulls) if view.pull_requests_enabled else ""
        ),
        "Issues": format_count(view.open_issues) if view.issues_enabled else "",
        "Quality": format_count(view.codeql) if view.quality_enabled else "",
    }
    return tuple(values[column] for column in columns)


def _count_row(
    label: str,
    enabled: bool,
    value: int | None,
    reason: str,
) -> tuple[str, str]:
    if not enabled:
        return label, f"SKIPPED — {reason}"
    return label, format_count(value)


def _status_and_checks(view: RepositoryView) -> tuple[str, tuple[tuple[str, str], ...]]:
    status = view.status
    rows: list[tuple[str, str]] = []
    if not view.checks:
        return status, (("Checks", "Not synchronised"),)
    for item in view.checks:
        shown = item.status
        if item.name == "releases":
            shown = _release_label(item.status, view.ahead)
        text = f"{shown} — {item.summary}"
        if item.name == "releases" and shown == view.status:
            status = text
            continue
        rows.append((_check_label(item.name), text))
    return status, tuple(rows)


def _check_label(name: str) -> str:
    columns = {"releases": "Status"}
    return columns.get(name, f"Check {name}")


def _workflow_rows(view: RepositoryView) -> tuple[tuple[str, str], ...]:
    if not view.workflows_enabled:
        return (("Workflow", "SKIPPED — Workflow checks are disabled."),)
    if view.workflows is None:
        return (("Workflow", view.workflow),)
    if not view.workflows:
        return (("Workflows", "No workflows"),)
    return tuple((f"Workflow {name}", status) for name, status in view.workflows)


def _workflow(summary: dict[str, object], documents: list[Document]) -> str:
    if "workflow" in summary:
        return _text(summary, "workflow") or "Never run"
    document = _document(documents, "workflows")
    if document is None:
        return ""
    return workflow_label(document.json_body(), failed=document.error is not None)


def _dependencies(summary: dict[str, object]) -> int:
    value = _whole(summary, "dependencies")
    if value is None:
        return 0
    return value


def _calendar_day(value: object) -> str:
    if not isinstance(value, str) or len(value) < 10:
        return ""
    if value[4] != "-" or value[7] != "-":
        return ""
    return value[:10]


def _quality(summary: dict[str, object]) -> int:
    value = _whole(summary, "codeql")
    if value is None:
        return 0
    return value


def _whole(summary: dict[str, object], key: str) -> int | None:
    value = summary.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _document(documents: list[Document], category: str) -> Document | None:
    for document in documents:
        if document.category == category:
            return document
    return None
