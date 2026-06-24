"""Main screen — DataTable gist browser with search, filter, and refresh."""

from datetime import date

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label

from gistman.log import logger
from gistman.screens.detail import DetailScreen
from gistman.screens.edit import EditScreen
from gistman.screens.filter_modal import FilterModal
from gistman.screens.stats_modal import StatsModal
from gistman.store import IStore


class MainScreen(Screen):
    """Primary screen — shows a searchable, filterable table of all gists."""

    search_query = reactive("")
    content_query = reactive("")
    active_filters: dict = {}

    BINDINGS = [
        Binding("ctrl+f", "focus_search", "Search"),
        Binding("ctrl+n", "new_gist", "New"),
        Binding("ctrl+o", "open_filters", "Filters"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+s", "open_stats", "Stats"),
        Binding("ctrl+b", "toggle_bookmarks", "Bookmarks"),
        Binding("escape", "pop", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="search-row"):
            yield Input(placeholder="Search by name/description...", id="search-input")
            yield Button("↻", id="refresh-btn")
        yield Label("", id="gist-count")
        yield DataTable(id="gist-table", cursor_type="row")
        yield Label("", id="filter-bar")

    def on_mount(self) -> None:
        """Initialise table columns and load cached data."""
        table = self.query_one("#gist-table", DataTable)
        table.add_columns("", "Name", "URL", "Type", "Updated", "Files", "Lines")
        self._load_data()

    def on_screen_resume(self) -> None:
        self._load_data()
        self.query_one("#gist-table", DataTable).focus()
        if self.app.store.is_stale or not self.app.store.gists:
            self.call_later(self._initial_refresh)

    def _load_data(self) -> None:
        self._apply_filters()

    def _to_filter_args(self) -> dict:
        """Build kwargs for ``store.search()`` from the reactive state."""
        args: dict = {}
        args["query"] = self.search_query or self.active_filters.get("name", "")

        if self.active_filters:
            args["content"] = self.active_filters.get("content", "")
            ftype = self.active_filters.get("file_type")
            if ftype:
                args["file_types"] = [ftype]
            args["visibility"] = self.active_filters.get("visibility")
            args["bookmarks_only"] = self.active_filters.get("bookmarks_only", False)
            df = self.active_filters.get("date_from")
            dt = self.active_filters.get("date_to")
            if df:
                try:
                    args["date_from"] = date.fromisoformat(df)
                except ValueError:
                    pass
            if dt:
                try:
                    args["date_to"] = date.fromisoformat(dt)
                except ValueError:
                    pass

        return args

    def _apply_filters(self) -> None:
        """Re-run the search and re-populate the DataTable."""
        store: IStore = self.app.store
        try:
            results = store.search(**self._to_filter_args())
        except Exception:
            self._show_empty("Error loading gists")
            return

        table = self.query_one("#gist-table", DataTable)
        table.clear()

        if not results:
            self._show_empty("No gists found")
            return

        for item in results:
            ts = item["updated_at"][:10] if item["updated_at"] else ""
            bm = "⋆" if item["bookmarked"] else " "
            desc = item["description"]
            if len(desc) > 50:
                desc = desc[:47] + "..."
            ft = ",".join(sorted(set(item["file_types"])))[:15]
            url = f"gist.github.com/{item['id']}"
            try:
                table.add_row(
                    bm,
                    desc,
                    url,
                    ft,
                    ts,
                    str(item["file_count"]),
                    str(item["total_lines"] or ""),
                )
            except Exception:
                pass

        table.move_cursor(row=0)
        table.focus()
        self._update_counts(len(results), len(store.gists))

    def _update_counts(self, shown: int, total: int) -> None:
        """Refresh the count and filter-bar labels."""
        label = self.query_one("#gist-count", Label)
        fb = self.query_one("#filter-bar", Label)
        filter_parts = []
        if self.search_query:
            filter_parts.append(f'name:"{self.search_query}"')
        if self.active_filters.get("content"):
            filter_parts.append(f'content:"{self.active_filters.get("content")}"')
        if self.active_filters.get("file_type"):
            filter_parts.append(f'type:{self.active_filters.get("file_type")}')
        if self.active_filters.get("visibility"):
            filter_parts.append(f'visibility:{self.active_filters.get("visibility")}')
        if self.active_filters.get("date_from") or self.active_filters.get("date_to"):
            df = self.active_filters.get("date_from", "∞")
            dt = self.active_filters.get("date_to", "∞")
            filter_parts.append(f"date:{df}→{dt}")
        if self.active_filters.get("bookmarks_only"):
            filter_parts.append("bookmarked")
        fb_str = " | ".join(filter_parts) if filter_parts else "All gists"
        label.update(f"Showing {shown} of {total} gists  ({fb_str})")

    def _show_empty(self, msg: str) -> None:
        self.query_one("#gist-count", Label).update(msg)

    # ── Actions ────────────────────────────────────────────────────────────

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_new_gist(self) -> None:
        self.app.push_screen(EditScreen(mode="create"))

    def action_open_filters(self) -> None:
        def on_filter(filters: dict | None) -> None:
            if filters is not None:
                self.active_filters = filters
                self._apply_filters()

        self.app.push_screen(FilterModal(), on_filter)

    def action_toggle_bookmarks(self) -> None:
        if self.active_filters.get("bookmarks_only"):
            self.active_filters.pop("bookmarks_only")
        else:
            self.active_filters["bookmarks_only"] = True
        self._apply_filters()

    def action_open_stats(self) -> None:
        self.app.push_screen(StatsModal())

    def action_pop(self) -> None:
        """Escape handler: clear search → clear filters → back (no-op on root)."""
        if self.search_query:
            self.query_one("#search-input", Input).value = ""
            self.search_query = ""
        elif self.active_filters:
            self.active_filters = {}
            self._apply_filters()

    # ── Event handlers ────────────────────────────────────────────────────

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value
        self._apply_filters()

    @on(DataTable.RowSelected, "#gist-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the gist detail screen on Enter."""
        store: IStore = self.app.store
        items = store.search(**self._to_filter_args())
        if event.cursor_row is not None and event.cursor_row < len(items):
            gist_id = items[event.cursor_row]["id"]
            self.app.push_screen(DetailScreen(gist_id))

    @on(Button.Pressed, "#refresh-btn")
    async def on_refresh(self) -> None:
        await self._do_refresh()

    async def _initial_refresh(self) -> None:
        await self._do_refresh()

    async def _do_refresh(self) -> None:
        """Fetch latest gist list from GitHub and refresh the table."""
        store: IStore = self.app.store
        self.query_one("#refresh-btn", Button).label = "⟳"
        try:
            count = await store.refresh_list()
            logger.info("Refreshed {} gists", count)
            self._apply_filters()
            self.app.notify(f"Loaded {count} gists", severity="information")
        except RuntimeError as e:
            logger.exception("Refresh failed")
            self.app.notify(f"Refresh failed: {e}", severity="error")
        self.query_one("#refresh-btn", Button).label = "↻"

    def action_refresh(self) -> None:
        self.call_later(self._do_refresh)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.action_pop()
            event.prevent_default()
            return
        focused = self.focused
        if focused is not None and hasattr(focused, "id") and focused.id == "search-input":
            return
        if event.key == "j":
            table = self.query_one("#gist-table", DataTable)
            if table.cursor_row is not None:
                table.move_cursor(row=min(table.cursor_row + 1, table.row_count - 1))
                event.prevent_default()
        elif event.key == "k":
            table = self.query_one("#gist-table", DataTable)
            if table.cursor_row is not None and table.cursor_row > 0:
                table.move_cursor(row=table.cursor_row - 1)
                event.prevent_default()
