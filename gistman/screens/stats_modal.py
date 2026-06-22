"""Statistics dashboard — file type distribution, monthly timeline, totals."""

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from gistman.store import IStore


class StatsModal(ModalScreen[None]):
    """Show aggregate stats over all cached gists."""

    BINDINGS = [
        Binding("escape", "close_stats", "Close", show=False),
    ]

    def action_close_stats(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        store: IStore = self.app.store
        stats = store.get_stats()
        with Vertical(classes="stats-dialog"):
            yield Label("Gist Statistics", classes="title")
            yield Static(
                f"Total gists:  {stats['total_gists']}\n"
                f"Total files:  {stats['total_files']}\n"
                f"Total lines:  {stats['total_lines']:,}\n"
                f"Avg files/gist:  {stats['avg_files']}\n"
                f"Avg lines/file:  {stats['avg_lines']}\n"
                f"Bookmarked:  {stats['bookmarked_count']}\n",
                classes="stat-row",
            )
            yield Label("File types:", classes="title")
            for ftype, count in stats["file_types"]:
                bar = "█" * count
                yield Static(f"  {ftype:<8} {bar} {count}", classes="stat-row")
            yield Label("Timeline (gists per month):", classes="title")
            for month, count in list(stats["months"].items())[-12:]:
                bar = "█" * count
                yield Static(f"  {month}  {bar} {count}", classes="stat-row")
            yield Button("Close", id="stats-close", variant="primary")

    @on(Button.Pressed, "#stats-close")
    def close_stats(self) -> None:
        self.dismiss(None)
