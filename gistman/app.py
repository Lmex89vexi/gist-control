"""Application entry point — wires the TUI together."""

from textual.app import App
from textual.binding import Binding

from gistman.css import APP_CSS
from gistman.log import logger
from gistman.screens.main import MainScreen
from gistman.store import GistStore


class GistManager(App):
    """Root Textual application.

    Owns a single ``GistStore`` instance shared by all screens.
    """

    CSS = APP_CSS
    TITLE = "Gist Manager"
    SUB_TITLE = "Manage your GitHub Gists"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.store = GistStore()

    def on_mount(self) -> None:
        logger.info("GistManager started — {} cached gists", len(self.store.gists))
        self.push_screen(MainScreen())

    def action_help(self) -> None:
        self.notify(
            "Ctrl+F:Search  Ctrl+N:New  Ctrl+O:Filters  "
            "Ctrl+R:Refresh  Ctrl+S:Stats  Ctrl+B:Bookmarks  "
            "Enter:View  Esc:Back  ?:Help  Q:Quit",
            title="Keyboard Shortcuts",
            severity="information",
        )


# Module-level singleton for the pyproject.toml entry point.
app = GistManager()


def main() -> None:
    """CLI entry point — launch the TUI."""
    logger.info("Starting gistman…")
    app.run()
