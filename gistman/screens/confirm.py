"""Reusable Yes/No confirmation modal."""

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmModal(ModalScreen[bool]):
    """Ask the user to confirm a destructive action.

    Returns True if the user clicked "Yes", False otherwise.
    """

    CSS = """
    ConfirmModal {
        align: center middle;
    }
    .confirm-dialog {
        width: 40;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }
    .confirm-dialog > .title {
        text-style: bold;
        margin-bottom: 1;
    }
    .confirm-dialog Horizontal {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel", show=False),
    ]

    def __init__(self, message: str = "Are you sure?") -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="confirm-dialog"):
            yield Label(self._message, classes="title")
            with Horizontal():
                yield Button("Yes", variant="error", id="confirm-yes")
                yield Button("No", id="confirm-no")

    def action_dismiss_modal(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed)
    def handle_confirm(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)
