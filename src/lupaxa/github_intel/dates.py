"""Date patterns used by tables and reports."""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = [
    "DEFAULT_DATE_FORMAT",
    "format_date",
    "format_timestamp",
    "require_date_format",
]

DEFAULT_DATE_FORMAT = "DD/MM/YYYY"
_TOKENS = ("YYYY", "MM", "DD")


def require_date_format(value: str) -> str:
    """
    Accept a date pattern built from ``DD``, ``MM``, and ``YYYY``.

    Args:
        value: Configured pattern, such as ``DD/MM/YYYY``.

    Returns:
        The pattern with those tokens in upper case.

    Raises:
        ValueError: A token is missing, repeated, or mixed with letters.

    """

    text = value.strip().upper()
    if any(text.count(token) != 1 for token in _TOKENS):
        message = "display.date_format must contain DD, MM, and YYYY once each."
        raise ValueError(message)
    remainder = text
    for token in _TOKENS:
        remainder = remainder.replace(token, "", 1)
    if any(character.isalnum() for character in remainder):
        message = "display.date_format must contain DD, MM, and YYYY once each."
        raise ValueError(message)
    return text


def format_date(value: str, pattern: str) -> str:
    """
    Format an ISO date with a ``DD/MM/YYYY`` style pattern.

    Args:
        value: ``YYYY-MM-DD`` text, or an empty string.
        pattern: Pattern accepted by :func:`require_date_format`.

    Returns:
        The formatted date, or an empty string when ``value`` is empty.

    """

    if value == "":
        return ""
    if len(value) < 10 or value[4] != "-" or value[7] != "-":
        return value
    year, month, day = value[0:4], value[5:7], value[8:10]
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return value
    return pattern.replace("YYYY", year).replace("MM", month).replace("DD", day)


def format_timestamp(value: float | None, pattern: str) -> str:
    """
    Format a UTC instant using the configured date pattern.

    Args:
        value: Unix timestamp, or None.
        pattern: Pattern accepted by :func:`require_date_format`.

    Returns:
        ``DD/MM/YYYY HH:MM UTC`` style text, or an empty string.

    """

    if value is None:
        return ""
    moment = datetime.fromtimestamp(value, UTC)
    date = format_date(moment.strftime("%Y-%m-%d"), pattern)
    return f"{date} {moment.strftime('%H:%M')} UTC"
