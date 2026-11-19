"""
Operations shared by the CLI and the TUI.

Neither interface talks to GitHub or SQLite except through this service.
"""

from __future__ import annotations

from collections.abc import Callable
import contextlib
from dataclasses import replace
from pathlib import Path
import time

import httpx

from lupaxa.github_intel.config.defaults import write_default_files
from lupaxa.github_intel.config.editor import (
    add_repository,
    remove_repository,
    set_repository_fields,
)
from lupaxa.github_intel.config.loader import LoadedConfig, load_config
from lupaxa.github_intel.config.models import RepositorySpec
from lupaxa.github_intel.config.paths import (
    config_directory,
    data_directory,
    default_config_file,
)
from lupaxa.github_intel.config.profiles import (
    ResolvedProfile,
    check_defaults,
    resolve_profile,
)
from lupaxa.github_intel.errors import AuthError, ConfigError, NotFound, SyncTooSoon
from lupaxa.github_intel.github.auth import github_cli_token
from lupaxa.github_intel.github.client import GitHubClient
from lupaxa.github_intel.logging_setup import configure_logging
from lupaxa.github_intel.storage.database import Database, Document
from lupaxa.github_intel.sync.engine import SyncReport, synchronise
from lupaxa.github_intel.views import RepositoryView, build_view, select_repositories

__all__ = ["Service"]

TokenProvider = Callable[[], str | None]


