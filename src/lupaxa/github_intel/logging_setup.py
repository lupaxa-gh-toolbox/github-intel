"""Logging that cannot print a GitHub token."""

from __future__ import annotations

import logging

__all__ = ["configure_logging"]


class _RedactingFormatter(logging.Formatter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__("%(levelname)s %(message)s")
        self._secrets = [secret for secret in secrets if secret]

    def format(self, record: logging.LogRecord) -> str:
        """
        Format one record and remove known secrets.

        Args:
            record: Log record.

        Returns:
            Redacted text.

        """

        text = super().format(record)
        for secret in self._secrets:
            text = text.replace(secret, "[redacted]")
        return text


def configure_logging(level: str, secrets: list[str] | None = None) -> None:
    """
    Configure the github-intel logger.

    Args:
        level: Logging level name.
        secrets: Values that must not appear in log output.

    """

    logger = logging.getLogger("github_intel")
    logger.handlers.clear()
    logger.setLevel(level.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(_RedactingFormatter(secrets or []))
    logger.addHandler(handler)
    logger.propagate = False
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
