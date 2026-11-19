"""List columns filled from cached GitHub summaries."""

from __future__ import annotations

import asyncio
from pathlib import Path
import time

import httpx

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.config.models import RepositorySpec
from lupaxa.github_intel.storage.database import Document, StoredCheck
from lupaxa.github_intel.sync.summary import collection_count, issue_count, latest_tag
from lupaxa.github_intel.views import (
    _headline,
    _last_push,
    _release_label,
    detail_rows,
    split_identifier,
    status_style,
)


def test_missing_release_is_not_hidden_by_a_standards_failure() -> None:
    metadata = Document(
        "acme/demo",
        "metadata",
        "{}",
        None,
        time.time(),
        None,
    )
    checks = [
        StoredCheck(
            "acme/demo",
            "standards:licence",
            "FAIL",
            "No licence file was found.",
            True,
            0,
        ),
        StoredCheck(
            "acme/demo",
            "releases",
            "No releases",
            "No published releases found.",
            False,
            0,
        ),
    ]
    assert _headline(RepositorySpec(repo="acme/demo"), metadata, checks) == (
        "No releases"
    )


def test_status_colours_match_the_outcome() -> None:
    assert status_style("Current") == "green"
    assert status_style("3 Ahead") == "yellow"
    assert status_style("3 Ahead — 3 commits after v1.") == "yellow"
    assert status_style("No releases") == "yellow"
    assert status_style("FAIL") == "red"
    assert status_style("Unavailable") == "red"
    assert status_style("SKIPPED — Issue checks are disabled.") == "dim"
    assert status_style("ActionsToolbox") == ""


def test_cached_unreleased_status_shows_the_commit_count() -> None:
    assert _release_label("Unreleased changes", 4) == "4 Ahead"
    assert _release_label("Current", 0) == "Current"


def test_last_push_is_blank_when_nothing_has_been_pushed() -> None:
    assert _last_push({"pushed_at": "2026-11-18T22:12:59Z", "size": 0}) == ""
    assert _last_push({"pushed_at": "2026-11-01T12:00:00Z", "size": 4}) == "2026-11-01"


def test_split_identifier_separates_org_and_repo() -> None:
    assert split_identifier("lupaxa-gh-toolbox/github-intel") == (
        "lupaxa-gh-toolbox",
        "github-intel",
    )


def test_latest_tag_skips_drafts() -> None:
    body = [{"tag_name": "v2", "draft": True}, {"tag_name": "v1", "draft": False}]
    assert latest_tag(body) == "v1"
    assert latest_tag([]) == ""


def test_collection_count_uses_the_last_page() -> None:
    link = '<https://example.test/pulls?per_page=1&page=4>; rel="last"'
    assert collection_count(body=[{}], link=link, failed=False) == 4
    assert collection_count(body=[], link=None, failed=False) == 0
    assert collection_count(body=None, link=None, failed=True) is None


def test_issue_count_excludes_pull_requests() -> None:
    assert issue_count(6, 4) == 2
    assert issue_count(6, None) is None


def test_sync_stores_version_pulls_issues_and_codeql(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/good", None, "upstream", [])

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/releases"):
            return httpx.Response(
                200,
                json=[
                    {
                        "tag_name": "v1.2.0",
                        "draft": False,
                        "published_at": "2026-10-01T00:00:00Z",
                    }
                ],
            )
        if "/compare/" in path:
            return httpx.Response(200, json={"status": "ahead", "ahead_by": 3})
        if path.endswith("/pulls"):
            link = '<https://example.test/pulls?per_page=1&page=4>; rel="last"'
            return httpx.Response(200, json=[{}], headers={"link": link})
        if path.endswith("/code-scanning/alerts"):
            return httpx.Response(403, json={"message": "no access"})
        if path.endswith("/dependabot/alerts"):
            return httpx.Response(404, json={"message": "no alerts"})
        if "/actions/" in path:
            message = f"unexpected actions request: {path}"
            raise AssertionError(message)
        payload = {
            "full_name": "acme/good",
            "description": "Demo",
            "default_branch": "main",
            "open_issues_count": 6,
            "visibility": "public",
            "archived": False,
            "pushed_at": "2026-11-01T12:00:00Z",
            "size": 4,
            "stargazers_count": 12,
            "license": {"spdx_id": "MIT"},
        }
        return httpx.Response(200, json=payload)

    service.transport = httpx.MockTransport(handler)
    asyncio.run(service.sync())
    view = asyncio.run(service.views())[0]
    assert view.version == "v1.2.0"
    assert view.open_pulls == 4
    assert view.open_issues is None
    assert view.codeql == 0
    assert view.last_push == "2026-11-01"
    assert view.stars == 12
    assert view.visibility == "public"
    assert view.archived is False
    assert view.licence == "MIT"
    assert view.release_date == "2026-10-01"
    assert view.ahead == 3
    assert view.workflows is None
    assert dict(detail_rows(view))["Workflow"] == (
        "SKIPPED — Workflow checks are disabled."
    )
    assert dict(detail_rows(view))["Issues"] == ("SKIPPED — Issue checks are disabled.")
    labels = [field for field, _ in detail_rows(view)]
    assert "Org" in labels
    assert "Check releases" not in labels
    assert view.status == "3 Ahead"
    assert dict(detail_rows(view))["Status"].startswith("3 Ahead — ")
    assert view.dependencies == 0


def test_workflow_sync_reads_the_latest_run_only(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/good", None, "maintained", [])
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.url.path}?{request.url.query.decode()}")
        path = request.url.path
        if path.endswith("/actions/workflows"):
            return httpx.Response(
                200,
                json={
                    "total_count": 2,
                    "workflows": [
                        {"id": 1, "name": "CI"},
                        {"id": 2, "name": "Release"},
                    ],
                },
            )
        if path.endswith("/actions/runs"):
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "workflow_id": 1,
                            "status": "completed",
                            "conclusion": "success",
                            "created_at": "2026-11-02T00:00:00Z",
                        }
                    ]
                },
            )
        if path.endswith("/workflows/1/runs"):
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "status": "completed",
                            "conclusion": "success",
                            "created_at": "2026-11-02T00:00:00Z",
                        }
                    ]
                },
            )
        if path.endswith("/workflows/2/runs"):
            return httpx.Response(200, json={"workflow_runs": []})
        if path.endswith("/releases"):
            return httpx.Response(200, json=[])
        if "page=2" in request.url.query.decode():
            message = f"unexpected extra page: {request.url}"
            raise AssertionError(message)
        return httpx.Response(
            200,
            json={"full_name": "acme/good", "default_branch": "main", "size": 1},
        )

    service.transport = httpx.MockTransport(handler)
    asyncio.run(service.sync())
    action_calls = [item for item in calls if "/actions/" in item]
    assert action_calls == [
        "/repos/acme/good/actions/workflows?per_page=100",
        "/repos/acme/good/actions/runs?per_page=100&branch=main",
        "/repos/acme/good/actions/workflows/2/runs?per_page=1&branch=main",
    ]
    view = asyncio.run(service.views())[0]
    assert view.workflows == (("CI", "Success"), ("Release", "Never run"))
