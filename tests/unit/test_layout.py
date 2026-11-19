"""Named list and detail layouts."""

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import pytest
from rich.console import Console
from rich.text import Text

from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.config.loader import load_config
from lupaxa.github_intel.config.models import AppConfig, ViewSettings
from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT
from lupaxa.github_intel.errors import ConfigError
from lupaxa.github_intel.layout import hardcoded_list, resolve_layout, view_names
from lupaxa.github_intel.reports.render import render_report
from lupaxa.github_intel.views import RepositoryView, detail_rows, field_text


def _config(display: dict[str, object] | None = None) -> AppConfig:
    document: dict[str, object] = {"version": 1}
    if display is not None:
        document["display"] = display
    return AppConfig.model_validate(document)


def test_shipped_template_declares_the_default_view(tmp_path: Path) -> None:
    config_path = write_default_files(tmp_path)
    loaded = load_config(config_path)
    assert loaded.config.display.view == "default"
    popularity = loaded.config.display.views["popularity"]
    assert popularity.list == (
        "Organisation",
        "Repository",
        "Stars",
        "Watchers",
        "Forks",
    )
    assert popularity.detail is None
    layout = resolve_layout(loaded.config.display, "default", [])
    assert layout.list_fields == hardcoded_list([])
    chosen = resolve_layout(loaded.config.display, "popularity", [])
    assert chosen.list_fields == popularity.list
    lines = config_path.read_text(encoding="utf-8").splitlines()
    assert "  view: default" in lines
    assert "    popularity:" in lines


def test_omitted_views_keep_the_hardcoded_names() -> None:
    config = _config()
    assert config.display.view == "default"
    assert config.display.views == {}
    layout = resolve_layout(config.display, "default", [])
    assert layout.list_fields == hardcoded_list([])
    assert layout.list_fields == (
        "Organisation",
        "Repository",
        "Visibility",
        "Language",
        "Status",
        "Version",
        "Release date",
        "Enabled",
    )
    assert layout.detail_fields is None


def test_default_entry_can_replace_one_side() -> None:
    config = _config(
        {
            "views": {
                "default": {"list": ["repository", "Status"]},
            },
        },
    )
    layout = resolve_layout(config.display, "default", [])
    assert layout.list_fields == ("Repository", "Status")
    assert layout.detail_fields is None
    detail_only = _config({"views": {"default": {"detail": ["Workflows"]}}})
    layout = resolve_layout(detail_only.display, "default", [])
    assert layout.list_fields == hardcoded_list([])
    assert layout.detail_fields == ("Workflows",)


def test_saved_view_name_is_resolved_without_a_flag() -> None:
    config = _config(
        {
            "view": "compact",
            "views": {"compact": {"list": ["Version"], "detail": ["Status"]}},
        },
    )
    layout = resolve_layout(config.display, config.display.view, [])
    assert layout.list_fields == ("Version",)
    assert layout.detail_fields == ("Status",)


def test_invalid_views_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _config({"views": {"compact": {"list": ["Nope"]}}})
    with pytest.raises(ValidationError):
        _config({"views": {"compact": {"list": ["Status", "status"]}}})
    with pytest.raises(ValidationError):
        _config({"views": {"compact": {"list": []}}})
    with pytest.raises(ValidationError):
        _config({"views": {"compact": {}}})
    with pytest.raises(ValidationError):
        _config({"views": {"compact": {"list": ["Metadata error"]}}})
    with pytest.raises(ValidationError):
        _config({"view": "missing"})


def test_unknown_runtime_view_is_a_config_error() -> None:
    config = _config()
    with pytest.raises(ConfigError, match="Unknown view: compact"):
        resolve_layout(config.display, "compact", [])


def test_view_settings_accepts_tuple_and_round_trips() -> None:
    view = ViewSettings(list=("Status",))
    assert view.list == ("Status",)
    assert ViewSettings.model_validate(view.model_dump()) == view


