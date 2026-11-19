"""List columns filled from cached GitHub summaries."""

from __future__ import annotations

import asyncio
from pathlib import Path
import time

import httpx
from rich.text import Text

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.config.models import RepositorySpec
from lupaxa.github_intel.storage.database import Document, StoredCheck
from lupaxa.github_intel.sync.summary import (
    codeql_reading,
    collection_count,
    dependabot_reading,
    issue_count,
    latest_tag,
    workflow_activity,
)
from lupaxa.github_intel.views import (
    _headline,
    _last_push,
    _release_label,
    _shown_checks,
    detail_rows,
    field_text,
    metric_cells,
    quality_text,
    split_identifier,
    status_style,
    visibility_text,
    workflow_text,
)


def test_missing_release_is_not_hidden_by_another_failure() -> None:
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
            "workflows",
            "Error",
            "Could not list workflows.",
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


def test_stored_file_and_issue_checks_are_hidden() -> None:
    checks = [
        StoredCheck("acme/demo", "standards:readme", "FAIL", "Missing.", True, 0),
        StoredCheck("acme/demo", "issues", "Open", "2 open issues.", False, 0),
        StoredCheck("acme/demo", "security", "SKIPPED", "Not implemented.", False, 0),
        StoredCheck("acme/demo", "releases", "Current", "Up to date.", False, 0),
    ]
    assert [item.name for item in _shown_checks(checks)] == ["releases"]


def test_status_colours_match_the_outcome() -> None:
    assert status_style("Current") == "green"
    assert status_style("Active") == "green"
    assert status_style("Disabled") == "dim"
    assert status_style("Manually Disabled") == "dim"
    assert status_style("Inactivity Disabled") == "dim"
    assert status_style("3 Ahead") == "yellow"
    assert status_style("3 Ahead — 3 commits after v1.") == "yellow"
    assert status_style("No releases") == "cyan"
    assert status_style("No releases — No published releases found.") == "cyan"
    assert status_style("FAIL") == "red"
    assert status_style("Unavailable") == "red"
    assert status_style("SKIPPED — Issue checks are disabled.") == "dim"
    assert status_style("ActionsToolbox") == ""
    public = visibility_text("public")
    private = visibility_text("private")
    internal = visibility_text("internal")
    assert isinstance(public, Text)
    assert isinstance(private, Text)
    assert isinstance(internal, Text)
    assert str(public.style) == "green"
    assert str(private.style) == "magenta"
    assert str(internal.style) == "cyan"


def test_cached_unreleased_status_shows_the_commit_count() -> None:
    assert _release_label("Unreleased changes", 4) == "4 Ahead"
    assert _release_label("Current", 0) == "Current"


def test_last_push_is_blank_when_nothing_has_been_pushed() -> None:
    assert _last_push({"pushed_at": "2026-11-18T22:12:59Z", "size": 0}) == ""
    assert _last_push({"pushed_at": "2026-11-01T12:00:00Z", "size": 4}) == (
        "2026-11-01T12:00:00Z"
    )


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


def test_workflow_statuses_use_the_state_colour() -> None:
    text = workflow_text(
        (("CI", "Active"), ("Release", "Manually Disabled"), ("Nightly", "Unknown")),
    )
    coloured = {
        text.plain[span.start : span.end]: str(span.style) for span in text.spans
    }
    assert coloured["Active"] == "green"
    assert coloured["Manually Disabled"] == "dim"
    assert coloured["Unknown"] == "yellow"


def test_workflow_states_stay_distinct() -> None:
    assert workflow_activity("active") == "Active"
    assert workflow_activity("disabled_manually") == "Manually Disabled"
    assert workflow_activity("disabled_inactivity") == "Inactivity Disabled"
    assert workflow_activity("disabled_fork") == "Fork Disabled"
    assert workflow_activity("") == "Unknown"
    assert workflow_activity("deleted") == "Deleted"


