"""CLI help, version, and JSON output."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import re
import time

from typer.testing import CliRunner

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.cli import app, syncing as real_syncing
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.constants import (
    EXIT_CONFIG,
    EXIT_SUCCESS,
    EXIT_SYNC,
    PROGRAM_VERSION_STRING,
)
from lupaxa.github_intel.storage.database import Database, StoredCheck

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


def test_reset_deletes_the_cache_and_keeps_configuration(
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
    (data / "cache.sqlite-wal").write_text("wal", encoding="utf-8")
    before = config.read_text(encoding="utf-8")
    result = runner.invoke(app, ["--config", str(config), "reset", "--yes"])
    assert result.exit_code == EXIT_SUCCESS
    assert _plain(result.stdout).startswith("Deleted ")
    assert not (data / "cache.sqlite").exists()
    assert not (data / "cache.sqlite-wal").exists()
    assert not (data / "cache.sqlite-shm").exists()
    assert config.read_text(encoding="utf-8") == before

    asyncio.run(Service(config, data).assert_sync_allowed(force=False))


def test_reset_keeps_the_cache_without_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = write_default_files(tmp_path / "config")
    data = tmp_path / "data"
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(data))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    async def seed() -> None:
        database = Database(data / "cache.sqlite")
        await database.open()
        await database.close()

    asyncio.run(seed())
    result = runner.invoke(app, ["--config", str(config), "reset"])
    assert result.exit_code == EXIT_CONFIG
    assert "Re-run with --yes." in _plain(result.stderr)
    assert (data / "cache.sqlite").is_file()


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
    repositories.write_text(
        "organisations:\n  - name: acme\n    repositories:\n      - demo\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(tmp_path / "data"))
    result = runner.invoke(
        app,
        ["--config", str(config), "repo", "list", "--format", "json"],
    )
    assert result.exit_code == EXIT_SUCCESS
    assert result.stdout.startswith("[\n")
    assert '"Organisation": "acme"' in result.stdout
    assert '"Repository": "demo"' in result.stdout
    assert "Repositories" not in result.stdout


def _display(config: Path, body: str) -> None:
    text = config.read_text(encoding="utf-8")
    needle = (
        "display:\n  date_format: DD/MM/YYYY HH:mm UTC\n  view: default\n  views: {}\n"
    )
    config.write_text(text.replace(needle, "display:\n" + body), encoding="utf-8")


def test_view_flag_selects_the_list(tmp_path: Path, monkeypatch) -> None:
    config = write_default_files(tmp_path / "config")
    _display(
        config,
        "  date_format: DD/MM/YYYY HH:mm UTC\n"
        "  view: default\n"
        "  views:\n"
        "    compact:\n"
        "      list:\n"
        "        - Repository\n"
        "        - Status\n",
    )
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(tmp_path / "data"))
    Service(config, tmp_path / "data").add("acme/demo", None, None, [])
    result = runner.invoke(
        app,
        [
            "--config",
            str(config),
            "repo",
            "list",
            "--format",
            "json",
            "--view",
            "compact",
        ],
    )
    assert result.exit_code == EXIT_SUCCESS
    assert list(json.loads(result.stdout)[0]) == ["Repository", "Status"]
    missing = runner.invoke(
        app,
        [
            "--config",
            str(config),
            "repo",
            "list",
            "--format",
            "json",
            "--view",
            "missing",
        ],
    )
    assert missing.exit_code == EXIT_CONFIG
    assert "Unknown view: missing" in _plain(missing.stderr)


def test_tui_view_flag_rejects_an_unknown_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = write_default_files(tmp_path / "config")
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(tmp_path / "data"))
    started: list[object] = []
    monkeypatch.setattr(
        "lupaxa.github_intel.cli.run_tui",
        lambda *args, **kwargs: started.append(args),
    )
    result = runner.invoke(
        app,
        ["--config", str(config), "tui", "--view", "missing"],
    )
    assert result.exit_code == EXIT_CONFIG
    assert "Unknown view: missing" in _plain(result.stderr)
    assert started == []
    known = runner.invoke(
        app,
        ["--config", str(config), "tui", "--view", "default"],
    )
    assert known.exit_code == EXIT_SUCCESS
    assert len(started) == 1


def test_repo_show_json_keeps_status_and_the_releases_check(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = write_default_files(tmp_path / "config")
    data = tmp_path / "data"
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(data))
    Service(config, data).add("acme/demo", None, None, [])

    async def seed() -> None:
        database = Database(data / "cache.sqlite")
        await database.save(
            "acme/demo",
            "metadata",
            body={},
            etag=None,
            error="boom",
            keep_body=False,
        )
        await database.save_checks(
            "acme/demo",
            [
                StoredCheck(
                    "acme/demo",
                    "releases",
                    "Current",
                    "Up to date.",
                    False,
                    0,
                ),
            ],
        )
        await database.close()

    asyncio.run(seed())
    result = runner.invoke(
        app,
        [
            "--config",
            str(config),
            "repo",
            "show",
            "acme",
            "demo",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == EXIT_SUCCESS
    payload = json.loads(result.stdout)
    assert payload["Status"] == "Error"
    assert payload["Check releases"] == "Current — Up to date."


def test_repo_show_json_uses_the_configured_detail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = write_default_files(tmp_path / "config")
    _display(
        config,
        "  date_format: DD/MM/YYYY HH:mm UTC\n"
        "  views:\n"
        "    default:\n"
        "      detail:\n"
        "        - Repository\n",
    )
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(tmp_path / "data"))
    Service(config, tmp_path / "data").add("acme/demo", None, None, [])
    result = runner.invoke(
        app,
        [
            "--config",
            str(config),
            "repo",
            "show",
            "acme",
            "demo",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == EXIT_SUCCESS
    payload = json.loads(result.stdout)
    assert list(payload) == ["Repository"]
    assert payload["Repository"] == "demo"


def test_repo_show_json_and_csv_keep_hardcoded_checks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = write_default_files(tmp_path / "config")
    monkeypatch.setenv("GITHUB_INTEL_DATA_DIR", str(tmp_path / "data"))
    Service(config, tmp_path / "data").add("acme/demo", None, None, [])
    result = runner.invoke(
        app,
        [
            "--config",
            str(config),
            "repo",
            "show",
            "acme",
            "demo",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == EXIT_SUCCESS
    payload = json.loads(result.stdout)
    assert payload["Repository"] == "demo"
    assert payload["Checks"] == "Not synchronised"
    csv_result = runner.invoke(
        app,
        [
            "--config",
            str(config),
            "repo",
            "show",
            "acme",
            "demo",
            "--format",
            "csv",
        ],
    )
    assert csv_result.exit_code == EXIT_SUCCESS
    header = csv_result.stdout.splitlines()[0].split(",")
    assert "Repository" in header
    assert "Checks" in header


def test_config_init_writes_defaults_and_force_replaces_them(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("GITHUB_INTEL_CONFIG_DIR", str(tmp_path / "config"))
    created = runner.invoke(app, ["config", "init"])
    assert created.exit_code == EXIT_SUCCESS
    directory = tmp_path / "config"
    config = directory / "config.yml"
    profiles = directory / "profiles.yml"
    repositories = directory / "repositories.yml"
    assert "version: 1" in config.read_text(encoding="utf-8")
    assert "upstream:" in profiles.read_text(encoding="utf-8")
    assert repositories.read_text(encoding="utf-8") == "organisations: []\n"
    assert config.stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700
    repositories.write_text("organisations:\n  - name: octocat\n", encoding="utf-8")
    kept = runner.invoke(app, ["config", "init"])
    assert kept.exit_code == EXIT_CONFIG
    assert "octocat" in repositories.read_text(encoding="utf-8")
    assert "Use --force to overwrite." in _plain(kept.stdout)
    replaced = runner.invoke(app, ["config", "init", "--force"])
    assert replaced.exit_code == EXIT_SUCCESS
    assert repositories.read_text(encoding="utf-8") == "organisations: []\n"


def test_config_init_writes_a_missing_file_and_keeps_the_others(tmp_path: Path) -> None:
    config = tmp_path / "custom.yml"
    result = runner.invoke(app, ["--config", str(config), "config", "init"])
    assert result.exit_code == EXIT_SUCCESS
    assert config.is_file()
    assert (tmp_path / "profiles.yml").is_file()
    (tmp_path / "profiles.yml").unlink()
    config.write_text("version: 1\n", encoding="utf-8")
    again = runner.invoke(app, ["--config", str(config), "config", "init"])
    assert again.exit_code == EXIT_SUCCESS
    assert config.read_text(encoding="utf-8") == "version: 1\n"
    assert "upstream:" in (tmp_path / "profiles.yml").read_text(encoding="utf-8")
    assert "Kept" in _plain(again.stdout)
