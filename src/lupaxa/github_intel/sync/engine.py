"""
Synchronise enabled repositories.

One repository failure does not cancel the others. Repositories are visited
in the same order as the default list: organisation, then name, ignoring
case. Up to the client's concurrency run at once. Completed rows are stored
as they finish.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import time
from typing import Any
from urllib.parse import quote

from lupaxa.github_intel.checks.base import CheckResult
from lupaxa.github_intel.checks.releases import evaluate_releases
from lupaxa.github_intel.checks.workflows import evaluate_workflows
from lupaxa.github_intel.config.loader import LoadedConfig
from lupaxa.github_intel.config.models import RepositorySpec
from lupaxa.github_intel.config.profiles import check_defaults, resolve_profile
from lupaxa.github_intel.github.client import FetchResult, GitHubClient
from lupaxa.github_intel.storage.database import Database, Document, StoredCheck
from lupaxa.github_intel.sync.summary import (
    ahead_count,
    codeql_reading,
    collection_count,
    dependabot_reading,
    issue_count,
    latest_published,
    latest_tag,
    workflow_definitions,
)

__all__ = [
    "SyncReport",
    "synchronise",
]


@dataclass
class SyncReport:
    """Repository outcomes and HTTP counters for one run."""

    repositories: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: bool = False
    auth_failed: bool = False
    requests: int = 0
    cache_hits: int = 0
    not_modified: int = 0
    elapsed: float = 0.0
    failures: list[str] = field(default_factory=list)
    check_failures: int = 0
    latest: str = ""
    rate_pauses: int = 0
    rate_wait: float = 0.0
    on_progress: Callable[[SyncReport], None] | None = field(default=None, repr=False)


async def synchronise(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    *,
    force: bool,
    selected: tuple[RepositorySpec, ...],
    on_progress: Callable[[SyncReport], None] | None = None,
) -> SyncReport:
    """
    Refresh stale categories for the selected repositories.

    Args:
        loaded: Validated configuration.
        database: Cache.
        client: GitHub client.
        force: Ignore freshness windows.
        selected: Enabled repositories to visit. Order in this tuple is ignored.
        on_progress: Called as counters change. It must not await.

    Returns:
        Run statistics. Cancelled runs keep rows already written.

    """

    ordered = tuple(sorted(selected, key=lambda item: item.repo.casefold()))
    report = SyncReport(repositories=len(ordered))
    report.on_progress = on_progress

    def waiting(seconds: float) -> None:
        report.rate_wait = seconds
        report.rate_pauses = client.rate_pauses
        _notify(report)

    client.watch_rate_limit(waiting)
    _notify(report)
    lock = asyncio.Lock()
    pending = list(ordered)

    async def worker() -> None:
        while True:
            async with lock:
                if not pending:
                    return
                repository = pending.pop(0)
                report.latest = repository.repo
            _notify(report)
            await _sync_one(
                loaded,
                database,
                client,
                repository,
                force,
                report,
                lock,
            )

    width = min(client.concurrency, len(ordered))
    tasks = [asyncio.create_task(worker()) for _ in range(width)]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        report.cancelled = True
        current = asyncio.current_task()
        if current is not None:
            while current.uncancel():
                pass
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return report


async def _sync_one(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    repository: RepositorySpec,
    force: bool,
    report: SyncReport,
    lock: asyncio.Lock,
) -> None:
    try:
        checks = await _refresh(
            loaded,
            database,
            client,
            repository,
            force,
            report,
            lock,
        )
        await _store_checks(database, repository.repo, checks, report, lock)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        async with lock:
            report.failed += 1
            report.failures.append(f"{repository.repo}: {exc}")
        _notify(report)


async def _refresh(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    repository: RepositorySpec,
    force: bool,
    report: SyncReport,
    lock: asyncio.Lock,
) -> list[CheckResult]:
    resolved = resolve_profile(
        loaded.profiles,
        repository.profile or loaded.config.defaults.profile,
        repository.checks,
        **check_defaults(loaded.config.defaults),
    )
    metadata = await _category(
        database,
        client,
        repository.repo,
        "metadata",
        f"/repos/{repository.repo}",
        loaded.config.sync.cache.metadata_ttl,
        force,
        loaded.config.sync.cache.enabled,
        report,
        lock,
    )
    meta = _mapping(metadata)
    checks: list[CheckResult] = []
    if resolved.enabled["releases"]:
        checks.append(
            await _releases(
                loaded, database, client, repository, meta, force, report, lock
            ),
        )
    workflow_states: list[dict[str, str]] | None = None
    workflow_headline = "No workflows"
    if resolved.enabled["workflows"]:
        workflow_states = await _workflow_inventory(
            client,
            repository.repo,
            report,
            lock,
        )
        result = evaluate_workflows(
            workflow_states,
            None if workflow_states is not None else "Could not list workflows.",
        )
        checks.append(result)
        workflow_headline = result.status
    await _summary(
        loaded,
        database,
        client,
        repository,
        meta,
        metadata,
        force,
        report,
        lock,
        workflow_headline,
        workflow_states,
        resolved.enabled["pull_requests"],
        resolved.enabled["quality"],
        resolved.enabled["issues"],
    )
    return checks


async def _releases(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    repository: RepositorySpec,
    meta: dict[str, Any],
    force: bool,
    report: SyncReport,
    lock: asyncio.Lock,
) -> CheckResult:
    repo = repository.repo
    ttl = loaded.config.sync.cache.releases_ttl
    enabled = loaded.config.sync.cache.enabled
    releases = await _category(
        database,
        client,
        repo,
        "releases",
        f"/repos/{repo}/releases",
        ttl,
        force,
        enabled,
        report,
        lock,
        params={"per_page": "20"},
    )
    branch = str(meta.get("default_branch") or "HEAD")
    published = [
        item
        for item in _list(releases)
        if isinstance(
            item,
            dict,
        )
        and not item.get("draft")
    ]
    tag = str(published[0].get("tag_name")) if published else ""
    compare: Document | None = None
    if tag:
        quoted = quote(tag, safe="")
        compare = await _category(
            database,
            client,
            repo,
            f"compare:{tag}",
            f"/repos/{repo}/compare/{quoted}...{quote(branch, safe='')}",
            ttl,
            force,
            enabled,
            report,
            lock,
        )
    return evaluate_releases(
        _list(releases) if releases and releases.error is None else None,
        compare_status=_compare_status(compare),
        ahead_by=_ahead_by(compare),
        compare_error=None
        if compare is None or compare.error is None
        else compare.error,
        fetch_error=None if releases is None else releases.error,
    )


async def _summary(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    repository: RepositorySpec,
    meta: dict[str, Any],
    metadata: Document | None,
    force: bool,
    report: SyncReport,
    lock: asyncio.Lock,
    workflow: str,
    workflows: list[dict[str, str]] | None,
    fetch_pulls: bool,
    fetch_quality: bool,
    count_issues: bool,
) -> None:
    repo = repository.repo
    current = await database.get(repo, "summary")
    fresh = _fresh(
        current,
        loaded.config.sync.cache.issues_ttl,
        force,
        loaded.config.sync.cache.enabled,
    )
    if fresh:
        async with lock:
            report.cache_hits += 1
        _notify(report)
        return
    if metadata is not None and metadata.error and "404" in metadata.error:
        await _save_summary(database, repo, _empty_summary())
        return
    pulls = None
    if fetch_pulls:
        pulls = await _counted(
            client,
            report,
            lock,
            f"/repos/{repo}/pulls",
            {"state": "open", "per_page": "1"},
        )
    alerts = None
    if fetch_quality:
        alerts = await _counted(
            client,
            report,
            lock,
            f"/repos/{repo}/code-scanning/alerts",
            {"tool_name": "CodeQL", "state": "open", "per_page": "1"},
        )
    dependencies = await _counted(
        client,
        report,
        lock,
        f"/repos/{repo}/dependabot/alerts",
        {"state": "open", "per_page": "1"},
    )
    open_pulls = (
        None
        if pulls is None
        else collection_count(
            body=pulls.body,
            link=pulls.link,
            failed=pulls.error is not None,
        )
    )
    if alerts is None:
        codeql, codeql_reason = None, ""
    else:
        codeql, codeql_reason = codeql_reading(
            status=alerts.status,
            error=alerts.error,
            body=alerts.body,
            link=alerts.link,
        )
    dependency_count, dependency_reason = dependabot_reading(
        status=dependencies.status,
        error=dependencies.error,
        body=dependencies.body,
        link=dependencies.link,
    )
    release_body = await _release_body(
        database,
        client,
        repo,
        report,
        lock,
    )
    version = latest_tag(release_body)
    branch = str(meta.get("default_branch") or "HEAD")
    ahead = await _ahead(
        database,
        client,
        repo,
        version,
        branch,
        report,
        lock,
    )
    await _save_summary(
        database,
        repo,
        {
            "version": version,
            "open_pulls": open_pulls,
            "open_issues": (
                issue_count(meta.get("open_issues_count")) if count_issues else None
            ),
            "codeql": codeql if fetch_quality else None,
            "codeql_reason": codeql_reason if fetch_quality else "",
            "release_date": latest_published(release_body),
            "ahead": ahead,
            "workflow": workflow,
            "workflows": workflows,
            "dependencies": dependency_count,
            "dependencies_reason": dependency_reason,
        },
    )


async def _counted(
    client: GitHubClient,
    report: SyncReport,
    lock: asyncio.Lock,
    path: str,
    params: dict[str, str],
) -> FetchResult:
    result = await client.get(path, params=params)
    async with lock:
        report.requests += 1
        report.rate_pauses = client.rate_pauses
        if result.status == 401:
            report.auth_failed = True
    _notify(report)
    return result


async def _release_body(
    database: Database,
    client: GitHubClient,
    repo: str,
    report: SyncReport,
    lock: asyncio.Lock,
) -> object:
    releases = await database.get(repo, "releases")
    if releases is not None and releases.error is None:
        return releases.json_body()
    fetched = await _counted(
        client,
        report,
        lock,
        f"/repos/{repo}/releases",
        {"per_page": "20"},
    )
    if fetched.error is not None:
        return []
    return fetched.body


async def _ahead(
    database: Database,
    client: GitHubClient,
    repo: str,
    tag: str,
    branch: str,
    report: SyncReport,
    lock: asyncio.Lock,
) -> int | None:
    if not tag:
        return None
    compare = await database.get(repo, f"compare:{tag}")
    if compare is not None and compare.error is None:
        return ahead_count(compare.json_body())
    quoted = quote(tag, safe="")
    head = quote(branch, safe="")
    fetched = await _counted(
        client,
        report,
        lock,
        f"/repos/{repo}/compare/{quoted}...{head}",
        {},
    )
    if fetched.error is not None:
        return None
    return ahead_count(fetched.body)


async def _workflow_inventory(
    client: GitHubClient,
    repo: str,
    report: SyncReport,
    lock: asyncio.Lock,
) -> list[dict[str, str]] | None:
    fetched = await _counted(
        client,
        report,
        lock,
        f"/repos/{repo}/actions/workflows",
        {"per_page": "100"},
    )
    if fetched.error is not None:
        return None
    return [
        {"name": name, "status": state}
        for name, state in workflow_definitions(_page_items(fetched.body, "workflows"))
    ]


def _page_items(body: object, key: str) -> list[object]:
    if not isinstance(body, dict):
        return []
    batch = body.get(key)
    if not isinstance(batch, list):
        return []
    return batch


def _empty_summary() -> dict[str, object]:
    return {
        "version": "",
        "open_pulls": None,
        "open_issues": None,
        "codeql": None,
        "codeql_reason": "",
        "release_date": "",
        "ahead": None,
        "workflow": "No workflows",
        "workflows": [],
        "dependencies": None,
        "dependencies_reason": "",
    }


async def _save_summary(
    database: Database,
    repo: str,
    body: dict[str, object],
) -> None:
    await database.save(
        repo,
        "summary",
        body=body,
        etag=None,
        error=None,
        keep_body=False,
    )


async def _category(
    database: Database,
    client: GitHubClient,
    repo: str,
    category: str,
    path: str,
    ttl: int,
    force: bool,
    cache_enabled: bool,
    report: SyncReport,
    lock: asyncio.Lock,
    params: dict[str, str] | None = None,
) -> Document | None:
    current = await database.get(repo, category)
    if _fresh(current, ttl, force, cache_enabled):
        async with lock:
            report.cache_hits += 1
        _notify(report)
        return current
    result = await client.get(
        path,
        etag=None if current is None else current.etag,
        params=params,
    )
    async with lock:
        report.requests += 1
        report.rate_pauses = client.rate_pauses
        if result.status == 401:
            report.auth_failed = True
        if result.not_modified:
            report.not_modified += 1
    _notify(report)
    await _store_fetch(database, repo, category, current, result)
    return await database.get(repo, category)


async def _store_fetch(
    database: Database,
    repo: str,
    category: str,
    current: Document | None,
    result: FetchResult,
) -> None:
    if result.not_modified and current is not None:
        await database.save(
            repo,
            category,
            etag=result.etag,
            error=None,
            keep_body=True,
        )
        return
    if result.error:
        await database.save(
            repo,
            category,
            body=None if current is None else current.json_body(),
            etag=result.etag,
            error=result.error,
            keep_body=False,
        )
        return
    await database.save(
        repo,
        category,
        body=result.body,
        etag=result.etag,
        error=None,
        keep_body=False,
    )


async def _store_checks(
    database: Database,
    repo: str,
    checks: list[CheckResult],
    report: SyncReport,
    lock: asyncio.Lock,
) -> None:
    moment = time.time()
    rows = [
        StoredCheck(repo, item.name, item.status, item.summary, item.failure, moment)
        for item in checks
    ]
    await database.save_checks(repo, rows)
    async with lock:
        report.successful += 1
        report.check_failures += sum(1 for item in checks if item.failure)
    _notify(report)


def _notify(report: SyncReport) -> None:
    if report.on_progress is not None:
        report.on_progress(report)


def _fresh(document: Document | None, ttl: int, force: bool, enabled: bool) -> bool:
    if force or not enabled or document is None or document.fetched_at is None:
        return False
    return time.time() - document.fetched_at < ttl


def _mapping(document: Document | None) -> dict[str, Any]:
    if document is None or document.error:
        return {}
    body = document.json_body()
    return body if isinstance(body, dict) else {}


def _list(document: Document | None) -> list[Any]:
    if document is None or document.error:
        return []
    body = document.json_body()
    return body if isinstance(body, list) else []


def _compare_status(document: Document | None) -> str | None:
    status = _mapping(document).get("status")
    return status if isinstance(status, str) else None


def _ahead_by(document: Document | None) -> int | None:
    value = _mapping(document).get("ahead_by")
    return value if isinstance(value, int) else None
