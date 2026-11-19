"""Synchronisation against a fake GitHub API."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.github.rate_limit import RateLimitController
from lupaxa.github_intel.present import _status_line
from lupaxa.github_intel.sync.engine import SyncReport


def _metadata(name: str) -> dict[str, object]:
    return {
        "full_name": name,
        "description": "Demo",
        "default_branch": "main",
        "visibility": "public",
        "archived": False,
        "fork": False,
        "stargazers_count": 1,
        "forks_count": 0,
        "open_issues_count": 0,
        "html_url": f"https://github.com/{name}",
        "topics": [],
        "license": None,
    }


def test_sync_keeps_going_when_one_repository_is_missing(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/good", None, "upstream", [])
    service.add("acme/missing", None, "upstream", [])
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.startswith("/repos/acme/missing"):
            return httpx.Response(404, json={"message": "Not Found"})
        if request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_metadata("acme/good"))

    service.transport = httpx.MockTransport(handler)
    report = asyncio.run(service.sync())
    assert report.successful == 2
    assert report.failed == 0
    assert any(path.startswith("/repos/acme/good") for path in seen)
    views = asyncio.run(service.views())
    by_name = {view.repo: view for view in views}
    assert by_name["acme/missing"].status == "Unavailable"
    assert by_name["acme/good"].status == "No releases"


def test_concurrency_is_bounded(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: "token-value")
    for index in range(6):
        service.add(f"acme/repo-{index}", None, "base", [])
    state = {"current": 0, "max": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        state["current"] += 1
        state["max"] = max(state["max"], state["current"])
        await asyncio.sleep(0.02)
        state["current"] -= 1
        name = request.url.path.split("/")[2] + "/" + request.url.path.split("/")[3]
        if request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_metadata(name))

    service.transport = httpx.MockTransport(handler)
    report = asyncio.run(service.sync(concurrency=2))
    assert report.successful == 6
    assert state["max"] <= 2


def test_second_sync_uses_the_cache(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/good", None, "upstream", [])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_metadata("acme/good"))

    service.transport = httpx.MockTransport(handler)
    first = asyncio.run(service.sync())
    second = asyncio.run(service.sync())
    assert first.requests > 0
    assert second.requests == 0
    assert second.cache_hits > 0


def test_sync_visits_repositories_in_list_order(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("gamma/b", None, "upstream", [])
    service.add("alpha/z", None, "upstream", [])
    service.add("gamma/a", None, "upstream", [])
    started: list[str] = []

    def on_progress(report: SyncReport) -> None:
        if report.latest and (not started or started[-1] != report.latest):
            started.append(report.latest)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[])
        name = request.url.path.removeprefix("/repos/")
        return httpx.Response(200, json=_metadata(name))

    service.transport = httpx.MockTransport(handler)
    report = asyncio.run(service.sync(concurrency=1, on_progress=on_progress))
    assert report.successful == 3
    assert started == ["alpha/z", "gamma/a", "gamma/b"]


def test_cancelling_during_a_rate_limit_wait_stops(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/good", None, "upstream", [])
    waiting = asyncio.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"retry-after": "3600"},
            json={"message": "rate limit"},
        )

    def on_progress(report: SyncReport) -> None:
        if report.rate_wait > 0:
            waiting.set()

    service.transport = httpx.MockTransport(handler)

    async def run() -> SyncReport:
        task = asyncio.create_task(service.sync(concurrency=1, on_progress=on_progress))
        await asyncio.wait_for(waiting.wait(), timeout=2)
        task.cancel()
        return await task

    report = asyncio.run(run())
    assert report.cancelled
    assert report.successful == 0


def test_sync_reports_progress_while_repositories_finish(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/good", None, "upstream", [])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_metadata("acme/good"))

    service.transport = httpx.MockTransport(handler)
    seen: list[int] = []

    def on_progress(report: SyncReport) -> None:
        seen.append(report.successful + report.failed)

    report = asyncio.run(service.sync(on_progress=on_progress))
    assert report.successful == 1
    assert seen[0] == 0
    assert seen[-1] == 1


def test_status_line_names_the_repository() -> None:
    report = SyncReport(
        repositories=4,
        successful=1,
        requests=3,
        cache_hits=2,
        latest="acme/good",
        rate_pauses=1,
    )
    text = _status_line(report)
    assert "acme/good  1/4" in text
    assert "requests 3" in text
    assert "cache 2" in text
    assert "rate limit pauses 1" in text
    report.rate_wait = 65
    assert "requests resume in 1m 05s" in _status_line(report)


def test_rate_limit_wait_reports_the_time_remaining() -> None:
    now = {"t": 0.0}
    seen: list[float] = []

    async def sleeper(delay: float) -> None:
        now["t"] += delay

    limits = RateLimitController(clock=lambda: now["t"], sleeper=sleeper)
    limits.set_listener(seen.append)
    limits.observe(429, {"retry-after": "2.5"})
    asyncio.run(limits.wait())
    assert seen[0] == 2.5
    assert seen[-1] == 0.0
    assert limits.pauses == 1
