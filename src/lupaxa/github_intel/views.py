"""Repository rows shared by the CLI, reports, and TUI."""

from __future__ import annotations

from dataclasses import dataclass
import time

from rich.text import Text

from lupaxa.github_intel.config.loader import LoadedConfig
from lupaxa.github_intel.config.models import RepositorySpec
from lupaxa.github_intel.config.profiles import check_defaults, resolve_profile
from lupaxa.github_intel.dates import (
    DEFAULT_DATE_FORMAT,
    format_date,
    format_timestamp,
    normalize_instant,
)
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
    "field_text",
    "metric_cells",
    "metric_columns",
    "quality_text",
    "select_repositories",
    "split_identifier",
    "status_style",
    "visibility_style",
    "visibility_text",
    "workflow_text",
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
    codeql: int | None
    codeql_reason: str
    archived: bool
    last_push: str
    default_branch: str
    homepage: str
    language: str
    topics: tuple[str, ...]
    fork: bool
    forks: int | None
    watchers: int | None
    created: str
    github_updated: str
    size: int | None
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
    dependencies: int | None
    dependencies_reason: str


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
        **check_defaults(loaded.config.defaults),
    )
    checks = _shown_checks(checks)
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
        codeql_reason=_codeql_reason(summary),
        archived=_archived(body),
        last_push=_last_push(body),
        default_branch=_default_branch(body),
        homepage=_body_text(body, "homepage"),
        language=_body_text(body, "language"),
        topics=_topics(body),
        fork=_flag(body, "fork"),
        forks=_body_whole(body, "forks_count"),
        watchers=_body_whole(body, "subscribers_count"),
        created=_body_day(body, "created_at"),
        github_updated=_body_day(body, "updated_at"),
        size=_body_whole(body, "size"),
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
        dependencies_reason=_dependencies_reason(summary),
    )


def field_text(
    view: RepositoryView,
    label: str,
    date_format: str,
    *,
    detail: bool,
) -> str:
    """
    Return one catalogue cell.

    Args:
        view: Repository to describe.
        label: Catalogue field name.
        date_format: Pattern such as ``DD/MM/YYYY HH:mm UTC``.
        detail: Use the detail wording for a skipped check. Status is the
            short word on the list and the release sentence on the detail.

    Returns:
        The cell text. A disabled list check is blank, except Workflows,
        which stays ``SKIPPED — …`` on the list as well.

    """

    org, name = split_identifier(view.repo)
    cells = {
        "Organisation": org,
        "Repository": name,
        "Visibility": view.visibility,
        "Description": view.description or "No description",
        "Homepage": view.homepage,
        "Language": view.language,
        "Topics": ", ".join(view.topics),
        "Group": view.group,
        "Profile": view.profile,
        "Tags": ", ".join(view.tags),
        "Enabled": _yes_no(view.enabled),
        "Status": view.status if not detail else _status_and_checks(view)[0],
        "Cache": ", ".join(view.statuses),
        "Archived": _yes_no(view.archived),
        "Fork": _yes_no(view.fork),
        "Forks": format_count(view.forks),
        "Last push": format_date(view.last_push, date_format),
        "Created": format_date(view.created, date_format),
        "Updated": format_date(view.github_updated, date_format),
        "Synchronised": format_timestamp(view.updated_at, date_format),
        "Default branch": view.default_branch,
        "Size": "" if view.size is None else f"{view.size} KB",
        "Stars": format_count(view.stars),
        "Watchers": format_count(view.watchers),
        "Licence": view.licence,
        "Version": view.version,
        "Release date": format_date(view.release_date, date_format),
        "Ahead": format_count(view.ahead),
        "Workflows": _workflow_rows(view)[0][1],
        "Dependabot Alerts": _dependabot_text(view),
    }
    if label in cells:
        return cells[label]
    if label == "Pull requests":
        return _listed_count(
            label,
            view.pull_requests_enabled,
            view.open_pulls,
            "Pull request checks are disabled.",
            detail=detail,
        )
    if label == "Issues":
        return _listed_count(
            label,
            view.issues_enabled,
            view.open_issues,
            "Issue checks are disabled.",
            detail=detail,
        )
    if label == "Quality":
        if detail:
            return _count_row(
                label,
                view.quality_enabled,
                view.codeql,
                "Quality checks are disabled.",
                unknown=view.codeql_reason or "Unknown",
            )[1]
        return quality_text(view.quality_enabled, view.codeql, view.codeql_reason)
    message = f"unknown display field {label!r}."
    raise ValueError(message)


