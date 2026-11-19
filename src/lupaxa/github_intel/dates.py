"""Date patterns used by tables and reports."""

from __future__ import annotations

from datetime import UTC, datetime
import re

__all__ = [
    "DEFAULT_DATE_FORMAT",
    "format_date",
    "format_timestamp",
    "normalize_instant",
    "require_date_format",
]

DEFAULT_DATE_FORMAT = "DD/MM/YYYY HH:mm UTC"
_MESSAGE = (
    "display.date_format must contain YYYY, MM, and DD once each. "
    "HH and mm are optional and must appear together. "
    "ss and UTC are optional with the time."
)
_TOKEN = re.compile(r"YYYY|MM|DD|HH|SS|UTC", re.IGNORECASE)


def require_date_format(value: str) -> str:
    """
    Accept a date and time pattern.

    Month is the first ``MM``. Leave out ``HH`` and ``mm`` for a date with no
    clock. When they are present, minute is the second ``MM``. ``ss`` and ``UTC``
    may appear once with the clock.

    Args:
        value: Configured pattern, such as ``DD/MM/YYYY HH:mm UTC``.

    Returns:
        The pattern with date and hour tokens in upper case and ``mm`` lower.

    Raises:
        ValueError: A required token is missing or repeated, or other letters remain.

    """

    text = value.strip()
    pieces: list[str] = []
    cursor = 0
    counts = {"YYYY": 0, "MM": 0, "DD": 0, "HH": 0, "mm": 0, "ss": 0, "UTC": 0}
    month_seen = False
    for match in _TOKEN.finditer(text):
        gap = text[cursor : match.start()]
        if any(character.isalnum() for character in gap):
            raise ValueError(_MESSAGE)
        pieces.append(gap)
        raw = match.group(0).upper()
        if raw == "MM":
            name = "MM" if not month_seen else "mm"
            month_seen = True
        elif raw == "SS":
            name = "ss"
        else:
            name = raw
        counts[name] += 1
        pieces.append(name)
        cursor = match.end()
    tail = text[cursor:]
    if any(character.isalnum() for character in tail):
        raise ValueError(_MESSAGE)
    pieces.append(tail)
    if counts["YYYY"] != 1 or counts["MM"] != 1 or counts["DD"] != 1:
        raise ValueError(_MESSAGE)
    clock = counts["HH"] + counts["mm"]
    if clock not in {0, 2} or counts["HH"] > 1 or counts["mm"] > 1:
        raise ValueError(_MESSAGE)
    if counts["ss"] > 1 or counts["UTC"] > 1:
        raise ValueError(_MESSAGE)
    if clock == 0 and (counts["ss"] or counts["UTC"]):
        raise ValueError(_MESSAGE)
    return "".join(pieces)


def normalize_instant(value: object) -> str:
    """
    Keep a GitHub timestamp for later formatting.

    Args:
        value: ISO text from GitHub, or anything else.

    Returns:
        ``YYYY-MM-DDTHH:MM:SSZ`` when a time is present, ``YYYY-MM-DD`` when only
        a calendar day is present, or an empty string.

    """

    if not isinstance(value, str):
        return ""
    parsed = _parse_instant(value.strip())
    if parsed is None:
        return ""
    moment, has_time = parsed
    if not has_time:
        return moment.strftime("%Y-%m-%d")
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_date(value: str, pattern: str) -> str:
    """
    Format an ISO instant with the configured pattern.

    Args:
        value: ``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM:SSZ`` text, or empty.
        pattern: Pattern accepted by :func:`require_date_format`.

    Returns:
        The formatted date and time. Missing clock fields become ``--``. An
        empty ``value`` stays empty.

    """

    if value == "":
        return ""
    parsed = _parse_instant(value)
    if parsed is None:
        return value
    moment, has_time = parsed
    hour = moment.strftime("%H") if has_time else "--"
    minute = moment.strftime("%M") if has_time else "--"
    second = moment.strftime("%S") if has_time else "--"
    return (
        pattern.replace("YYYY", moment.strftime("%Y"))
        .replace("MM", moment.strftime("%m"))
        .replace("DD", moment.strftime("%d"))
        .replace("HH", hour)
        .replace("mm", minute)
        .replace("ss", second)
        .replace("UTC", "UTC")
    )


def format_timestamp(value: float | None, pattern: str) -> str:
    """
    Format a UTC instant using the configured pattern.

    Args:
        value: Unix timestamp, or None.
        pattern: Pattern accepted by :func:`require_date_format`.

    Returns:
        Text shaped by ``pattern``, or an empty string.

    """

    if value is None:
        return ""
    moment = datetime.fromtimestamp(value, UTC)
    return format_date(moment.strftime("%Y-%m-%dT%H:%M:%SZ"), pattern)


def _parse_instant(value: str) -> tuple[datetime, bool] | None:
    if len(value) < 10 or value[4] != "-" or value[7] != "-":
        return None
    if len(value) == 10:
        try:
            moment = datetime(
                int(value[0:4]),
                int(value[5:7]),
                int(value[8:10]),
                tzinfo=UTC,
            )
        except ValueError:
            return None
        return moment, False
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC), True
