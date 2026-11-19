"""Repository file edits."""

from __future__ import annotations

from pathlib import Path

import pytest

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.errors import ConfigError


def test_add_preserves_comments_and_rejects_duplicates(tmp_path: Path) -> None:
    config = write_default_files(tmp_path)
    repositories = tmp_path / "repositories.yml"
    repositories.write_text(
        "# keep me\nrepositories:\n  - acme/demo\n",
        encoding="utf-8",
    )
    service = Service(config, tmp_path / "data", token_provider=lambda: None)
    service.add("acme/other", "third-party", "watchlist", ["python"])
    text = repositories.read_text(encoding="utf-8")
    assert "# keep me" in text
    assert "acme/other" in text
    with pytest.raises(ConfigError, match="already configured"):
        service.add("ACME/DEMO", None, None, [])