def _listed_count(
    label: str,
    enabled: bool,
    value: int | None,
    reason: str,
    *,
    detail: bool,
) -> str:
    if detail:
        return _count_row(label, enabled, value, reason)[1]
    if not enabled:
        return ""
    return format_count(value)


def detail_rows(
    view: RepositoryView,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
    fields: tuple[str, ...] | None = None,
) -> tuple[tuple[str, str], ...]:
    """
    Return the field and value rows for one repository.

    Args:
        view: Repository to describe.
        date_format: Pattern such as ``DD/MM/YYYY HH:mm UTC``.
        fields: Catalogue labels to show. ``None`` keeps every current row.

    Returns:
        Ordered pairs for the detail table.

    """

    if fields is not None:
        selected: list[tuple[str, str]] = []
        if view.metadata_error:
            selected.append(("Metadata error", view.metadata_error))
        selected.extend(
            (label, field_text(view, label, date_format, detail=True))
            for label in fields
        )
        return tuple(selected)

    org, name = split_identifier(view.repo)
    status, checks = _status_and_checks(view)
    rows = []
    if view.metadata_error:
        rows.append(("Metadata error", view.metadata_error))
    rows.extend(
        [
            ("Organisation", org),
            ("Repository", name),
            ("Visibility", view.visibility),
            ("Description", view.description or "No description"),
            ("Homepage", view.homepage),
            ("Language", view.language),
            ("Topics", ", ".join(view.topics)),
            ("Group", view.group),
            ("Profile", view.profile),
            ("Tags", ", ".join(view.tags)),
            ("Enabled", _yes_no(view.enabled)),
            ("Status", status),
            ("Cache", ", ".join(view.statuses)),
            ("Archived", _yes_no(view.archived)),
            ("Fork", _yes_no(view.fork)),
            ("Forks", format_count(view.forks)),
            ("Last push", format_date(view.last_push, date_format)),
            ("Created", format_date(view.created, date_format)),
            ("Updated", format_date(view.github_updated, date_format)),
            ("Synchronised", format_timestamp(view.updated_at, date_format)),
            ("Default branch", view.default_branch),
            ("Size", "" if view.size is None else f"{view.size} KB"),
            ("Stars", format_count(view.stars)),
            ("Watchers", format_count(view.watchers)),
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
                unknown=view.codeql_reason or "Unknown",
            ),
            *_workflow_rows(view),
            ("Dependabot Alerts", _dependabot_text(view)),
            *checks,
        ]
    )
    return tuple(rows)


def visibility_style(value: str) -> str:
    """
    Choose a colour for a visibility word.

    Args:
        value: ``public``, ``private``, ``internal``, or empty.

    Returns:
        ``green``, ``magenta``, ``cyan``, or an empty string.

    """

    return {"public": "green", "private": "magenta", "internal": "cyan"}.get(
        value.strip().casefold(),
        "",
    )


def visibility_text(value: str) -> str | Text:
    """
    Colour a visibility word.

    Args:
        value: ``public``, ``private``, ``internal``, or empty.

    Returns:
        Styled text, or the plain word when it has no colour.

    """

    style = visibility_style(value)
    if not style:
        return value
    return Text(value, style=style)


