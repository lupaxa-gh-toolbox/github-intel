"""Check evaluation."""

from __future__ import annotations

from lupaxa.github_intel.checks.releases import evaluate_releases


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
