"""Advanced filter dialog — name, content, file type, date range, visibility."""

from datetime import date, timedelta

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select


class FilterModal(ModalScreen[dict | None]):
    """Modal for setting multi-field gist filters.

    Dismisses with a dict of filter values, ``{}`` (reset), or ``None`` (cancel).
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel", show=False),
        Binding("enter", "submit", "Apply", show=False),
    ]

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(self._get_filters())

    def compose(self) -> ComposeResult:
        with Vertical(classes="filter-dialog"):
            yield Label("Advanced Filters", classes="title")
            yield Input(placeholder="Search by name/description...", id="f-name")
            yield Input(placeholder="Search by content...", id="f-content")
            yield Select(
                [(t, t) for t in [
                    "", ".py", ".js", ".ts", ".sql", ".yaml", ".yml",
                    ".json", ".md", ".sh", ".bash", ".ps1", ".txt",
                    ".csv", ".xml", ".html", ".css", ".go", ".rs", ".java",
                ]],
                prompt="File type (optional)...",
                id="f-type",
            )
            yield Select(
                [("All", "all"), ("Secret", "secret"), ("Public", "public")],
                value="all",
                id="f-visibility",
            )
            yield Label("Date range:")
            with Horizontal():
                yield Input(placeholder="From (YYYY-MM-DD)", id="f-date-from")
                yield Input(placeholder="To (YYYY-MM-DD)", id="f-date-to")
            yield Label("Presets:")
            with Horizontal(id="preset-row"):
                yield Button("7d", id="preset-7d")
                yield Button("30d", id="preset-30d")
                yield Button("90d", id="preset-90d")
                yield Button("All year", id="preset-year")
                yield Button("Clear", id="preset-clear")
            with Horizontal():
                yield Button("Apply", variant="primary", id="f-apply")
                yield Button("Reset", id="f-reset")
                yield Button("Cancel", id="f-cancel")

    def _get_filters(self) -> dict:
        """Read all form fields and return as a flat dict."""
        ftype = self.query_one("#f-type", Select).value
        visibility = self.query_one("#f-visibility", Select).value
        return {
            "name": self.query_one("#f-name", Input).value,
            "content": self.query_one("#f-content", Input).value,
            "file_type": ftype if ftype and ftype != "" else None,
            "visibility": visibility if visibility != "all" else None,
            "date_from": self.query_one("#f-date-from", Input).value or None,
            "date_to": self.query_one("#f-date-to", Input).value or None,
        }

    @on(Button.Pressed)
    def handle_filter_buttons(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "f-apply":
            self.dismiss(self._get_filters())
        elif btn_id == "f-reset":
            self.dismiss({})
        elif btn_id == "f-cancel":
            self.dismiss(None)
        elif btn_id in ("preset-7d", "preset-30d", "preset-90d"):
            days = {"preset-7d": 7, "preset-30d": 30, "preset-90d": 90}[btn_id]
            from_date = (date.today() - timedelta(days=days)).isoformat()
            self.query_one("#f-date-from", Input).value = from_date
            self.query_one("#f-date-to", Input).value = date.today().isoformat()
        elif btn_id == "preset-year":
            self.query_one("#f-date-from", Input).value = date(
                date.today().year, 1, 1
            ).isoformat()
            self.query_one("#f-date-to", Input).value = date.today().isoformat()
        elif btn_id == "preset-clear":
            self.query_one("#f-date-from", Input).value = ""
            self.query_one("#f-date-to", Input).value = ""