def test_padded_view_keys_are_stored_stripped() -> None:
    config = _config(
        {
            "view": " compact ",
            "views": {
                " default": {"list": ["Repository"]},
                "compact": {"list": ["Version"]},
            },
        },
    )
    assert " default" not in config.display.views
    assert config.display.views["default"].list == ("Repository",)
    assert config.display.view == "compact"
    layout = resolve_layout(config.display, "default", [])
    assert layout.list_fields == ("Repository",)
    layout = resolve_layout(config.display, config.display.view, [])
    assert layout.list_fields == ("Version",)


def test_duplicate_view_names_after_strip_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _config(
            {
                "views": {
                    " default": {"list": ["Status"]},
                    "default": {"list": ["Version"]},
                },
            },
        )


def test_view_names_put_default_first() -> None:
    config = _config(
        {
            "views": {
                "zeta": {"list": ["Status"]},
                "alpha": {"detail": ["Status"]},
            },
        },
    )
    assert view_names(config.display) == ("default", "alpha", "zeta")


def _view(**overrides: Any) -> RepositoryView:
    view = RepositoryView(
        repo="acme/demo",
        group="",
        profile="",
        tags=(),
        enabled=False,
        description="",
        visibility="",
        status="",
        statuses=(),
        updated_at=None,
        checks=(),
        metadata_error="boom",
        version="",
        open_pulls=None,
        open_issues=None,
        codeql=None,
        codeql_reason="",
        archived=False,
        last_push="",
        default_branch="",
        homepage="",
        language="",
        topics=(),
        fork=False,
        forks=None,
        watchers=None,
        created="",
        github_updated="",
        size=None,
        stars=None,
        licence="",
        release_date="",
        ahead=None,
        workflow="",
        workflows=None,
        workflows_enabled=False,
        issues_enabled=False,
        pull_requests_enabled=False,
        quality_enabled=False,
        dependencies=None,
        dependencies_reason="",
    )
    if not overrides:
        return view
    return replace(view, **overrides)


@pytest.fixture
def view() -> RepositoryView:
    return _view()


def test_detail_selection_keeps_the_error_first(view: RepositoryView) -> None:
    rows = detail_rows(view, fields=("Status", "Repository"))
    assert rows[0] == ("Metadata error", "boom")
    assert rows[1][0] == "Status"
    assert rows[2] == ("Repository", "demo")
    assert "Checks" not in {label for label, _value in rows}
    full = detail_rows(view)
    assert "Dependabot Alerts" in {label for label, _value in full}
    assert full[-1] == ("Checks", "Not synchronised")


def test_blank_error_is_omitted(view: RepositoryView) -> None:
    quiet = replace(view, metadata_error=None)
    labels = [label for label, _value in detail_rows(quiet, fields=("Status",))]
    assert labels == ["Status"]


def test_list_cells_are_blank_when_the_check_is_off(view: RepositoryView) -> None:
    assert field_text(view, "Issues", "DD/MM/YYYY", detail=False) == ""
    assert field_text(view, "Issues", "DD/MM/YYYY", detail=True).startswith(
        "SKIPPED — ",
    )
    assert field_text(view, "Workflows", "DD/MM/YYYY", detail=False) == (
        "SKIPPED — Workflow checks are disabled."
    )


def test_repository_name_is_red_when_metadata_failed(view: RepositoryView) -> None:
    from lupaxa.github_intel.present import list_row

    painted = list_row(view, ("Repository",), DEFAULT_DATE_FORMAT)[0]
    assert isinstance(painted, Text)
    assert str(painted.style) == "red"
    assert painted.plain == "demo"
    plain = list_row(
        replace(view, metadata_error=None),
        ("Repository",),
        DEFAULT_DATE_FORMAT,
    )[0]
    assert plain == "demo"


def test_disabled_workflows_cell_ignores_the_cached_list(
    view: RepositoryView,
) -> None:
    from lupaxa.github_intel.present import list_row

    off = replace(
        view,
        workflows_enabled=False,
        workflows=(("lint", "success"),),
    )
    painted = list_row(off, ("Workflows",), DEFAULT_DATE_FORMAT)[0]
    plain = painted.plain if isinstance(painted, Text) else painted
    assert plain == "SKIPPED — Workflow checks are disabled."
    assert "lint" not in plain


