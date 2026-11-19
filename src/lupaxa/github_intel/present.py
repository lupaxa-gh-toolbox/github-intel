"""Human-readable CLI output. Machine-readable output never uses this module."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from lupaxa.github_intel.config.profiles import ResolvedProfile
from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT, format_timestamp
from lupaxa.github_intel.layout import RIGHT_ALIGNED, hardcoded_list
from lupaxa.github_intel.sync.engine import SyncReport
from lupaxa.github_intel.views import (
    RepositoryView,
    detail_rows,
    field_text,
    status_style,
    visibility_style,
    workflow_text,
)

__all__ = [
    "print_detail",
    "print_profile",
    "print_repos",
    "print_sync",
    "stderr_console",
    "stdout_console",
    "syncing",
]


def stdout_console() -> Console:
    """
    Return a console for human stdout.

    Returns:
        Rich console.

    """

    return Console()


def stderr_console() -> Console:
    """
    Return a console for progress and diagnostics.

    Returns:
        Rich console bound to stderr.

    """

    return Console(stderr=True)


def print_repos(
    views: list[RepositoryView],
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
    fields: tuple[str, ...] | None = None,
) -> None:
    """
    Print a repository table.

    Args:
        views: Rows to show.
        date_format: Pattern such as ``DD/MM/YYYY HH:mm UTC``.
        fields: Catalogue labels. ``None`` uses the hardcoded list.

    """

    columns = hardcoded_list(views) if fields is None else fields
    table = Table(title="Repositories", header_style="bold cyan")
    for column in columns:
        table.add_column(
            column,
            justify="right" if column in RIGHT_ALIGNED else "left",
        )
    for view in views:
        table.add_row(*list_row(view, columns, date_format))
    stdout_console().print(table)


def print_detail(
    view: RepositoryView,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
    fields: tuple[str, ...] | None = None,
) -> None:
    """
    Print one repository as a field and value table.

    Args:
        view: Repository to show.
        date_format: Pattern such as ``DD/MM/YYYY HH:mm UTC``.
        fields: Catalogue labels. ``None`` keeps every current row.

    """

    table = Table(title=repo_title(view))
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    for field, value in detail_rows(view, date_format=date_format, fields=fields):
        table.add_row(field, _present_cell(field, value, view))
    stdout_console().print(table)


def print_profile(resolved: ResolvedProfile, *, show_sources: bool) -> None:
    """
    Print one profile.

    Args:
        resolved: Effective flags.
        show_sources: Include the profile that set each flag.

    """

    console = stdout_console()
    console.print(f"Profile: {resolved.name}")
    console.print("Inheritance: " + " -> ".join(resolved.chain))
    table = Table()
    table.add_column("Check")
    table.add_column("Enabled")
    if show_sources:
        table.add_column("Source")
    for name in sorted(resolved.enabled):
        enabled = "Yes" if resolved.enabled[name] else "No"
        if show_sources:
            table.add_row(name, enabled, resolved.sources[name])
        else:
            table.add_row(name, enabled)
    console.print(table)


def print_sync(report: SyncReport) -> None:
    """
    Print synchronisation statistics.

    Args:
        report: Completed or cancelled run.

    """

    title = (
        "Synchronisation cancelled" if report.cancelled else "Synchronisation completed"
    )
    lines = [
        title,
        "",
        f"Repositories: {report.repositories}",
        f"Successful: {report.successful}",
        f"Failed: {report.failed}",
        f"Skipped: {report.skipped}",
        "",
        f"API requests: {report.requests}",
        f"Cache hits: {report.cache_hits}",
        f"Not modified: {report.not_modified}",
        "",
        f"Elapsed: {report.elapsed:.1f}s",
    ]
    if report.rate_pauses:
        lines.extend(["", f"Rate-limit pauses: {report.rate_pauses}"])
    stdout_console().print("\n".join(lines))
    for failure in report.failures:
        stderr_console().print(failure)


@contextmanager
def syncing() -> Iterator[Callable[[SyncReport], None]]:
    """
    Show synchronisation progress on stderr.

    A terminal gets a status bar. Any other stderr gets one line each time a
    repository finishes.

    Yields:
        Callback for :meth:`Service.sync`. It must not await.

    """

    console = stderr_console()
    if not console.is_terminal:
        seen = {"done": -1, "wait": -1}

        def emit(report: SyncReport) -> None:
            done = report.successful + report.failed
            waiting = int(report.rate_wait)
            if done == seen["done"] and waiting == seen["wait"]:
                return
            seen["done"] = done
            seen["wait"] = waiting
            console.print(_status_line(report))

        yield emit
        return

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
    with progress:
        task = progress.add_task("Synchronising", total=None)

        def update(report: SyncReport) -> None:
            done = report.successful + report.failed
            progress.update(
                task,
                completed=done,
                total=report.repositories or None,
                description=_status_line(report),
            )

        yield update


def _status_line(report: SyncReport) -> str:
    done = report.successful + report.failed
    name = report.latest or "Synchronising"
    line = (
        f"{name}  {done}/{report.repositories}"
        f"  requests {report.requests}"
        f"  cache {report.cache_hits}"
        f"  failed {report.failed}"
    )
    if report.rate_wait > 0:
        remaining = _wait_label(report.rate_wait)
        return f"{line}  waiting for GitHub rate limit, requests resume in {remaining}"
    if report.rate_pauses:
        return f"{line}  rate limit pauses {report.rate_pauses}"
    return line


def _wait_label(seconds: float) -> str:
    remaining = max(0, int(seconds + 0.5))
    minutes, secs = divmod(remaining, 60)
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def list_row(
    view: RepositoryView,
    fields: tuple[str, ...],
    date_format: str,
) -> tuple[str | Text, ...]:
    """
    Paint one repository list row.

    Args:
        view: Repository to show.
        fields: Catalogue labels, in column order.
        date_format: Pattern such as ``DD/MM/YYYY HH:mm UTC``.

    Returns:
        One cell per field.

    """

    cells: list[str | Text] = []
    for label in fields:
        text = field_text(view, label, date_format, detail=False)
        cells.append(_present_cell(label, text, view))
    return tuple(cells)


def repo_title(view: RepositoryView) -> str | Text:
    """Colour the repository id red when its record failed."""
    if view.metadata_error:
        return Text(view.repo, style="red")
    return view.repo


def _present_cell(label: str, value: str, view: RepositoryView) -> str | Text:
    if label == "Workflows" and view.workflows:
        listed = workflow_text(view.workflows)
        if listed.plain == value:
            return listed
    style = _cell_style(label, value, view)
    if not style or not value:
        return value
    return Text(value, style=style)


def _cell_style(label: str, value: str, view: RepositoryView) -> str:
    if label == "Repository" and view.metadata_error:
        return "red"
    if label == "Metadata error":
        return "red"
    if label == "Visibility":
        return visibility_style(value)
    if label == "Status":
        return status_style(view.status)
    if label == "Enabled":
        return {"yes": "green", "no": "dim"}.get(value.strip().casefold(), "")
    if label == "Archived" and value.strip().casefold() == "yes":
        return "yellow"
    if label == "Fork" and value.strip().casefold() == "yes":
        return "cyan"
    if label == "Ahead":
        return _count_style(value, zero="green", positive="yellow")
    if label in {"Quality", "Dependabot Alerts"}:
        counted = _count_style(value, zero="green", positive="yellow")
        return counted or status_style(value)
    if label == "Cache":
        return _cache_style(value)
    return status_style(value)


def _count_style(value: str, *, zero: str, positive: str) -> str:
    text = value.strip()
    if not text.isdigit():
        return ""
    return zero if int(text) == 0 else positive


def _cache_style(value: str) -> str:
    tokens = {part.strip().casefold() for part in value.split(",") if part.strip()}
    if tokens & {"error", "unavailable"}:
        return "red"
    if "stale" in tokens:
        return "yellow"
    if "cached" in tokens:
        return "green"
    return ""


def format_time(
    value: float | None,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> str:
    """
    Format a cache timestamp.

    Args:
        value: Epoch seconds, or None.
        date_format: Pattern such as ``DD/MM/YYYY HH:mm UTC``.

    Returns:
        UTC timestamp, or an empty string.

    """

    return format_timestamp(value, date_format)
