"""Shared check result."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CheckResult"]


@dataclass(frozen=True)
class CheckResult:
    """One derived check outcome."""

    name: str
    status: str
    summary: str
    failure: bool = False
