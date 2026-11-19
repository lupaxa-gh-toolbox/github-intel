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
from lupaxa.github_intel.checks.issues import evaluate_issues, issue_records
from lupaxa.github_intel.checks.releases import evaluate_releases
from lupaxa.github_intel.checks.security import evaluate_security
from lupaxa.github_intel.checks.standards import (
    STANDARD_PATHS,
    evaluate_standards,
    tree_statuses,
)
from lupaxa.github_intel.checks.workflows import evaluate_workflows
from lupaxa.github_intel.config.loader import LoadedConfig
from lupaxa.github_intel.config.models import RepositorySpec, StandardsSettings
from lupaxa.github_intel.config.profiles import resolve_profile
from lupaxa.github_intel.github.client import FetchResult, GitHubClient
from lupaxa.github_intel.storage.database import Database, Document, StoredCheck
from lupaxa.github_intel.sync.summary import (
    ahead_count,
    collection_count,
    issue_count,
    latest_published,
    latest_tag,
    newest_run,
    run_state,
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
        loaded.config.defaults.standards,
        issues=loaded.config.defaults.issues,
        pull_requests=loaded.config.defaults.pull_requests,
        quality=loaded.config.defaults.quality,
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
    workflow_headline = "Never run"
    if resolved.enabled["workflows"]:
        workflow_states, newest = await _workflow_inventory(
            client,
            repository.repo,
            str(meta.get("default_branch") or ""),
            report,
            lock,
        )
        if workflow_states is None:
            checks.append(evaluate_workflows(None, "Could not list workflows."))
            workflow_headline = "Unknown"
        else:
            latest = [newest] if newest is not None else []
            checks.append(evaluate_workflows(latest, None))
            workflow_headline = run_state(newest)
    if resolved.enabled["issues"]:
        checks.append(
            await _issues(loaded, database, client, repository, force, report, lock),
        )
    if resolved.enabled["standards"]:
        checks.extend(
            await _standards(
                loaded,
                database,
                client,
                repository,
                str(meta.get("default_branch") or "HEAD"),
                force,
                report,
                lock,
                resolved.standards,
            ),
        )
    checks.append(evaluate_security(enabled=resolved.enabled["security"]))
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
        resolved.enabled["pull_requests"] or resolved.enabled["issues"],
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


async def _issues(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    repository: RepositorySpec,
    force: bool,
    report: SyncReport,
    lock: asyncio.Lock,
) -> CheckResult:
    document = await _category(
        database,
        client,
        repository.repo,
        "issues",
        f"/repos/{repository.repo}/issues",
        loaded.config.sync.cache.issues_ttl,
        force,
        loaded.config.sync.cache.enabled,
        report,
        lock,
        params={"state": "open", "per_page": "30", "sort": "updated"},
    )
    records = issue_records(
        _list(document) if document and document.error is None else None,
    )
    total = None if document is None or document.error else len(records)
    return evaluate_issues(total, None if document is None else document.error)


async def _standards(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    repository: RepositorySpec,
    branch: str,
    force: bool,
    report: SyncReport,
    lock: asyncio.Lock,
    rules: StandardsSettings,
) -> list[CheckResult]:
    enabled_rules = {name for name, enabled in rules.model_dump().items() if enabled}
    wanted = tuple(
        path
        for name, group in STANDARD_PATHS.items()
        if name in enabled_rules
        for path in group
    )
    statuses = await _standard_statuses(
        loaded,
        database,
        client,
        repository.repo,
        branch,
        wanted,
        force,
        report,
        lock,
    )
    return evaluate_standards(rules, statuses)


async def _standard_statuses(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    repo: str,
    branch: str,
    wanted: tuple[str, ...],
    force: bool,
    report: SyncReport,
    lock: asyncio.Lock,
) -> dict[str, int | None]:
    quoted = quote(branch or "HEAD", safe="")
    document = await _category(
        database,
        client,
        repo,
        f"git-tree:{branch or 'HEAD'}",
        f"/repos/{repo}/git/trees/{quoted}",
        loaded.config.sync.cache.standards_ttl,
        force,
        loaded.config.sync.cache.enabled,
        report,
        lock,
        params={"recursive": "1"},
    )
    if document is not None and document.error:
        if "404" in document.error or "409" in document.error:
            return dict.fromkeys(wanted, 404)
        return dict.fromkeys(wanted)
    body = None if document is None else document.json_body()
    found = tree_statuses(body, wanted)
    if found is not None:
        return found
    return await _content_statuses(
        loaded,
        database,
        client,
        repo,
        wanted,
        force,
        report,
        lock,
    )


async def _content_statuses(
    loaded: LoadedConfig,
    database: Database,
    client: GitHubClient,
    repo: str,
    wanted: tuple[str, ...],
    force: bool,
    report: SyncReport,
    lock: asyncio.Lock,
) -> dict[str, int | None]:
    statuses: dict[str, int | None] = {}
    for _name, paths in STANDARD_PATHS.items():
        if not any(path in wanted for path in paths):
            continue
        for path in paths:
            if path not in wanted:
                continue
            document = await _category(
                database,
                client,
                repo,
                f"contents:{path}",
                f"/repos/{repo}/contents/{quote(path, safe='')}",
                loaded.config.sync.cache.standards_ttl,
                force,
                loaded.config.sync.cache.enabled,
                report,
                lock,
            )
            status = _content_status(document)
            statuses[path] = status
            if status == 200:
                break
    return statuses


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
    codeql = (
        None
        if alerts is None
        else collection_count(
            body=alerts.body,
            link=alerts.link,
            failed=alerts.error is not None,
        )
    )
    dependency_count = collection_count(
        body=dependencies.body,
        link=dependencies.link,
        failed=dependencies.error is not None,
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
                issue_count(meta.get("open_issues_count"), open_pulls)
                if count_issues
                else None
            ),
            "codeql": _stored_quality(fetch_quality, codeql),
            "release_date": latest_published(release_body),
            "ahead": ahead,
            "workflow": workflow,
            "workflows": workflows,
            "dependencies": 0 if dependency_count is None else dependency_count,
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
    branch: str,
    report: SyncReport,
    lock: asyncio.Lock,
) -> tuple[list[dict[str, str]] | None, dict[str, Any] | None]:
    fetched = await _counted(
        client,
        report,
        lock,
        f"/repos/{repo}/actions/workflows",
        {"per_page": "100"},
    )
    if fetched.error is not None:
        return None, None
    names = workflow_definitions(_page_items(fetched.body, "workflows"))
    branch_params: dict[str, str] = {}
    if branch and branch != "HEAD":
        branch_params["branch"] = branch
    listed = await _counted(
        client,
        report,
        lock,
        f"/repos/{repo}/actions/runs",
        {"per_page": "100", **branch_params},
    )
    known: dict[int, dict[str, object]] = {}
    if listed.error is None:
        known = newest_run(_page_items(listed.body, "workflow_runs"))
    states: list[dict[str, str]] = []
    runs: list[dict[str, Any]] = []
    for workflow_id, name in names:
        seen = known.get(workflow_id)
        if seen is not None:
            states.append({"name": name, "status": run_state(seen)})
            runs.append(seen)
            continue
        one = await _counted(
            client,
            report,
            lock,
            f"/repos/{repo}/actions/workflows/{workflow_id}/runs",
            {"per_page": "1", **branch_params},
        )
        if one.error is not None:
            states.append({"name": name, "status": "Unknown"})
            continue
        found = _page_items(one.body, "workflow_runs")
        run = found[0] if found and isinstance(found[0], dict) else None
        states.append({"name": name, "status": run_state(run)})
        if run is not None:
            runs.append(run)
    states.sort(key=lambda item: item["name"].casefold())
    newest = max(runs, key=_run_stamp) if runs else None
    return states, newest


def _run_stamp(run: dict[str, Any]) -> str:
    for key in ("run_started_at", "created_at", "updated_at"):
        value = run.get(key)
        if isinstance(value, str):
            return value
    return ""


def _page_items(body: object, key: str) -> list[object]:
    if not isinstance(body, dict):
        return []
    batch = body.get(key)
    if not isinstance(batch, list):
        return []
    return batch


def _stored_quality(enabled: bool, count: int | None) -> int | None:
    if not enabled:
        return None
    return 0 if count is None else count


def _empty_summary() -> dict[str, object]:
    return {
        "version": "",
        "open_pulls": None,
        "open_issues": None,
        "codeql": 0,
        "release_date": "",
        "ahead": None,
        "workflow": "Never run",
        "workflows": [],
        "dependencies": 0,
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


def _content_status(document: Document | None) -> int | None:
    if document is None or document.error is None:
        return 200 if document is not None else None
    if "404" in document.error:
        return 404
    return None
