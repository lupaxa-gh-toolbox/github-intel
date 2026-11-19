"""Terminal interface against cached configuration."""

from __future__ import annotations

from pathlib import Path

from textual.widgets import DataTable, Static

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.tui.application import IntelTui, RepoDetail


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
        assert "Dependencies" in fields
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
