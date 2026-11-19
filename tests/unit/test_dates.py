"""Configured date formatting."""

from datetime import UTC, datetime

from pydantic import ValidationError
import pytest

from lupaxa.github_intel.config.models import AppConfig
from lupaxa.github_intel.dates import format_date, format_timestamp


def test_default_date_format_is_day_month_year() -> None:
    config = AppConfig.model_validate({"version": 1})
    assert config.display.date_format == "DD/MM/YYYY"
    assert format_date("2026-11-18", config.display.date_format) == "18/11/2026"


def test_date_format_accepts_another_token_order() -> None:
    config = AppConfig.model_validate(
        {"version": 1, "display": {"date_format": "yyyy-mm-dd"}},
    )
    assert config.display.date_format == "YYYY-MM-DD"
    assert format_date("2026-11-18", config.display.date_format) == "2026-11-18"


def test_date_format_rejects_an_incomplete_pattern() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {"version": 1, "display": {"date_format": "DD/MM/YY"}},
        )


def test_timestamp_uses_the_date_pattern() -> None:
    moment = datetime(2026, 11, 18, 23, 6, tzinfo=UTC)
    assert format_timestamp(moment.timestamp(), "DD/MM/YYYY") == "18/11/2026 23:06 UTC"
