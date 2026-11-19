"""Check evaluation."""

from __future__ import annotations

from lupaxa.github_intel.checks.issues import issue_records
from lupaxa.github_intel.checks.releases import evaluate_releases
from lupaxa.github_intel.checks.standards import evaluate_standards, tree_statuses
from lupaxa.github_intel.config.models import StandardsSettings


def test_release_ahead_is_unreleased() -> None:
    result = evaluate_releases(
        [{"tag_name": "v1", "draft": False}],
        compare_status="ahead",
        ahead_by=2,
        compare_error=None,
        fetch_error=None,
    )
    assert result.status == "2 Ahead"
    assert result.failure is False


def test_diverged_release_is_unknown() -> None:
    result = evaluate_releases(
        [{"tag_name": "v1", "draft": False}],
        compare_status="diverged",
        ahead_by=3,
        compare_error=None,
        fetch_error=None,
    )
    assert result.status == "Unknown"


def test_pull_requests_are_not_issues() -> None:
    records = issue_records([{"number": 1}, {"number": 2, "pull_request": {}}])
    assert [item["number"] for item in records] == [1]


def test_one_git_tree_answers_every_standards_path() -> None:
    body = {
        "tree": [
            {"path": "README.md", "type": "blob"},
            {"path": ".github/workflows/ci.yml", "type": "blob"},
        ],
    }
    statuses = tree_statuses(
        body,
        ("README.md", "README.rst", ".github/workflows", "LICENCE"),
    )
    assert statuses == {
        "README.md": 200,
        "README.rst": 404,
        ".github/workflows": 200,
        "LICENCE": 404,
    }
    assert tree_statuses({"truncated": True, "tree": []}, ("README.md",)) is None


def test_missing_readme_fails_and_api_error_does_not() -> None:
    settings = StandardsSettings(readme=True, licence=False, gitignore=False)
    missing = evaluate_standards(
        settings,
        {"README.md": 404, "README.rst": 404, "README.txt": 404, "README": 404},
    )
    readme = next(item for item in missing if item.name == "standards:readme")
    assert readme.status == "FAIL"
    errored = evaluate_standards(
        settings,
        {"README.md": None, "README.rst": None, "README.txt": None, "README": None},
    )
    readme_error = next(item for item in errored if item.name == "standards:readme")
    assert readme_error.status == "ERROR"
