"""Auto-dismissing notification bar widget."""

from textual.widgets import Static


class Notification(Static):
    """Floating notification that auto-removes after 3 seconds."""

    def on_mount(self) -> None:
        self.set_timer(3, self.remove)
