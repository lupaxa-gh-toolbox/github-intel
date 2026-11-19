"""
Command-line interface for GitHub Intel.

Human output uses Rich. JSON and CSV are written to stdout alone.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
import sys
from typing import Any, TypeVar

import typer

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.constants import (
    EXIT_SYNC,
    PROGRAM_NAME,
    PROGRAM_VERSION_STRING,
)
from lupaxa.github_intel.errors import (
    AuthError,
    ChecksFailed,
    IntelError,
    SyncIncomplete,
)
from lupaxa.github_intel.present import (
    print_detail,
    print_profile,
    print_repos,
    print_sync,
    stderr_console,
    stdout_console,
    syncing,
)
from lupaxa.github_intel.reports.render import render_report
from lupaxa.github_intel.sync.engine import SyncReport
from lupaxa.github_intel.tui.application import run_tui

__all__ = ["app", "main"]

app = typer.Typer(
    name=PROGRAM_NAME,
    invoke_without_command=True,
    pretty_exceptions_enable=False,
    no_args_is_help=False,
)
repo_app = typer.Typer(help="Manage the configured repository list.")
profile_app = typer.Typer(help="Inspect monitoring profiles.")
config_app = typer.Typer(help="Show and validate configuration.")
cache_app = typer.Typer(help="Inspect and clear the local cache.")
app.add_typer(repo_app, name="repo")
app.add_typer(profile_app, name="profile")
app.add_typer(config_app, name="config")
app.add_typer(cache_app, name="cache")


class _State:
    def __init__(self, config: Path | None, verbose: bool, debug: bool) -> None:
        self.service = Service(config)
        self.service.log_level = "DEBUG" if verbose or debug else None


def _version(value: bool) -> None:
    if value:
        typer.echo(PROGRAM_VERSION_STRING)
        raise typer.Exit


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Main configuration file.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Write debug logs to stderr.",
    ),
    debug: bool = typer.Option(False, "--debug", help="Write debug logs to stderr."),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Monitor an explicit collection of GitHub repositories."""

    del version

    ctx.obj = _State(config, verbose, debug)
    if ctx.invoked_subcommand is not None:
        return
    if sys.stdin.isatty() and sys.stdout.isatty():
        run_tui(ctx.obj.service)
        return
    typer.echo(ctx.get_help())


@repo_app.command("list")
def repo_list(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group"),
    profile: str | None = typer.Option(None, "--profile"),
    tag: str | None = typer.Option(None, "--tag"),
    status: str | None = typer.Option(None, "--status"),
    sort: str = typer.Option("name", "--sort"),
    output_format: str = typer.Option("table", "--format"),
    offline: bool = typer.Option(False, "--offline", help="Read the cache only."),
) -> None:
    """List configured repositories."""

    del offline
    views = _run(
        ctx.obj.service.views(group=group, profile=profile, tag=tag, status=status),
    )
    views = _sort(views, sort)
    _emit_views(views, output_format, _date_format(ctx))


@app.command("list")
def list_alias(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group"),
    profile: str | None = typer.Option(None, "--profile"),
    tag: str | None = typer.Option(None, "--tag"),
    status: str | None = typer.Option(None, "--status"),
    sort: str = typer.Option("name", "--sort"),
    output_format: str = typer.Option("table", "--format"),
    offline: bool = typer.Option(False, "--offline"),
) -> None:
    """List configured repositories."""

    repo_list(ctx, group, profile, tag, status, sort, output_format, offline)


@repo_app.command("add")
def repo_add(
    ctx: typer.Context,
    repo: str = typer.Argument(...),
    group: str | None = typer.Option(None, "--group"),
    profile: str | None = typer.Option(None, "--profile"),
    tag: list[str] | None = typer.Option(None, "--tag"),
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Ask GitHub whether the repository is visible.",
    ),
) -> None:
    """Add a repository. This does not call GitHub unless --validate is set."""

    service = ctx.obj.service
    service.config_path = service.ensure_config()
    if validate:
        _run(service.check_remote(repo))
    _call(service.add, repo, group, profile, tag or [])
    stdout_console().print(f"Added {repo}.")


