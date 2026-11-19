"""
Textual interface.

The widgets call :class:`Service`. They do not call GitHub themselves.
"""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Static

from lupaxa.github_intel.app import Service
from lupaxa.github_intel.config.paths import default_config_file
from lupaxa.github_intel.config.profiles import resolve_profile
from lupaxa.github_intel.dates import DEFAULT_DATE_FORMAT, format_date
from lupaxa.github_intel.errors import ConfigError
from lupaxa.github_intel.views import (
    RepositoryView,
    detail_rows,
    metric_cells,
    metric_columns,
    split_identifier,
    status_style,
)

__all__ = ["IntelTui", "RepoDetail", "run_tui"]


class RepoDetail(ModalScreen[None]):
    """Popup table of one repository."""

    BINDINGS = [Binding("escape", "dismiss", "Close", priority=True)]

    def __init__(self, view: RepositoryView, date_format: str) -> None:
        """
        Create the popup.

        Args:
            view: Repository to show.
            date_format: Pattern such as ``DD/MM/YYYY``.

        """

        super().__init__()
        self.view = view
        self.date_format = date_format

    def compose(self) -> ComposeResult:
        """
        Build the field and value table.

        Returns:
            A bordered dialog.

        """

        with VerticalScroll(id="dialog"):
            yield Static(self.view.repo, id="detail-title")
            with Vertical(id="detail"):
                for field, value in detail_rows(
                    self.view,
                    date_format=self.date_format,
                ):
                    with Horizontal(classes="detail-row"):
                        yield Static(field, classes="detail-field")
                        yield Static(_painted(value), classes="detail-value")


