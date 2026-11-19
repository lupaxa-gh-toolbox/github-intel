"""Configured date formatting."""

from datetime import UTC, datetime

from pydantic import ValidationError
import pytest

from lupaxa.github_intel.config.models import AppConfig
from lupaxa.github_intel.dates import format_date, format_timestamp, normalize_instant


def test_default_date_format_includes_the_clock() -> None:
    config = AppConfig.model_validate({"version": 1})
    assert config.display.date_format == "DD/MM/YYYY HH:mm UTC"
    assert (
        format_date("2026-11-18T23:06:41Z", config.display.date_format)
        == "18/11/2026 23:06 UTC"
    )


def test_date_format_accepts_another_token_order() -> None:
    config = AppConfig.model_validate(
        {"version": 1, "display": {"date_format": "yyyy-mm-dd hh:mm"}},
    )
    assert config.display.date_format == "YYYY-MM-DD HH:mm"
    assert format_date("2026-11-18T23:06:41+01:00", config.display.date_format) == (
        "2026-11-18 22:06"
    )


def test_date_format_can_include_seconds() -> None:
    config = AppConfig.model_validate(
        {"version": 1, "display": {"date_format": "DD/MM/YYYY HH:MM:SS"}},
    )
    assert config.display.date_format == "DD/MM/YYYY HH:mm:ss"
    assert format_date("2026-11-18T23:06:41Z", config.display.date_format) == (
        "18/11/2026 23:06:41"
    )


def test_date_format_can_omit_the_clock() -> None:
    config = AppConfig.model_validate(
        {"version": 1, "display": {"date_format": "DD/MM/YYYY"}},
    )
    assert config.display.date_format == "DD/MM/YYYY"
    assert format_date("2026-11-18T23:06:41Z", config.display.date_format) == (
        "18/11/2026"
    )


def test_date_format_rejects_an_incomplete_pattern() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {"version": 1, "display": {"date_format": "DD/MM/YY"}},
        )
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {"version": 1, "display": {"date_format": "DD/MM/YYYY HH"}},
        )


def test_a_date_without_a_clock_leaves_the_time_blank() -> None:
    assert format_date("2026-11-18", "DD/MM/YYYY HH:mm UTC") == "18/11/2026 --:-- UTC"


def test_timestamp_uses_the_date_pattern() -> None:
    moment = datetime(2026, 11, 18, 23, 6, tzinfo=UTC)
    assert format_timestamp(moment.timestamp(), "DD/MM/YYYY HH:mm UTC") == (
        "18/11/2026 23:06 UTC"
    )


def test_normalize_instant_keeps_the_clock_in_utc() -> None:
    assert normalize_instant("2026-11-18T23:06:41+01:00") == "2026-11-18T22:06:41Z"
    assert normalize_instant("2026-11-18") == "2026-11-18"
    assert normalize_instant("later") == ""
