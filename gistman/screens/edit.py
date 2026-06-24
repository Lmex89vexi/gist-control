"""Create / Edit gist form — description, visibility, dynamic file list."""

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, RadioButton, RadioSet

from gistman.config import edit_files_in_editor
from gistman.log import logger
from gistman.store import IStore


class EditScreen(Screen):
    """Screen for creating a new gist or editing an existing one.

    Mode is set via ``mode="create"`` or ``mode="edit"``; the latter
    requires ``gist_id`` to pre-populate the form.

    File contents are edited externally via the ``Edit ↵`` button,
    which opens the user's configured editor (neovim by default).
    """

    CSS = """
    EditScreen {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    def action_cancel(self) -> None:
        self.app.pop_screen()

    def action_cursor_down(self) -> None:
        lv = self.query_one("#edit-file-list", ListView)
        if lv.index is not None and lv.index < len(self._files) - 1:
            lv.index = lv.index + 1

    def action_cursor_up(self) -> None:
        lv = self.query_one("#edit-file-list", ListView)
        if lv.index is not None and lv.index > 0:
            lv.index = lv.index - 1

    def __init__(
        self,
        mode: str = "create",
        gist_id: str | None = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.gist_id = gist_id
        self._files: list[dict] = []

    def compose(self) -> ComposeResult:
        store: IStore = self.app.store
        title = "Edit Gist" if self.mode == "edit" else "Create Gist"
        with Vertical(classes="edit-dialog"):
            yield Label(title, classes="title")
            yield Input(
                placeholder="Description",
                id="edit-desc",
            )
            with Horizontal():
                yield Label("Visibility: ")
                yield RadioSet(
                    RadioButton("Secret", value=True, id="vis-secret"),
                    RadioButton("Public", id="vis-public"),
                    id="edit-visibility",
                )

            yield Label("Files:")
            with Vertical(id="edit-files"):
                yield ListView(id="edit-file-list")

            with Horizontal(id="edit-file-actions"):
                yield Input(placeholder="filename.txt", id="new-filename")
                yield Button("+ Add", id="add-file")
                yield Button("- Remove", id="rm-file")

            with Horizontal(id="edit-actions"):
                yield Button("Edit ↵", id="edit-ext-btn")
                yield Button("Save", variant="primary", id="edit-save")
                yield Button("Cancel", id="edit-cancel")

    def on_mount(self) -> None:
        if self.mode == "edit" and self.gist_id:
            store: IStore = self.app.store
            gist = store.get_gist(self.gist_id)
            if gist:
                self.query_one("#edit-desc", Input).value = gist.get("description", "")
                vis = gist.get("visibility", "secret")
                rs = self.query_one("#edit-visibility", RadioSet)
                rs.query_one("#vis-secret", RadioButton).value = vis == "secret"
                rs.query_one("#vis-public", RadioButton).value = vis == "public"

                files = list(gist["files"].values())
                self._files = [
                    {"filename": f["filename"], "content": f.get("content", "")}
                    for f in files
                ]
                self._rebuild_file_list()

    def _rebuild_file_list(self) -> None:
        lv = self.query_one("#edit-file-list", ListView)
        lv.clear()
        for f in self._files:
            lv.append(ListItem(Label(f["filename"])))
        if self._files:
            lv.index = len(self._files) - 1

    @on(ListView.Selected)
    def on_file_selected(self, event: ListView.Selected) -> None:
        if event.item:
            idx = list(self.query_one("#edit-file-list", ListView).children).index(
                event.item
            )

    @on(Input.Submitted, "#new-filename")
    def on_filename_submit(self) -> None:
        self.add_file()

    @on(Button.Pressed, "#add-file")
    def add_file(self) -> None:
        inp = self.query_one("#new-filename", Input)
        name = inp.value.strip() or "untitled.txt"
        self._files.append({"filename": name, "content": ""})
        self._rebuild_file_list()
        inp.value = ""

    @on(Button.Pressed, "#rm-file")
    def remove_file(self) -> None:
        lv = self.query_one("#edit-file-list", ListView)
        if lv.index is not None and 0 <= lv.index < len(self._files):
            self._files.pop(lv.index)
            self._rebuild_file_list()

    @on(Button.Pressed, "#edit-ext-btn")
    def edit_external(self) -> None:
        if not self._files:
            self.app.notify("No files to edit", severity="warning")
            return
        try:
            with self.app.suspend():
                updated = edit_files_in_editor(self._files)
            self._files = updated
            self._rebuild_file_list()
            logger.info("Files updated via external editor ({})", len(updated))
            self.app.notify("Files updated from editor", severity="information")
        except RuntimeError as e:
            self.app.notify(f"Editor failed: {e}", severity="error")

    @on(Button.Pressed, "#edit-save")
    async def save(self) -> None:
        desc = self.query_one("#edit-desc", Input).value
        files = [(f["filename"], f["content"]) for f in self._files if f["filename"].strip()]
        rs = self.query_one("#edit-visibility", RadioSet)
        public = rs.pressed_index == 1

        store: IStore = self.app.store
        try:
            if self.mode == "create":
                await store.create_gist(desc, files, public)
                logger.info("Gist created via EditScreen")
                self.app.notify("Gist created!", severity="information")
            elif self.mode == "edit" and self.gist_id:
                await store.update_gist(self.gist_id, desc, files)
                logger.info("Gist {} updated via EditScreen", self.gist_id)
                self.app.notify("Gist updated!", severity="information")
            self.app.pop_screen()
        except RuntimeError as e:
            logger.exception("Failed to save gist")
            self.app.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#edit-cancel")
    def cancel(self) -> None:
        self.app.pop_screen()
