"""JSON, CSV, and Markdown reports."""

from __future__ import annotations

import csv
import io
import json

from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT
from lupaxa.github_intel.views import RepositoryView, field_text

__all__ = ["render_report"]


def render_report(
    views: list[RepositoryView],
    report_format: str,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
    fields: tuple[str, ...],
    detail: bool = False,
) -> str:
    """
    Render repository rows.

    Args:
        views: Rows to export.
        report_format: ``json``, ``csv``, or ``markdown``.
        date_format: Pattern used for date cells.
        fields: Catalogue labels, in display order.
        detail: Use detail wording. A metadata error is the first record key.

    Returns:
        Report text.

    Raises:
        ValueError: The format is not supported.

    """

    records = [_record(view, date_format, fields, detail=detail) for view in views]
    if report_format == "json":
        return _json(records, detail=detail)
    if report_format == "csv":
        return _csv(records, fields, detail=detail)
    if report_format == "markdown":
        return _markdown(records, fields)
    message = f"Unsupported report format: {report_format}"
    raise ValueError(message)


def _record(
    view: RepositoryView,
    date_format: str,
    fields: tuple[str, ...],
    *,
    detail: bool,
) -> dict[str, str]:
    record: dict[str, str] = {}
    if detail and view.metadata_error:
        record["Metadata error"] = view.metadata_error
    for label in fields:
        record[label] = field_text(view, label, date_format, detail=detail)
    return record


def _json(records: list[dict[str, str]], *, detail: bool) -> str:
    if detail:
        return json.dumps(records[0] if records else {}, indent=2) + "\n"
    return json.dumps(records, indent=2) + "\n"


def _csv(
    records: list[dict[str, str]],
    fields: tuple[str, ...],
    *,
    detail: bool,
) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=_fieldnames(records, fields, detail=detail),
    )
    writer.writeheader()
    for record in records:
        writer.writerow(record)
    return buffer.getvalue()


def _fieldnames(
    records: list[dict[str, str]],
    fields: tuple[str, ...],
    *,
    detail: bool,
) -> list[str]:
    if detail and any("Metadata error" in record for record in records):
        return ["Metadata error", *fields]
    return list(fields)


def _markdown(records: list[dict[str, str]], fields: tuple[str, ...]) -> str:
    heading = "| " + " | ".join(fields) + " |"
    separator = "| " + " | ".join("---" for _ in fields) + " |"
    lines = ["# GitHub Intel Report", "", heading, separator]
    for record in records:
        cells = (_markdown_cell(record[label]) for label in fields)
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")