class IntelTui(App[None]):
    """Repository browser backed by the local cache."""

    CSS = """
    #summary { height: auto; padding: 0 1; }
    #search { margin: 0 1; }
    DataTable { height: 1fr; }
    RepoDetail { align: center middle; }
    #dialog {
        width: 90%;
        max-width: 120;
        height: auto;
        max-height: 90%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow-x: hidden;
    }
    #detail-title { text-style: bold; padding: 0 0 1 0; height: auto; }
    #detail { height: auto; }
    .detail-row { height: auto; width: 100%; }
    .detail-field { width: 18; height: auto; text-style: bold; }
    .detail-value { width: 1fr; height: auto; }
    """
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", key_display="control + q", priority=True),
        Binding("r", "sync", "Sync"),
        Binding("slash", "search", "Search"),
        Binding("p", "profiles", "Profiles"),
        Binding("c", "config", "Config"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, service: Service) -> None:
        """
        Create the interface.

        Args:
            service: Shared application service.

        """

        super().__init__()
        self.service = service
        self.views: list[RepositoryView] = []
        self._columns = metric_columns([])
        self.date_format = DEFAULT_DATE_FORMAT
        self._mode = "repos"
        self._sync_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        """
        Build the browser layout.

        Returns:
            Header, summary, search, table, and footer.

        """

        yield Header()
        yield Static("Loading cache…", id="summary")
        yield Input(placeholder="Search repositories...", id="search")
        yield DataTable(id="table")
        yield Footer()

    async def on_mount(self) -> None:
        """Load cached repositories without contacting GitHub."""

        table = self.query_one(DataTable)
        table.cursor_type = "row"
        await self._reload()

    async def on_input_changed(self, event: Input.Changed) -> None:
        """
        Filter the current table.

        Args:
            event: Search box change.

        """

        self._fill(event.value)

    def action_search(self) -> None:
        """Focus the search box."""

        self.query_one("#search", Input).focus()

    async def action_sync(self) -> None:
        """Start synchronisation without blocking the interface."""

        if self._sync_task is not None and not self._sync_task.done():
            return
        self._sync_task = asyncio.create_task(self._run_sync())

    def action_cancel(self) -> None:
        """Cancel the in-progress synchronisation."""

        if self._sync_task is not None and not self._sync_task.done():
            self._sync_task.cancel()

    async def action_profiles(self) -> None:
        """Show profiles and the repositories that use them."""

        try:
            loaded = self.service.load()
        except ConfigError as exc:
            self._show_config_error(exc)
            return
        self._mode = "profiles"
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("Profile", "Inheritance", "Repositories")
        counts: dict[str, int] = {}
        for view in self.views:
            counts[view.profile] = counts.get(view.profile, 0) + 1
        for name in loaded.profiles:
            resolved = resolve_profile(
                loaded.profiles,
                name,
                {},
                loaded.config.defaults.standards,
                issues=loaded.config.defaults.issues,
                pull_requests=loaded.config.defaults.pull_requests,
                quality=loaded.config.defaults.quality,
            )
            table.add_row(name, " -> ".join(resolved.chain), str(counts.get(name, 0)))

    async def action_config(self) -> None:
        """Show the resolved configuration paths and sync settings."""

        try:
            loaded = self.service.load()
        except ConfigError as exc:
            self._show_config_error(exc)
            return
        self.query_one("#summary", Static).update(
            "\n".join(
                [
                    f"Config: {loaded.path}",
                    f"Profiles: {loaded.profiles_path}",
                    f"Repositories: {loaded.repositories_path}",
                    f"Concurrency: {loaded.config.sync.concurrency}",
                    "Configuration editing from the TUI is not available yet.",
                ]
            )
        )

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """
        Show the selected repository.

        Args:
            event: Table selection.

        """

        if self._mode != "repos":
            return
        repo = str(event.row_key.value)
        view = next((item for item in self.views if item.repo == repo), None)
        if view is None:
            return
        self.push_screen(RepoDetail(view, self.date_format))

    async def _run_sync(self) -> None:
        self.query_one("#summary", Static).update("Synchronising…")
        try:
            report = await self.service.sync()
        except asyncio.CancelledError:
            self.query_one("#summary", Static).update("Synchronisation cancelled.")
            await self._reload()
            return
        except ConfigError as exc:
            self._show_config_error(exc)
            return
        self.query_one("#summary", Static).update(
            f"Successful {report.successful}  Failed {report.failed}  "
            f"Requests {report.requests}  Elapsed {report.elapsed:.1f}s"
        )
        await self._reload()

    def _show_config_error(self, exc: ConfigError) -> None:
        self.query_one("#summary", Static).update(_config_problem(exc, self.service))
        self.notify("Configuration could not be loaded.", severity="error")

    async def _reload(self) -> None:
        try:
            self.date_format = self.service.load().config.display.date_format
            self.views = await self.service.views()
        except ConfigError as exc:
            self.views = []
            self._show_config_error(exc)
            return
        self._mode = "repos"
        table = self.query_one(DataTable)
        table.clear(columns=True)
        self._columns = metric_columns(self.views)
        _repo_columns(table, self._columns)
        self._fill(self.query_one("#search", Input).value)
        self.query_one("#summary", Static).update(_counts(self.views))

    def _fill(self, query: str) -> None:
        if self._mode != "repos":
            return
        folded = query.casefold()
        table = self.query_one(DataTable)
        table.clear()
        rows = sorted(self.views, key=lambda view: view.repo.casefold())
        for view in rows:
            haystack = f"{view.repo} {view.description}".casefold()
            if folded and folded not in haystack:
                continue
            org, name = split_identifier(view.repo)
            table.add_row(
                org,
                name,
                view.visibility,
                view.group,
                view.profile,
                _painted(view.status),
                view.version,
                format_date(view.last_push, self.date_format),
                format_date(view.release_date, self.date_format),
                *metric_cells(view, self._columns),
                key=view.repo,
            )


def _painted(value: str) -> str | Text:
    style = status_style(value)
    if not style:
        return value
    return Text(value, style=style)


def _repo_columns(table: DataTable[str | Text], columns: tuple[str, ...]) -> None:
    table.add_columns(
        "Org",
        "Repo",
        "Visibility",
        "Group",
        "Profile",
        "Status",
        "Version",
        "Last push",
        "Release date",
        *columns,
    )


def run_tui(service: Service) -> None:
    """
    Run the interactive interface until the operator quits.

    Args:
        service: Shared application service.

    """

    IntelTui(service).run()


def _config_problem(exc: ConfigError, service: Service) -> str:
    location = service.config_path or default_config_file()
    lines = ["Configuration could not be loaded.", "", str(exc)]
    if str(location) not in str(exc):
        lines.extend(["", f"Expected file: {location}"])
    lines.extend(
        [
            "",
            "Create the configuration with:",
            "",
            "    github-intel repo add owner/name",
            "",
            "Or press control + q to quit.",
        ]
    )
    return "\n".join(lines)


def _counts(views: list[RepositoryView]) -> str:
    total = len(views)
    pending = {"Healthy", "Current", "Disabled", "No releases"}
    review = sum(1 for view in views if view.status not in pending)
    cached = sum(
        1
        for view in views
        if "cached" in view.statuses and "stale" not in view.statuses
    )
    percent = 0 if total == 0 else round(cached / total * 100)
    return f"Repositories {total}    Need review {review}    Cache fresh {percent}%"