@repo_app.command("remove")
def repo_remove(ctx: typer.Context, repo: str = typer.Argument(...)) -> None:
    """Remove a repository from configuration. Cached data is kept."""

    _call(ctx.obj.service.remove, repo)
    stdout_console().print(f"Removed {repo}.")


@repo_app.command("enable")
def repo_enable(ctx: typer.Context, repo: str = typer.Argument(...)) -> None:
    """Include a repository in synchronisation."""

    _call(ctx.obj.service.set_fields, repo, enabled=True)


@repo_app.command("disable")
def repo_disable(ctx: typer.Context, repo: str = typer.Argument(...)) -> None:
    """Keep a repository in configuration but skip synchronisation."""

    _call(ctx.obj.service.set_fields, repo, enabled=False)


@repo_app.command("set-profile")
def repo_set_profile(
    ctx: typer.Context,
    repo: str = typer.Argument(...),
    profile: str = typer.Argument(...),
) -> None:
    """Assign a monitoring profile."""

    _call(ctx.obj.service.set_fields, repo, profile=profile)


@repo_app.command("set-group")
def repo_set_group(
    ctx: typer.Context,
    repo: str = typer.Argument(...),
    group: str = typer.Argument(...),
) -> None:
    """Assign a group. Groups do not change which checks run."""

    _call(ctx.obj.service.set_fields, repo, group=group)


@repo_app.command("show")
def repo_show(
    ctx: typer.Context,
    org: str = typer.Argument(..., metavar="ORG"),
    name: str | None = typer.Argument(None, metavar="REPO"),
    offline: bool = typer.Option(False, "--offline"),
    output_format: str = typer.Option("table", "--format"),
) -> None:
    """Show one repository. Pass the organisation and the repository name."""

    del offline
    view, _resolved, _documents = _run(ctx.obj.service.show(_identifier(org, name)))
    if output_format == "json":
        typer.echo(render_report([view], "json"), nl=False)
        return
    print_detail(view, date_format=_date_format(ctx))


@profile_app.command("list")
def profile_list(ctx: typer.Context) -> None:
    """List profile names."""

    loaded = _call(ctx.obj.service.load)
    for name in loaded.profiles:
        stdout_console().print(name)


@profile_app.command("show")
def profile_show(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    resolved: bool = typer.Option(False, "--resolved"),
) -> None:
    """Show a profile. --resolved includes the source of each flag."""

    from lupaxa.github_intel.config.profiles import resolve_profile

    loaded = _call(ctx.obj.service.load)
    print_profile(
        resolve_profile(
            loaded.profiles,
            name,
            {},
            loaded.config.defaults.standards,
            issues=loaded.config.defaults.issues,
            pull_requests=loaded.config.defaults.pull_requests,
            quality=loaded.config.defaults.quality,
        ),
        show_sources=resolved,
    )


@profile_app.command("tree")
def profile_tree(ctx: typer.Context) -> None:
    """Print each profile's inheritance chain."""

    from lupaxa.github_intel.config.profiles import resolve_profile

    loaded = _call(ctx.obj.service.load)
    for name in loaded.profiles:
        chain = " -> ".join(
            resolve_profile(
                loaded.profiles,
                name,
                {},
                loaded.config.defaults.standards,
                issues=loaded.config.defaults.issues,
                pull_requests=loaded.config.defaults.pull_requests,
                quality=loaded.config.defaults.quality,
            ).chain
        )
        stdout_console().print(f"{name}: {chain}")


@profile_app.command("validate")
def profile_validate(ctx: typer.Context) -> None:
    """Validate every profile, including inheritance."""

    from lupaxa.github_intel.config.profiles import resolve_profile

    loaded = _call(ctx.obj.service.load)
    for name in loaded.profiles:
        resolve_profile(
            loaded.profiles,
            name,
            {},
            loaded.config.defaults.standards,
            issues=loaded.config.defaults.issues,
            pull_requests=loaded.config.defaults.pull_requests,
            quality=loaded.config.defaults.quality,
        )
    stdout_console().print(f"Validated {len(loaded.profiles)} profiles.")


