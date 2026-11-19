"""
SQLite cache.

One lock serialises writes. Network code stays outside the lock.
Expired rows are kept until a newer result or an explicit clear.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time

import aiosqlite

__all__ = [
    "Database",
    "Document",
    "StoredCheck",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    repo TEXT NOT NULL,
    category TEXT NOT NULL,
    body TEXT,
    etag TEXT,
    fetched_at REAL,
    error TEXT,
    PRIMARY KEY (repo, category)
);
CREATE TABLE IF NOT EXISTS check_results (
    repo TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    failure INTEGER NOT NULL,
    checked_at REAL NOT NULL,
    PRIMARY KEY (repo, name)
);
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    finished_at REAL,
    stats_json TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Document:
    """One cached API payload."""

    repo: str
    category: str
    body: str | None
    etag: str | None
    fetched_at: float | None
    error: str | None

    def json_body(self) -> object:
        """
        Return the parsed JSON body.

        Returns:
            Decoded JSON, or None when the body is empty.

        """

        if self.body is None or self.body == "":
            return None
        return json.loads(self.body)


@dataclass(frozen=True)
class StoredCheck:
    """One stored check row."""

    repo: str
    name: str
    status: str
    summary: str
    failure: bool
    checked_at: float


class Database:
    """Async SQLite cache with a single in-process writer."""

    def __init__(self, path: Path) -> None:
        """
        Point at a database file. The file is created on first open.

        Args:
            path: SQLite path.

        """

        self.path = path
        self._lock = asyncio.Lock()
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        """Create the file, enable WAL, and apply the schema."""

        async with self._lock:
            if self._db is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                self.path.parent.chmod(0o700)
            self._db = await aiosqlite.connect(self.path)
            self._db.row_factory = aiosqlite.Row
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.executescript(_SCHEMA)
            await self._db.commit()
            if os.name != "nt":
                self.path.chmod(0o600)

    async def close(self) -> None:
        """Close the connection."""

        async with self._lock:
            if self._db is not None:
                await self._db.close()
                self._db = None

    async def get(self, repo: str, category: str) -> Document | None:
        """
        Return one cached document.

        Args:
            repo: Repository identifier.
            category: Cache category.

        Returns:
            The row, or None.

        """

        await self.open()
        async with self._lock:
            cursor = await self._connection().execute(
                """
                SELECT repo, category, body, etag, fetched_at, error
                FROM documents WHERE repo = ? AND category = ?
                """,
                (repo, category),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return _document(row)

    async def save(
        self,
        repo: str,
        category: str,
        *,
        body: object | None = None,
        etag: str | None,
        error: str | None,
        keep_body: bool,
    ) -> None:
        """
        Insert or update a document and refresh its timestamp.

        Args:
            repo: Repository identifier.
            category: Cache category.
            body: JSON value. Ignored when ``keep_body`` is true.
            etag: New ETag.
            error: Error text, or None on success.
            keep_body: Preserve the previous body (HTTP 304).

        """

        await self.open()
        encoded = None if body is None else json.dumps(body)
        async with self._lock:
            if keep_body:
                await self._connection().execute(
                    """
                    UPDATE documents
                    SET etag = ?, fetched_at = ?, error = NULL
                    WHERE repo = ? AND category = ?
                    """,
                    (etag, time.time(), repo, category),
                )
            else:
                await self._connection().execute(
                    """
                    INSERT INTO documents (
                        repo, category, body, etag, fetched_at, error
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(repo, category) DO UPDATE SET
                        body = excluded.body,
                        etag = excluded.etag,
                        fetched_at = excluded.fetched_at,
                        error = excluded.error
                    """,
                    (repo, category, encoded, etag, time.time(), error),
                )
            await self._connection().commit()

    async def save_checks(self, repo: str, checks: list[StoredCheck]) -> None:
        """
        Replace the stored checks for one repository.

        Args:
            repo: Repository identifier.
            checks: New rows.

        """

        await self.open()
        async with self._lock:
            await self._connection().execute(
                "DELETE FROM check_results WHERE repo = ?",
                (repo,),
            )
            await self._connection().executemany(
                """
                INSERT INTO check_results (
                    repo, name, status, summary, failure, checked_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.repo,
                        item.name,
                        item.status,
                        item.summary,
                        int(item.failure),
                        item.checked_at,
                    )
                    for item in checks
                ],
            )
            await self._connection().commit()

    async def checks_for(self, repo: str) -> list[StoredCheck]:
        """
        Return stored checks for one repository.

        Args:
            repo: Repository identifier.

        Returns:
            Check rows.

        """

        await self.open()
        async with self._lock:
            cursor = await self._connection().execute(
                """
                SELECT repo, name, status, summary, failure, checked_at
                FROM check_results WHERE repo = ? ORDER BY name
                """,
                (repo,),
            )
            rows = await cursor.fetchall()
        return [_check(row) for row in rows]

    async def documents_for(self, repo: str) -> list[Document]:
        """
        Return every cached document for one repository.

        Args:
            repo: Repository identifier.

        Returns:
            Document rows.

        """

        await self.open()
        async with self._lock:
            cursor = await self._connection().execute(
                """
                SELECT repo, category, body, etag, fetched_at, error
                FROM documents WHERE repo = ? ORDER BY category
                """,
                (repo,),
            )
            rows = await cursor.fetchall()
        return [_document(row) for row in rows]

    async def clear(self, repo: str | None = None) -> None:
        """
        Delete cached documents and checks.

        Args:
            repo: Limit the delete to one repository. None clears everything.

        """

        await self.open()
        async with self._lock:
            if repo is None:
                await self._connection().execute("DELETE FROM documents")
                await self._connection().execute("DELETE FROM check_results")
            else:
                await self._connection().execute(
                    "DELETE FROM documents WHERE repo = ?",
                    (repo,),
                )
                await self._connection().execute(
                    "DELETE FROM check_results WHERE repo = ?",
                    (repo,),
                )
            await self._connection().commit()

    async def vacuum(self) -> None:
        """Rebuild the database file."""

        await self.open()
        async with self._lock:
            await self._connection().execute("VACUUM")

    async def counts(self) -> dict[str, int]:
        """
        Return row counts.

        Returns:
            Document, check, and sync-run counts.

        """

        await self.open()
        async with self._lock:
            documents = await self._count("documents")
            checks = await self._count("check_results")
            runs = await self._count("sync_runs")
        return {"documents": documents, "checks": checks, "sync_runs": runs}

    async def latest_sync_started(self) -> float | None:
        """
        Return when the newest synchronisation started.

        Returns:
            Epoch seconds, or None when no run has been recorded.

        """

        await self.open()
        async with self._lock:
            cursor = await self._connection().execute(
                "SELECT started_at FROM sync_runs ORDER BY started_at DESC LIMIT 1",
            )
            row = await cursor.fetchone()
        return None if row is None else float(row[0])

    async def record_run(
        self,
        started: float,
        finished: float,
        stats: dict[str, object],
    ) -> None:
        """
        Append one synchronisation history row.

        Args:
            started: Start timestamp.
            finished: Finish timestamp.
            stats: JSON-serialisable statistics.

        """

        await self.open()
        async with self._lock:
            await self._connection().execute(
                """
                INSERT INTO sync_runs (started_at, finished_at, stats_json)
                VALUES (?, ?, ?)
                """,
                (started, finished, json.dumps(stats)),
            )
            await self._connection().commit()

    def _connection(self) -> aiosqlite.Connection:
        if self._db is None:
            message = "Database is not open."
            raise RuntimeError(message)
        return self._db

    async def _count(self, table: str) -> int:
        cursor = await self._connection().execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        row = await cursor.fetchone()
        return 0 if row is None else int(row[0])


def _document(row: aiosqlite.Row) -> Document:
    return Document(
        repo=str(row["repo"]),
        category=str(row["category"]),
        body=None if row["body"] is None else str(row["body"]),
        etag=None if row["etag"] is None else str(row["etag"]),
        fetched_at=None if row["fetched_at"] is None else float(row["fetched_at"]),
        error=None if row["error"] is None else str(row["error"]),
    )


def _check(row: aiosqlite.Row) -> StoredCheck:
    return StoredCheck(
        repo=str(row["repo"]),
        name=str(row["name"]),
        status=str(row["status"]),
        summary=str(row["summary"]),
        failure=bool(row["failure"]),
        checked_at=float(row["checked_at"]),
    )