def status_style(value: str) -> str:
    """
    Choose a terminal colour for a status.

    Args:
        value: Status text, or a detail value that starts with one.

    Returns:
        ``green``, ``cyan``, ``yellow``, ``red``, ``dim``, or an empty string.

    """

    label = value.split(" — ", 1)[0].strip().casefold()
    if label in {"active", "current", "healthy", "success"}:
        return "green"
    if label == "no releases":
        return "cyan"
    if label == "no scanning":
        return "dim"
    if label.endswith(" ahead") or label in {"unknown", "forbidden", "in progress"}:
        return "yellow"
    if label in {"fail", "error", "failure", "unavailable"}:
        return "red"
    if (
        "disabled" in label
        or label in {"not synchronised", "never run"}
        or label.startswith("skipped")
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


def _shown_checks(checks: list[StoredCheck]) -> list[StoredCheck]:
    return [
        item
        for item in checks
        if item.name not in {"issues", "security"}
        and not item.name.startswith("standards:")
    ]


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


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _flag(body: object, key: str) -> bool:
    return isinstance(body, dict) and body.get(key) is True


def _body_day(body: object, key: str) -> str:
    return normalize_instant(_body_text(body, key))


def _body_text(body: object, key: str) -> str:
    if not isinstance(body, dict):
        return ""
    value = body.get(key)
    return value if isinstance(value, str) else ""


def _body_whole(body: object, key: str) -> int | None:
    if not isinstance(body, dict):
        return None
    return _whole({key: body.get(key)}, key)


def _topics(body: object) -> tuple[str, ...]:
    if not isinstance(body, dict):
        return ()
    value = body.get("topics")
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _archived(body: object) -> bool:
    return _flag(body, "archived")


def _default_branch(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    branch = body.get("default_branch")
    return branch if isinstance(branch, str) else ""


def _last_push(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    # GitHub sets pushed_at when it creates an empty repository.
    if body.get("size") == 0:
        return ""
    return normalize_instant(body.get("pushed_at"))


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
    releases = _document(documents, "releases")
    if releases is not None and not releases.error:
        published = latest_published(releases.json_body())
        if published:
            return published
    if "release_date" in summary:
        return _text(summary, "release_date")
    return ""


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
        "Quality": quality_text(
            view.quality_enabled,
            view.codeql,
            view.codeql_reason,
        ),
    }
    return tuple(values[column] for column in columns)


def quality_text(enabled: bool, count: int | None, reason: str = "") -> str:
    """
    Return the Quality cell.

    Args:
        enabled: The profile includes the quality check.
        count: Open CodeQL alerts, or None when GitHub did not share them.
        reason: Why the count is missing. Empty means ``Unknown``.

    Returns:
        A blank cell when the check is off, the reason when the count is
        missing, or the decimal count.

    """

    if not enabled:
        return ""
    if count is None:
        return reason or "Unknown"
    return str(count)


def _count_row(
    label: str,
    enabled: bool,
    value: int | None,
    reason: str,
    *,
    unknown: str = "",
) -> tuple[str, str]:
    if not enabled:
        return label, f"SKIPPED — {reason}"
    if value is None and unknown:
        return label, unknown
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
            status = item.summary or shown
            continue
        if item.name == "workflows":
            continue
        rows.append((_check_label(item.name), text))
    return status, tuple(rows)


def _check_label(name: str) -> str:
    return f"Check {name}"


def _workflow_rows(view: RepositoryView) -> tuple[tuple[str, str], ...]:
    if not view.workflows_enabled:
        return (("Workflows", "SKIPPED — Workflow checks are disabled."),)
    failed = next(
        (item for item in view.checks if item.name == "workflows" and item.failure),
        None,
    )
    if failed is not None:
        return (("Workflows", f"{failed.status} — {failed.summary}"),)
    if not view.workflows:
        return (("Workflows", "No workflows found"),)
    return (("Workflows", _workflow_table(view.workflows)),)


def workflow_text(workflows: tuple[tuple[str, str], ...]) -> Text:
    """
    Return the workflow list with each state coloured.

    Args:
        workflows: Name and state pairs, already sorted.

    Returns:
        A monospaced block. Names share a width and states share a column.

    """

    if not workflows:
        return Text("No workflows found")
    width = max(len(name) for name, _status in workflows)
    text = Text()
    for index, (name, status) in enumerate(workflows):
        if index:
            text.append("\n")
        text.append(f"{name:<{width}}  ")
        text.append(status, style=status_style(status) or None)
    return text


def _workflow_table(workflows: tuple[tuple[str, str], ...]) -> str:
    return workflow_text(workflows).plain


def _workflow(summary: dict[str, object], documents: list[Document]) -> str:
    if "workflow" in summary:
        return _text(summary, "workflow") or "Never run"
    document = _document(documents, "workflows")
    if document is None:
        return ""
    return workflow_label(document.json_body(), failed=document.error is not None)


def _dependabot_text(view: RepositoryView) -> str:
    if view.dependencies is None:
        return view.dependencies_reason or "Unknown"
    return str(view.dependencies)


def _dependencies(summary: dict[str, object]) -> int | None:
    if "dependencies" not in summary:
        return None
    return _whole(summary, "dependencies")


def _dependencies_reason(summary: dict[str, object]) -> str:
    if _dependencies(summary) is not None:
        return ""
    return _text(summary, "dependencies_reason")


def _quality(summary: dict[str, object]) -> int | None:
    return _whole(summary, "codeql")


def _codeql_reason(summary: dict[str, object]) -> str:
    if _quality(summary) is not None:
        return ""
    return _text(summary, "codeql_reason")


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