@config_app.command("show")
def config_show(ctx: typer.Context) -> None:
    """Print the resolved settings. Secrets are not part of the configuration."""

    loaded = _call(ctx.obj.service.load)
    stdout_console().print_json(data=loaded.config.model_dump())


@config_app.command("validate")
def config_validate(ctx: typer.Context) -> None:
    """Validate configuration files."""

    loaded = _call(ctx.obj.service.load)
    stdout_console().print(
        f"Configuration is valid ({len(loaded.repositories)} repositories).",
    )


@config_app.command("paths")
def config_paths(ctx: typer.Context) -> None:
    """Print configuration and cache paths."""

    from lupaxa.github_intel.config.paths import data_directory

    loaded = _call(ctx.obj.service.load)
    stdout_console().print(f"config: {loaded.path}")
    stdout_console().print(f"profiles: {loaded.profiles_path}")
    stdout_console().print(f"repositories: {loaded.repositories_path}")
    stdout_console().print(f"cache: {data_directory() / 'cache.sqlite'}")


@app.command("sync")
def sync_command(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Ignore cache freshness and sync.interval.",
    ),
    group: str | None = typer.Option(None, "--group"),
    profile: str | None = typer.Option(None, "--profile"),
    repo: str | None = typer.Option(None, "--repo"),
    stats: bool = typer.Option(False, "--stats"),
    concurrency: int | None = typer.Option(None, "--concurrency"),
    fail_on_checks: bool = typer.Option(False, "--fail-on-checks"),
) -> None:
    """Refresh stale or missing information. Ctrl+C cancels the run."""

    del stats
    try:
        _run(ctx.obj.service.assert_sync_allowed(force=force))
        with syncing() as on_progress:
            report = _run(
                ctx.obj.service.sync(
                    force=force,
                    group=group,
                    profile=profile,
                    repo=repo,
                    concurrency=concurrency,
                    on_progress=on_progress,
                )
            )
    except KeyboardInterrupt:
        stderr_console().print("Synchronisation cancelled.")
        raise typer.Exit(code=EXIT_SYNC) from None
    print_sync(report)
    _call(_finish_sync, report, fail_on_checks)


@app.command("report")
def report_command(
    ctx: typer.Context,
    output_format: str = typer.Option("markdown", "--format"),
    group: str | None = typer.Option(None, "--group"),
    profile: str | None = typer.Option(None, "--profile"),
    output: Path | None = typer.Option(None, "--output"),
    offline: bool = typer.Option(False, "--offline"),
) -> None:
    """Export repository information."""

    del offline
    views = _run(ctx.obj.service.views(group=group, profile=profile))
    text = render_report(views, output_format, date_format=_date_format(ctx))
    if output is None:
        sys.stdout.write(text)
        return
    output.write_text(text, encoding="utf-8")


@app.command("audit")
def audit_command(
    ctx: typer.Context,
    output_format: str = typer.Option("table", "--format"),
    fail_on_checks: bool = typer.Option(False, "--fail-on-checks"),
) -> None:
    """Show cached check results."""

    views = _run(ctx.obj.service.views())
    failing = [view for view in views if any(item.failure for item in view.checks)]
    if output_format == "json":
        typer.echo(render_report(failing, "json"), nl=False)
    else:
        print_repos(failing, date_format=_date_format(ctx))
    if fail_on_checks and failing:
        raise ChecksFailed(f"{len(failing)} repositories have failing checks.")


@app.command("releases")
def releases_command(ctx: typer.Context) -> None:
    """Show cached release check results."""

    _print_named_checks(ctx, "releases")


@app.command("workflows")
def workflows_command(ctx: typer.Context) -> None:
    """Show cached workflow check results."""

    _print_named_checks(ctx, "workflows")