class Service:
    """Load configuration, edit it, read the cache, and synchronise."""

    def __init__(
        self,
        config_path: Path | None = None,
        data_dir: Path | None = None,
        token_provider: TokenProvider = github_cli_token,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """
        Create a service.

        Args:
            config_path: Main configuration file, or None for the default.
            data_dir: Cache directory, or None for the XDG data directory.
            token_provider: Supplies the GitHub token. Tests pass a stub.
            transport: Optional HTTP transport. Tests pass a mock.

        """

        self.config_path = config_path
        self.data_dir = data_directory() if data_dir is None else data_dir
        self.token_provider = token_provider
        self.transport = transport
        self.log_level: str | None = None

    def load(self) -> LoadedConfig:
        """
        Load and validate configuration.

        Returns:
            Loaded configuration.

        """

        return load_config(self._require_config())

    def ensure_config(self) -> Path:
        """
        Return the main configuration path, creating defaults when absent.

        Returns:
            Path to config.yml. An explicit missing ``--config`` is not created.

        """

        if self.config_path is not None:
            return self.config_path
        directory = config_directory()
        current = default_config_file(directory)
        if current.is_file():
            return current
        return write_default_files(directory)

    async def views(
        self,
        *,
        group: str | None = None,
        profile: str | None = None,
        tag: str | None = None,
        status: str | None = None,
    ) -> list[RepositoryView]:
        """
        List repositories from configuration and the cache.

        Args:
            group: Group filter.
            profile: Profile filter.
            tag: Tag filter.
            status: Status filter such as ``stale`` or ``disabled``.

        Returns:
            Display rows.

        """

        loaded = self.load()
        database = self._database()
        try:
            rows = []
            for repository in select_repositories(
                loaded,
                group=group,
                profile=profile,
                tag=tag,
            ):
                view = await self._view(loaded, database, repository)
                if status is None or status in view.statuses:
                    rows.append(view)
            return rows
        finally:
            await database.close()

    async def show(
        self,
        repo: str,
    ) -> tuple[RepositoryView, ResolvedProfile, list[Document]]:
        """
        Return one repository, its resolved profile, and cached documents.

        Args:
            repo: ``owner/name``.

        Returns:
            View, resolved checks, and documents.

        Raises:
            NotFound: The repository is not configured.

        """

        loaded = self.load()
        repository = _require(loaded, repo)
        database = self._database()
        try:
            view = await self._view(loaded, database, repository)
            documents = await database.documents_for(repository.repo)
        finally:
            await database.close()
        resolved = resolve_profile(
            loaded.profiles,
            repository.profile or loaded.config.defaults.profile,
            repository.checks,
            **check_defaults(loaded.config.defaults),
        )
        return view, resolved, documents

    async def sync(
        self,
        *,
        force: bool = False,
        group: str | None = None,
        profile: str | None = None,
        repo: str | None = None,
        concurrency: int | None = None,
        on_progress: Callable[[SyncReport], None] | None = None,
    ) -> SyncReport:
        """
        Synchronise enabled repositories.

        Args:
            force: Ignore cache freshness and ``sync.interval``.
            group: Limit to one group.
            profile: Limit to one profile.
            repo: Limit to one repository.
            concurrency: Override the configured request limit.
            on_progress: Called as counters change. It must not await.

        Returns:
            Synchronisation statistics.

        Raises:
            NotFound: ``repo`` is not configured.
            SyncTooSoon: The previous sync is still inside ``sync.interval``.

        """

        loaded = self._with_concurrency(self.load(), concurrency)
        if repo is not None:
            _require(loaded, repo)
        matched = select_repositories(loaded, group=group, profile=profile, repo=repo)
        selected = tuple(item for item in matched if item.enabled)
        token = self.token_provider()
        configure_logging(
            self.log_level or loaded.config.logging.level,
            [token] if token else [],
        )
        await self.assert_sync_allowed(force=force)
        database = self._database()
        client = GitHubClient(
            api_url=loaded.config.github.api_url,
            token=token,
            timeout=loaded.config.sync.timeout,
            retries=loaded.config.sync.retries,
            concurrency=loaded.config.sync.concurrency,
            transport=self.transport,
        )
        started = time.time()
        try:
            report = await synchronise(
                loaded,
                database,
                client,
                force=force,
                selected=selected,
                on_progress=on_progress,
            )
        finally:
            await client.aclose()
        report.skipped = len(matched) - len(selected)
        report.elapsed = time.time() - started
        await database.record_run(started, time.time(), _stats(report))
        await database.close()
        return report

    async def assert_sync_allowed(self, *, force: bool = False) -> None:
        """
        Refuse a sync that starts inside ``sync.interval``.

        Args:
            force: Skip the interval check.

        Raises:
            SyncTooSoon: The previous sync is still inside ``sync.interval``.

        """

        if force:
            return
        interval = self.load().config.sync.interval
        if interval <= 0:
            return
        database = self._database()
        try:
            await _refuse_if_too_soon(database, interval)
        finally:
            await database.close()

    async def check_remote(self, repo: str) -> None:
        """
        Confirm GitHub will answer for one repository.

        Args:
            repo: ``owner/name``.

        Raises:
            AuthError: GitHub returned 401.
            ConfigError: GitHub returned 404 or another error.

        """

        loaded = self.load()
        token = self.token_provider()
        client = GitHubClient(
            api_url=loaded.config.github.api_url,
            token=token,
            timeout=loaded.config.sync.timeout,
            retries=0,
            concurrency=1,
            transport=self.transport,
        )
        try:
            result = await client.get(f"/repos/{repo}")
        finally:
            await client.aclose()
        if result.status == 401:
            raise AuthError(result.error or "GitHub rejected the credentials.")
        if result.error:
            raise ConfigError(result.error)

    def add(
        self,
        repo: str,
        group: str | None,
        profile: str | None,
        tags: list[str],
    ) -> None:
        """
        Add a repository to the configuration file.

        Args:
            repo: ``owner/name``.
            group: Optional group.
            profile: Optional profile.
            tags: Tags.

        """

        path = self.ensure_config()
        self.config_path = path
        add_repository(path, repo, group=group, profile=profile, tags=tags)

    def remove(self, repo: str) -> None:
        """
        Remove a repository from configuration.

        Args:
            repo: ``owner/name``.

        """

        remove_repository(self._require_config(), repo)

    def set_fields(self, repo: str, **fields: bool | str | None) -> None:
        """
        Update fields on a configured repository.

        Args:
            repo: ``owner/name``.
            fields: Values such as ``enabled`` or ``profile``.

        """

        set_repository_fields(self._require_config(), repo, **fields)

    def reset(self) -> tuple[Path, ...]:
        """
        Delete the cache files.

        Configuration, profiles, and the repository list stay. The next sync
        starts from an empty cache, including the sync interval.

        Returns:
            Files that were removed.

        """

        database = self._database().path
        names = (
            database,
            Path(f"{database}-wal"),
            Path(f"{database}-shm"),
            Path(f"{database}-journal"),
        )
        removed: list[Path] = []
        for path in names:
            if path.is_file():
                path.unlink()
                removed.append(path)
        with contextlib.suppress(OSError):
            self.data_dir.rmdir()
        return tuple(removed)

    async def clear_cache(self, repo: str | None) -> None:
        """
        Delete cached rows.

        Args:
            repo: One repository, or None for the whole cache.

        """

        database = self._database()
        try:
            await database.clear(repo)
        finally:
            await database.close()

    async def vacuum(self) -> None:
        """Rebuild the SQLite file."""

        database = self._database()
        try:
            await database.vacuum()
        finally:
            await database.close()

    async def cache_info(self) -> dict[str, int | str]:
        """
        Describe the cache file.

        Returns:
            Path, size, and row counts.

        """

        database = self._database()
        try:
            counts = await database.counts()
        finally:
            await database.close()
        size = database.path.stat().st_size if database.path.exists() else 0
        return {"path": str(database.path), "bytes": size, **counts}

    def _database(self) -> Database:
        return Database(self.data_dir / "cache.sqlite")

    def _require_config(self) -> Path:
        if self.config_path is not None:
            if not self.config_path.is_file():
                raise ConfigError(f"{self.config_path} does not exist.")
            return self.config_path
        current = default_config_file(config_directory())
        if not current.is_file():
            raise ConfigError("No configuration file exists.")
        return current

    async def _view(
        self,
        loaded: LoadedConfig,
        database: Database,
        repository: RepositorySpec,
    ) -> RepositoryView:
        documents = await database.documents_for(repository.repo)
        checks = await database.checks_for(repository.repo)
        return build_view(loaded, repository, documents, checks)

    def _with_concurrency(
        self,
        loaded: LoadedConfig,
        concurrency: int | None,
    ) -> LoadedConfig:
        if concurrency is None:
            return loaded
        sync = loaded.config.sync.model_copy(update={"concurrency": concurrency})
        config = loaded.config.model_copy(update={"sync": sync})
        return replace(loaded, config=config)


async def _refuse_if_too_soon(database: Database, interval: int) -> None:
    if interval <= 0:
        return
    started = await database.latest_sync_started()
    if started is None:
        return
    elapsed = time.time() - started
    if elapsed >= interval:
        return
    raise SyncTooSoon(
        "Synchronisation is too soon. "
        f"The last sync started {_span(elapsed)} ago.\n"
        f"Wait {_span(interval - elapsed)}, or pass --force. "
        f"sync.interval is {_span(interval)}.",
    )


def _span(seconds: float) -> str:
    total = max(0, int(seconds + 0.5))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _require(loaded: LoadedConfig, repo: str) -> RepositorySpec:
    for repository in loaded.repositories:
        if repository.repo.casefold() == repo.casefold():
            return repository
    raise NotFound(f"{repo} is not configured.")


def _stats(report: SyncReport) -> dict[str, object]:
    return {
        "repositories": report.repositories,
        "successful": report.successful,
        "failed": report.failed,
        "skipped": report.skipped,
        "requests": report.requests,
        "cache_hits": report.cache_hits,
        "not_modified": report.not_modified,
        "cancelled": report.cancelled,
    }