def test_failed_workflows_cell_shows_the_error_not_the_cached_list(
    view: RepositoryView,
) -> None:
    from lupaxa.github_intel.present import list_row
    from lupaxa.github_intel.storage.database import StoredCheck

    failed = replace(
        view,
        workflows_enabled=True,
        workflows=(("lint", "success"),),
        checks=(
            StoredCheck(
                "acme/demo",
                "workflows",
                "Error",
                "Could not list workflows.",
                True,
                0,
            ),
        ),
    )
    painted = list_row(failed, ("Workflows",), DEFAULT_DATE_FORMAT)[0]
    plain = painted.plain if isinstance(painted, Text) else painted
    assert plain == "Error — Could not list workflows."
    assert "lint" not in plain


def test_healthy_workflows_cell_stays_the_coloured_table(
    view: RepositoryView,
) -> None:
    from lupaxa.github_intel.present import list_row

    listed = replace(
        view,
        workflows_enabled=True,
        workflows=(("lint", "success"), ("release", "failure")),
    )
    painted = list_row(listed, ("Workflows",), DEFAULT_DATE_FORMAT)[0]
    assert isinstance(painted, Text)
    assert painted.plain == field_text(
        listed,
        "Workflows",
        DEFAULT_DATE_FORMAT,
        detail=False,
    )
    assert "\n" in painted.plain
    assert any(span.style for span in painted.spans)


def test_list_status_is_the_short_word_and_detail_is_the_sentence(
    view: RepositoryView,
) -> None:
    from lupaxa.github_intel.present import _present_cell, list_row
    from lupaxa.github_intel.storage.database import StoredCheck

    current = replace(
        view,
        status="Current",
        metadata_error="",
        checks=(
            StoredCheck(
                "acme/demo",
                "releases",
                "Current",
                "v1 has no newer commits on the default branch.",
                False,
                0,
            ),
        ),
    )
    assert field_text(current, "Status", DEFAULT_DATE_FORMAT, detail=False) == "Current"
    sentence = "v1 has no newer commits on the default branch."
    assert field_text(current, "Status", DEFAULT_DATE_FORMAT, detail=True) == sentence
    assert dict(detail_rows(current))["Status"] == sentence
    assert "Check releases" not in dict(detail_rows(current))
    painted = list_row(current, ("Status",), DEFAULT_DATE_FORMAT)[0]
    assert isinstance(painted, Text)
    assert painted.plain == "Current"
    assert str(painted.style) == "green"
    detail = _present_cell("Status", sentence, current)
    assert isinstance(detail, Text)
    assert detail.plain == sentence
    assert str(detail.style) == "green"


def _style(cell: str | Text) -> str:
    if isinstance(cell, Text):
        return str(cell.style)
    return ""