@app.command("issues")
def issues_command(ctx: typer.Context) -> None:
    """Show cached issue check results."""

    _print_named_checks(ctx, "issues")


@cache_app.command("info")
def cache_info(ctx: typer.Context) -> None:
    """Show cache size and row counts."""

    info = _run(ctx.obj.service.cache_info())
    for key, value in info.items():
        stdout_console().print(f"{key}: {value}")


@cache_app.command("clear")
def cache_clear(
    ctx: typer.Context,
    repo: str | None = typer.Option(None, "--repo"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    """Delete cached data. Interactive runs ask for confirmation."""

    target = "all cached data" if repo is None else repo
    _confirm(f"Clear {target}?", yes)
    _run(ctx.obj.service.clear_cache(repo))


@cache_app.command("vacuum")
def cache_vacuum(ctx: typer.Context) -> None:
    """Rebuild the SQLite file."""

    _run(ctx.obj.service.vacuum())


@app.command("tui")
def tui_command(ctx: typer.Context) -> None:
    """Open the interactive interface."""

    run_tui(ctx.obj.service)


def main(argv: list[str] | None = None) -> None:
    """
    Run the command-line interface.

    Args:
        argv: Arguments excluding the program name. None reads the process arguments.

    """

    app(args=argv)


ResultT = TypeVar("ResultT")


def _call(func: Callable[..., ResultT], *args: object, **kwargs: object) -> ResultT:
    try:
        return func(*args, **kwargs)
    except IntelError as exc:
        stderr_console().print(str(exc))
        raise typer.Exit(code=exc.exit_code) from exc


def _run(coro: Coroutine[Any, Any, ResultT]) -> ResultT:
    try:
        return asyncio.run(coro)
    except IntelError as exc:
        stderr_console().print(str(exc))
        raise typer.Exit(code=exc.exit_code) from exc


def _date_format(ctx: typer.Context) -> str:
    loaded = _call(ctx.obj.service.load)
    pattern: str = loaded.config.display.date_format
    return pattern


def _emit_views(views: list[Any], output_format: str, date_format: str) -> None:
    if output_format in {"json", "csv", "markdown"}:
        sys.stdout.write(
            render_report(views, output_format, date_format=date_format),
        )
        return
    print_repos(views, date_format=date_format)


def _sort(views: list[Any], key: str) -> list[Any]:
    if key == "group":
        return sorted(views, key=lambda view: (view.group, view.repo))
    if key == "profile":
        return sorted(views, key=lambda view: (view.profile, view.repo))
    if key == "updated":
        return sorted(views, key=lambda view: (view.updated_at or 0, view.repo))
    return sorted(views, key=lambda view: view.repo.casefold())


def _finish_sync(report: SyncReport, fail_on_checks: bool) -> None:
    if report.auth_failed and report.successful == 0:
        raise AuthError("GitHub rejected the credentials.")
    if report.cancelled or report.failed:
        raise SyncIncomplete("Synchronisation did not finish cleanly.")
    if fail_on_checks and report.check_failures:
        raise ChecksFailed(f"{report.check_failures} checks failed.")


def _identifier(org: str, name: str | None) -> str:
    if name:
        return f"{org}/{name}"
    if "/" in org:
        return org
    message = "Pass the organisation and the repository name."
    raise typer.BadParameter(message)


def _print_named_checks(ctx: typer.Context, name: str) -> None:
    views = _run(ctx.obj.service.views())
    for view in views:
        for item in view.checks:
            if item.name == name:
                stdout_console().print(f"{view.repo}: {item.status} — {item.summary}")


def _confirm(message: str, yes: bool) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        stderr_console().print(f"{message} Re-run with --yes.")
        raise typer.Exit(code=2)
    answer = input(f"{message} [y/N] ")
    if answer.strip().casefold() != "y":
        raise typer.Exit(code=2)


if __name__ == "__main__":
    main()
