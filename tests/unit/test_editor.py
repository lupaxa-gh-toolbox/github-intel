"""Repository file edits."""

from __future__ import annotations

from pathlib import Path

import pytest

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.errors import ConfigError


def test_owner_settings_apply_to_each_repository(tmp_path: Path) -> None:
    config = write_default_files(tmp_path)
    (tmp_path / "repositories.yml").write_text(
        "\n".join(
            (
                "organisations:",
                "  - name: acme",
                "    group: Examples",
                "    profile: upstream",
                "    repositories:",
                "      - demo",
                "      - name: special",
                "        profile: watchlist",
                "        enabled: false",
            )
        ),
        encoding="utf-8",
    )
    loaded = Service(config, tmp_path / "data", token_provider=lambda: None).load()
    rows = {item.repo: item for item in loaded.repositories}
    assert rows["acme/demo"].group == "Examples"
    assert rows["acme/demo"].profile == "upstream"
    assert rows["acme/special"].group == "Examples"
    assert rows["acme/special"].profile == "watchlist"
    assert rows["acme/special"].enabled is False


def test_add_preserves_comments_and_rejects_duplicates(tmp_path: Path) -> None:
    config = write_default_files(tmp_path)
    repositories = tmp_path / "repositories.yml"
    repositories.write_text(
        "# keep me\norganisations:\n  - name: acme\n    repositories:\n      - demo\n",
        encoding="utf-8",
    )
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/other", "third-party", "watchlist", ["python"])
    text = repositories.read_text(encoding="utf-8")
    assert "# keep me" in text
    assert "name: other" in text
    assert "watchlist" in text
    with pytest.raises(ConfigError, match="already configured"):
        service.add("ACME/DEMO", None, None, [])