def test_issue_count_keeps_githubs_total() -> None:
    assert issue_count(6) == 6
    assert issue_count(True) is None


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
            "homepage": "https://example.com",
            "language": "Python",
            "topics": ["release", "docs"],
            "fork": False,
            "forks_count": 2,
            "subscribers_count": 5,
            "created_at": "2020-11-01T00:00:00Z",
            "updated_at": "2026-11-02T00:00:00Z",
        }
        return httpx.Response(200, json=payload)

    service.transport = httpx.MockTransport(handler)
    asyncio.run(service.sync())
    view = asyncio.run(service.views())[0]
    assert view.version == "v1.2.0"
    assert view.open_pulls == 4
    assert view.open_issues is None
    assert view.codeql is None
    assert view.codeql_reason == "Forbidden"
    assert quality_text(view.quality_enabled, view.codeql, view.codeql_reason) == (
        "Forbidden"
    )
    assert metric_cells(view, ("Quality",)) == ("Forbidden",)
    assert dict(detail_rows(view))["Quality"] == "Forbidden"
    assert view.last_push == "2026-11-01T12:00:00Z"
    assert view.default_branch == "main"
    assert dict(detail_rows(view))["Default branch"] == "main"
    shown = dict(detail_rows(view))
    assert shown["Homepage"] == "https://example.com"
    assert shown["Language"] == "Python"
    assert shown["Topics"] == "release, docs"
    assert shown["Fork"] == "no"
    assert shown["Forks"] == "2"
    assert shown["Watchers"] == "5"
    assert shown["Created"] == "01/11/2020 00:00 UTC"
    assert shown["Updated"] == "02/11/2026 00:00 UTC"
    assert shown["Size"] == "4 KB"
    assert shown["Enabled"] == "yes"
    assert "cached" in shown["Cache"]
    assert view.stars == 12
    assert view.visibility == "public"
    assert view.archived is False
    assert view.licence == "MIT"
    assert view.release_date == "2026-10-01T00:00:00Z"
    assert view.ahead == 3
    assert view.workflows is None
    assert dict(detail_rows(view))["Workflows"] == (
        "SKIPPED — Workflow checks are disabled."
    )
    assert dict(detail_rows(view))["Issues"] == ("SKIPPED — Issue checks are disabled.")
    labels = [field for field, _ in detail_rows(view)]
    assert "Organisation" in labels
    assert "Repository" in labels
    assert "Check releases" not in labels
    assert view.status == "3 Ahead"
    assert field_text(view, "Status", "DD/MM/YYYY", detail=False) == "3 Ahead"
    sentence = "3 commits ahead on the default branch after v1.2.0."
    assert field_text(view, "Status", "DD/MM/YYYY", detail=True) == sentence
    assert dict(detail_rows(view))["Status"] == sentence
    assert view.dependencies is None
    assert view.dependencies_reason == "Forbidden"
    assert dict(detail_rows(view))["Dependabot Alerts"] == "Forbidden"


def test_codeql_reading_names_why_the_count_is_missing() -> None:
    assert codeql_reading(
        status=404,
        error="GitHub returned 404. The repository may be missing or not visible.",
        body=None,
        link=None,
    ) == (None, "No scanning")
    assert codeql_reading(
        status=403,
        error="GitHub returned 403: Code scanning is not enabled for this repository.",
        body=None,
        link=None,
    ) == (None, "No scanning")
    assert codeql_reading(
        status=403,
        error=(
            "GitHub returned 403: Code Security must be enabled "
            "for this repository to use code scanning."
        ),
        body=None,
        link=None,
    ) == (None, "No scanning")
    assert codeql_reading(
        status=403,
        error="GitHub returned 403: no access",
        body=None,
        link=None,
    ) == (None, "Forbidden")
    assert codeql_reading(
        status=0,
        error="Network request failed.",
        body=None,
        link=None,
    ) == (None, "Unknown")
    assert codeql_reading(status=200, error=None, body=[], link=None) == (0, "")


def test_dependabot_reading_names_why_the_count_is_missing() -> None:
    disabled = (
        "GitHub returned 403: Dependabot alerts are disabled for this repository."
    )
    assert dependabot_reading(
        status=403,
        error=disabled,
        body=None,
        link=None,
    ) == (None, "Disabled")
    assert dependabot_reading(
        status=403,
        error="GitHub returned 403: Resource not accessible by personal access token",
        body=None,
        link=None,
    ) == (None, "Forbidden")
    assert dependabot_reading(
        status=404,
        error="GitHub returned 404. The repository may be missing or not visible.",
        body=None,
        link=None,
    ) == (None, "Forbidden")
    assert dependabot_reading(
        status=0,
        error="Network request failed.",
        body=None,
        link=None,
    ) == (None, "Unknown")
    assert dependabot_reading(status=200, error=None, body=[], link=None) == (0, "")


def test_codeql_empty_page_is_zero(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/clean", None, "upstream", [])

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/code-scanning/alerts"):
            return httpx.Response(200, json=[])
        if path.endswith(("/releases", "/pulls", "/dependabot/alerts")):
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={"full_name": "acme/clean", "default_branch": "main"},
        )

    service.transport = httpx.MockTransport(handler)
    asyncio.run(service.sync())
    view = asyncio.run(service.views())[0]
    assert view.codeql == 0
    assert quality_text(view.quality_enabled, view.codeql) == "0"


def test_workflow_sync_lists_workflows_without_reading_runs(tmp_path: Path) -> None:
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
                        {"id": 1, "name": "CI", "state": "active"},
                        {"id": 2, "name": "Release", "state": "disabled_manually"},
                    ],
                },
            )
        if "/actions/runs" in path or path.endswith("/runs"):
            message = f"workflow runs are not requested: {request.url}"
            raise AssertionError(message)
        if path.endswith("/issues") or "/git/" in path or "/contents/" in path:
            message = f"files and the issues page are not requested: {request.url}"
            raise AssertionError(message)
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
    ]
    view = asyncio.run(service.views())[0]
    assert view.workflows == (
        ("CI", "Active"),
        ("Release", "Manually Disabled"),
    )
    assert dict(detail_rows(view))["Workflows"] == (
        "CI       Active\nRelease  Manually Disabled"
    )
    labels = [field for field, _value in detail_rows(view)]
    assert labels.count("Workflows") == 1
    assert "Workflow summary" not in labels
    assert "Metadata error" not in labels
    assert "Workflow CI" not in labels
