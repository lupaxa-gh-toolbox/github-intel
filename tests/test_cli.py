"""CLI help, version, and JSON output."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path
import re
import time

from typer.testing import CliRunner

from lupaxa.github_intel.cli import app, syncing as real_syncing
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.constants import (
    EXIT_CONFIG,
    EXIT_SUCCESS,
    EXIT_SYNC,
    PROGRAM_VERSION_STRING,
)
from lupaxa.github_intel.storage.database import Database

runner = CliRunner()
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return _ANSI.sub("", text)


def test_sync_ctrl_c_exits_without_a_traceback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = write_default_files(tmp_path / "config")
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(tmp_path / "data"))

    def interrupt(coro: object) -> None:
        close = getattr(coro, "close", None)
        if close is not None:
            close()
        raise KeyboardInterrupt

    monkeypatch.setattr("lupaxa.github_intel.cli.asyncio.run", interrupt)
    result = runner.invoke(app, ["--config", str(config), "sync"])
    assert result.exit_code == EXIT_SYNC
    assert "Synchronisation cancelled." in result.stderr
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


def test_sync_too_soon_prints_before_the_progress_bar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = write_default_files(tmp_path / "config")
    text = config.read_text(encoding="utf-8")
    config.write_text(
        text.replace("interval: 0\n", "interval: 3600\n"),
        encoding="utf-8",
    )
    data = tmp_path / "data"
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(data))

    async def seed() -> None:
        database = Database(data / "cache.sqlite")
        now = time.time()
        await database.record_run(now, now, {})
        await database.close()

    asyncio.run(seed())
    entered = False

    @contextmanager
    def watching():
        nonlocal entered
        entered = True
        with real_syncing() as callback:
            yield callback

    monkeypatch.setattr("lupaxa.github_intel.cli.syncing", watching)
    result = runner.invoke(app, ["--config", str(config), "sync"])
    error = _plain(result.stderr)
    assert result.exit_code == EXIT_CONFIG
    assert not entered
    assert "Synchronising" not in error
    assert "Synchronisation is too soon." in error
    assert "\nWait " in error


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    output = _plain(result.stdout)
    assert result.exit_code == EXIT_SUCCESS
    assert "github-intel" in output
    assert "--version" in output


def test_version_exits_zero() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == EXIT_SUCCESS
    assert PROGRAM_VERSION_STRING in result.stdout


def test_list_json_contains_only_data(tmp_path: Path, monkeypatch) -> None:
    config = write_default_files(tmp_path / "config")
    repositories = config.parent / "repositories.yml"
    repositories.write_text("repositories:\n  - acme/demo\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(tmp_path / "data"))
    result = runner.invoke(
        app,
        ["--config", str(config), "repo", "list", "--format", "json"],
    )
    assert result.exit_code == EXIT_SUCCESS
    assert result.stdout.startswith("[\n")
    assert "acme/demo" in result.stdout
    assert "Repositories" not in result.stdout