def test_list_and_detail_use_the_same_colours(view: RepositoryView) -> None:
    from lupaxa.github_intel.present import _present_cell, list_row, repo_title

    shown = replace(
        view,
        metadata_error="",
        enabled=True,
        visibility="private",
        archived=True,
        fork=True,
        ahead=3,
        quality_enabled=True,
        codeql=0,
        codeql_reason="",
        dependencies=4,
        statuses=("cached", "stale"),
        status="Current",
    )
    expected = {
        "Enabled": "green",
        "Visibility": "magenta",
        "Archived": "yellow",
        "Fork": "cyan",
        "Ahead": "yellow",
        "Quality": "green",
        "Dependabot Alerts": "yellow",
        "Cache": "yellow",
        "Status": "green",
    }
    for label, colour in expected.items():
        listed = list_row(shown, (label,), DEFAULT_DATE_FORMAT)[0]
        detail_text = field_text(shown, label, DEFAULT_DATE_FORMAT, detail=True)
        detail = _present_cell(label, detail_text, shown)
        assert _style(listed) == colour
        assert _style(detail) == colour
    disabled = replace(shown, enabled=False, codeql=None, codeql_reason="No scanning")
    enabled = list_row(disabled, ("Enabled",), DEFAULT_DATE_FORMAT)[0]
    enabled_detail = field_text(disabled, "Enabled", DEFAULT_DATE_FORMAT, detail=True)
    assert _style(enabled) == "dim"
    assert _style(_present_cell("Enabled", enabled_detail, disabled)) == "dim"
    scanning = field_text(disabled, "Quality", DEFAULT_DATE_FORMAT, detail=False)
    assert _style(_present_cell("Quality", scanning, disabled)) == "dim"
    failed = replace(view, metadata_error="boom", status="Error")
    repository = list_row(failed, ("Repository",), DEFAULT_DATE_FORMAT)[0]
    assert isinstance(repository, Text)
    assert repository.plain == "demo"
    assert str(repository.style) == "red"
    error = _present_cell("Metadata error", "boom", failed)
    assert isinstance(error, Text)
    assert str(error.style) == "red"
    title = repo_title(failed)
    assert isinstance(title, Text)
    assert title.plain == "acme/demo"
    assert str(title.style) == "red"


def test_a_differing_releases_check_keeps_its_own_detail_row(
    view: RepositoryView,
) -> None:
    from lupaxa.github_intel.storage.database import StoredCheck

    errored = replace(
        view,
        status="Error",
        checks=(
            StoredCheck("acme/demo", "releases", "Current", "Up to date.", False, 0),
        ),
    )
    rows = detail_rows(errored)
    labels = [label for label, _value in rows]
    assert labels.count("Status") == 1
    shown = dict(rows)
    assert shown["Status"] == "Error"
    assert shown["Check releases"] == "Current — Up to date."


def test_custom_fields_set_headers_and_right_align_stars(
    view: RepositoryView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lupaxa.github_intel.present import print_repos

    shown = replace(view, stars=3)
    console = Console(record=True, width=120, force_terminal=False)
    monkeypatch.setattr(
        "lupaxa.github_intel.present.stdout_console",
        lambda: console,
    )
    print_repos([shown], fields=("Workflows", "Stars"))
    text = console.export_text()
    header = next(
        line for line in text.splitlines() if "Workflows" in line and "Stars" in line
    )
    assert header.index("Workflows") < header.index("Stars")
    assert "Organisation" not in text
    assert "    3" in text


def test_reports_use_the_resolved_labels_and_human_text() -> None:
    view = _view(repo="acme/demo", metadata_error="boom", description="Hello")
    fields = ("Repository", "Description")
    payload = json.loads(render_report([view], "json", fields=fields))
    assert list(payload[0]) == ["Repository", "Description"]
    assert payload[0]["Repository"] == "demo"
    shown = json.loads(
        render_report([view], "json", fields=("Status",), detail=True),
    )
    assert list(shown)[0] == "Metadata error"
    assert shown["Metadata error"] == "boom"
    csv_text = render_report([view], "csv", fields=fields)
    assert csv_text.splitlines()[0] == "Repository,Description"
    markdown = render_report([view], "markdown", fields=fields)
    assert markdown.startswith("# GitHub Intel Report\n")
    assert "| Repository | Description |" in markdown
    assert "| Updated |" not in markdown
    flows = _view(
        workflows_enabled=True,
        workflows=(("lint|job", "success"), ("release", "failure")),
    )
    raw = field_text(flows, "Workflows", DEFAULT_DATE_FORMAT, detail=False)
    assert "\n" in raw
    rendered = render_report([flows], "markdown", fields=("Workflows",))
    escaped = raw.replace("|", "\\|").replace("\n", "<br>")
    assert rendered.splitlines() == [
        "# GitHub Intel Report",
        "",
        "| Workflows |",
        "| --- |",
        f"| {escaped} |",
    ]
    assert json.loads(render_report([], "json", fields=fields, detail=True)) == {}
