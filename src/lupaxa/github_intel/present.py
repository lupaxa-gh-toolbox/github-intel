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
from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT, format_date, format_timestamp
from lupaxa.github_intel.sync.engine import SyncReport
from lupaxa.github_intel.views import (
    RepositoryView,
    detail_rows,
    metric_cells,
    metric_columns,
    split_identifier,
    status_style,
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
) -> None:
    """
    Print a repository table.

    Args:
        views: Rows to show.
        date_format: Pattern such as ``DD/MM/YYYY``.

    """

    table = Table(title="Repositories")
    for column in (
        "Org",
        "Repo",
        "Visibility",
        "Group",
        "Profile",
        "Status",
        "Version",
        "Last push",
        "Release date",
    ):
        table.add_column(column)
    columns = metric_columns(list(views))
    for column in columns:
        table.add_column(column, justify="right")
    for view in views:
        org, name = split_identifier(view.repo)
        table.add_row(
            org,
            name,
            view.visibility,
            view.group,
            view.profile,
            _painted(view.status),
            view.version,
            format_date(view.last_push, date_format),
            format_date(view.release_date, date_format),
            *metric_cells(view, columns),
        )
    stdout_console().print(table)


def print_detail(
    view: RepositoryView,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> None:
    """
    Print one repository as a field and value table.

    Args:
        view: Repository to show.
        date_format: Pattern such as ``DD/MM/YYYY``.

    """

    table = Table(title=view.repo)
    table.add_column("Field")
    table.add_column("Value")
    for field, value in detail_rows(view, date_format=date_format):
        table.add_row(field, _painted(value))
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
    rules = Table(title="Standards")
    rules.add_column("Rule")
    rules.add_column("Required")
    for name, required in resolved.standards.model_dump().items():
        rules.add_row(name, "Yes" if required else "No")
    console.print(rules)


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


def _painted(value: str) -> str | Text:
    style = status_style(value)
    if not style:
        return value
    return Text(value, style=style)


def format_time(
    value: float | None,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> str:
    """
    Format a cache timestamp.

    Args:
        value: Epoch seconds, or None.
        date_format: Pattern such as ``DD/MM/YYYY``.

    Returns:
        UTC timestamp, or an empty string.

    """

    return format_timestamp(value, date_format)
