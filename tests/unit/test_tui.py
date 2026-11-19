"""Terminal interface against cached configuration."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.widgets import DataTable, OptionList, Static

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.storage.database import Database
from lupaxa.github_intel.tui.application import IntelTui, RepoDetail, ViewPicker


async def test_tui_lists_and_filters_cached_repositories(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/demo", "third-party", "upstream", [])
    interface = IntelTui(service)
    async with interface.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        assert table.row_count == 1
        pilot.app.query_one("#search").focus()
        await pilot.press("z", "z")
        assert table.row_count == 0


async def test_tui_opens_repository_detail(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/demo", "third-party", "upstream", [])
    interface = IntelTui(service)
    async with interface.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one("#table", DataTable)
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(pilot.app.screen, RepoDetail)
        fields = [
            str(widget.content) for widget in pilot.app.screen.query(".detail-field")
        ]
        assert "Last push" in fields
        assert "Licence" in fields
        assert "Dependabot Alerts" in fields
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(pilot.app.screen, RepoDetail)


async def test_tui_explains_a_missing_configuration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("GITHUB_INTEL_CONFIG_DIR", str(tmp_path / "missing"))
    service = Service(None, tmp_path / "data", token_provider=lambda: None)
    interface = IntelTui(service)
    async with interface.run_test() as pilot:
        await pilot.pause()
        summary = str(pilot.app.query_one("#summary", Static).content)
        assert "Configuration could not be loaded." in summary
        assert "github-intel repo add owner/name" in summary
        assert "control + q" in summary
        assert "config.yml" in summary
        await pilot.press("r")
        await pilot.pause()
        summary = str(pilot.app.query_one("#summary", Static).content)
        assert "Configuration could not be loaded." in summary


async def test_tui_explains_a_missing_profiles_file(tmp_path: Path) -> None:
    config = write_default_files(tmp_path)
    (tmp_path / "profiles.yml").unlink()
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    interface = IntelTui(service)
    async with interface.run_test() as pilot:
        await pilot.pause()
        summary = str(pilot.app.query_one("#summary", Static).content)
        assert "profiles.yml" in summary
        assert "Configuration could not be loaded." in summary


def _column_labels(table: DataTable) -> list[str]:
    return [column.label.plain for column in table.columns.values()]


def _compact_list(config: Path) -> None:
    text = config.read_text(encoding="utf-8")
    original = (
        "display:\n  date_format: DD/MM/YYYY HH:mm UTC\n  view: default\n  views: {}\n"
    )
    replacement = (
        "display:\n"
        "  date_format: DD/MM/YYYY HH:mm UTC\n"
        "  view: default\n"
        "  views:\n"
        "    compact:\n"
        "      list:\n"
        "        - Repository\n"
        "        - Status\n"
    )
    assert original in text
    config.write_text(text.replace(original, replacement, 1), encoding="utf-8")


async def test_tui_switches_views(tmp_path: Path) -> None:
    config = write_default_files(tmp_path / "config")
    _compact_list(config)
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/demo", "third-party", "upstream", [])
    interface = IntelTui(service, view="compact")
    async with interface.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        assert len(table.columns) == 2
        assert _column_labels(table) == ["Repository", "Status"]
        await pilot.press("v")
        await pilot.pause()
        assert isinstance(pilot.app.screen, ViewPicker)
        options = pilot.app.screen.query_one(OptionList)
        assert str(options.get_option_at_index(0).prompt) == "default"
        await pilot.press("enter")
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        labels = _column_labels(table)
        assert len(table.columns) > 2
        assert "Organisation" in labels


async def test_tui_paints_repository_red_when_metadata_failed(
    tmp_path: Path,
) -> None:
    config = write_default_files(tmp_path / "config")
    data = tmp_path / "data"
    service = Service(config, data, token_provider=lambda: None)
    service.add("acme/demo", "third-party", "upstream", [])
    database = Database(data / "cache.sqlite")
    await database.save(
        "acme/demo",
        "metadata",
        body=None,
        etag=None,
        error="boom",
        keep_body=False,
    )
    await database.close()
    interface = IntelTui(service)
    async with interface.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        cell = table.get_row_at(0)[_column_labels(table).index("Repository")]
        assert isinstance(cell, Text)
        assert cell.plain == "demo"
        assert str(cell.style) == "red"
