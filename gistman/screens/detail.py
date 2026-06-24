"""Gist detail view — file tabs, syntax-highlighted content, meta, actions."""

import subprocess
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, TextArea

from gistman.config import edit_files_in_editor
from gistman.constants import LANGUAGE_MAP
from gistman.log import logger
from gistman.screens.confirm import ConfirmModal
from gistman.screens.edit import EditScreen
from gistman.store import IStore


class DetailScreen(Screen):
    """View a single gist: browse files, read content, and perform actions.

    Actions: Edit, Copy URL, Bookmark, Clone, Open in Browser, Delete.
    """

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_cursor_down(self) -> None:
        lv = self.query_one("#file-list", ListView)
        if lv.index is not None and lv.index < lv.child_count - 1:
            lv.index = lv.index + 1

    def action_cursor_up(self) -> None:
        lv = self.query_one("#file-list", ListView)
        if lv.index is not None and lv.index > 0:
            lv.index = lv.index - 1

    def __init__(self, gist_id: str) -> None:
        super().__init__()
        self.gist_id = gist_id
        self._current_file: str | None = None

    def compose(self) -> ComposeResult:
        store: IStore = self.app.store
        gist = store.get_gist(self.gist_id)
        desc = (gist or {}).get("description", "") or "(no description)"

        with Container(classes="detail-container"):
            with Horizontal(classes="detail-header"):
                yield Button("← Back", id="back-btn")
                yield Label(desc, id="detail-title")
            with Horizontal(classes="detail-body"):
                yield ListView(id="file-list", classes="detail-files")
                yield TextArea(
                    id="detail-text",
                    classes="detail-content",
                    read_only=True,
                )
            with Horizontal(classes="detail-meta"):
                yield Label("", id="detail-meta-left")
                yield Label("", id="detail-meta-right")
            with Horizontal(classes="detail-actions"):
                yield Button("Edit", id="edit-btn")
                yield Button("Edit ↵", id="edit-ext-btn")
                yield Button("Copy URL", id="copy-btn")
                yield Button(
                    "⋆" if store and self.gist_id in store.bookmarks else "☆",
                    id="bookmark-btn",
                )
                yield Button("Clone", id="clone-btn")
                yield Button("Open in Browser", id="open-btn")
                yield Button("Delete", variant="error", id="delete-btn")

    def on_mount(self) -> None:
        store: IStore = self.app.store
        gist = store.get_gist(self.gist_id)
        if not gist:
            return

        files = list(gist["files"].values())
        lv = self.query_one("#file-list", ListView)
        for f in files:
            lv.append(ListItem(Label(f["filename"])))

        if files:
            lv.index = 0
            self._show_file(files[0])

        self._update_meta(gist)

        # If content hasn't been fetched yet, show a placeholder and fetch
        if not any(f.get("content") for f in files):
            ta = self.query_one("#detail-text", TextArea)
            ta.text = "⏳ Loading content from GitHub..."
            self.app.call_later(self._fetch_content)

    async def _fetch_content(self) -> None:
        """Lazy-load full gist content from the API."""
        store: IStore = self.app.store
        await store.fetch_content(self.gist_id)
        gist = store.get_gist(self.gist_id)
        if gist:
            files = list(gist["files"].values())
            lv = self.query_one("#file-list", ListView)
            if lv.index is not None and 0 <= lv.index < len(files):
                self._show_file(files[lv.index])
            self._update_meta(gist)

    def _show_file(self, f: dict) -> None:
        """Display the given file's content with appropriate syntax highlighting."""
        ta = self.query_one("#detail-text", TextArea)
        content = f.get("content", "")
        if f.get("truncated"):
            content += "\n\n# ⚠ Content truncated by GitHub API"
        ta.text = content
        ext = Path(f["filename"]).suffix.lower()
        lang = LANGUAGE_MAP.get(ext)
        if lang:
            ta.language = lang
        self._current_file = f["filename"]

    def _update_meta(self, gist: dict) -> None:
        """Refresh the metadata bar (dates, file count, line count, visibility)."""
        files = list(gist["files"].values())
        total_lines = sum(
            f.get("content", "").count("\n") + 1 for f in files if f.get("content")
        )
        created = gist.get("created_at", "")[:10]
        updated = gist.get("updated_at", "")[:10]
        vis = gist.get("visibility", "")
        left = self.query_one("#detail-meta-left", Label)
        right = self.query_one("#detail-meta-right", Label)
        left.update(f"Created: {created}  |  Updated: {updated}  |  Files: {len(files)}")
        right.update(f"Lines: {total_lines:,}  |  {vis}")

    # ── Event handlers ────────────────────────────────────────────────────

    @on(ListView.Selected, "#file-list")
    def on_file_selected(self, event: ListView.Selected) -> None:
        store: IStore = self.app.store
        gist = store.get_gist(self.gist_id)
        if gist and event.item:
            idx = list(self.query_one("#file-list", ListView).children).index(
                event.item
            )
            files = list(gist["files"].values())
            if 0 <= idx < len(files):
                self._show_file(files[idx])

    @on(Button.Pressed, "#back-btn")
    def go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#edit-btn")
    def edit_gist(self) -> None:
        self.app.push_screen(EditScreen(mode="edit", gist_id=self.gist_id))

    @on(Button.Pressed, "#edit-ext-btn")
    async def edit_external(self) -> None:
        store: IStore = self.app.store
        gist = store.get_gist(self.gist_id)
        if not gist:
            return

        if not any(f.get("content") for f in gist["files"].values()):
            self.app.notify("Fetching content…", severity="information")
            await store.fetch_content(self.gist_id)
            gist = store.get_gist(self.gist_id)
            if not gist:
                return

        files = [
            {"filename": f["filename"], "content": f.get("content", "")}
            for f in gist["files"].values()
        ]

        try:
            with self.app.suspend():
                updated = edit_files_in_editor(files)
            update_files = [(f["filename"], f["content"]) for f in updated]
            await store.update_gist(self.gist_id, files=update_files)
            logger.info("Gist {} updated via external editor", self.gist_id)
            self.app.notify("Gist updated!", severity="information")
            gist = store.get_gist(self.gist_id)
            if gist:
                files_list = list(gist["files"].values())
                lv = self.query_one("#file-list", ListView)
                lv.clear()
                for f in files_list:
                    lv.append(ListItem(Label(f["filename"])))
                if files_list:
                    lv.index = 0
                    self._show_file(files_list[0])
                self._update_meta(gist)
        except RuntimeError as e:
            self.app.notify(f"Edit failed: {e}", severity="error")

    @on(Button.Pressed, "#copy-btn")
    def copy_url(self) -> None:
        store: IStore = self.app.store
        url = f"https://gist.github.com/{self.gist_id}"
        if store.copy_to_clipboard(url):
            self.app.notify("URL copied!", severity="information")
        else:
            self.app.notify("Clipboard not available", severity="warning")

    @on(Button.Pressed, "#bookmark-btn")
    def toggle_bookmark(self) -> None:
        store: IStore = self.app.store
        btn = self.query_one("#bookmark-btn", Button)
        if self.gist_id in store.bookmarks:
            store.bookmarks.discard(self.gist_id)
            btn.label = "☆"
            self.app.notify("Bookmark removed", severity="information")
        else:
            store.bookmarks.add(self.gist_id)
            btn.label = "⋆"
            self.app.notify("Bookmarked!", severity="information")
        store.save_cache()

    @on(Button.Pressed, "#clone-btn")
    async def clone_gist(self) -> None:
        try:
            store: IStore = self.app.store
            result = await store._run_gh(["gist", "clone", self.gist_id])
            lines = result.strip().split("\n")
            last_line = lines[-1] if lines else ""
            self.app.notify(f"Cloned: {last_line}", severity="information")
        except RuntimeError as e:
            self.app.notify(f"Clone failed: {e}", severity="error")

    @on(Button.Pressed, "#open-btn")
    def open_in_browser(self) -> None:
        url = f"https://gist.github.com/{self.gist_id}"
        try:
            subprocess.Popen(["xdg-open", url])
        except FileNotFoundError:
            self.app.notify(f"URL: {url}", severity="information")

    @on(Button.Pressed, "#delete-btn")
    def delete_gist(self) -> None:
        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self.app.call_later(self._do_delete)
        self.app.push_screen(ConfirmModal("Delete this gist forever?"), on_confirm)

    async def _do_delete(self) -> None:
        store: IStore = self.app.store
        try:
            await store.delete_gist(self.gist_id)
            logger.info("Gist {} deleted via DetailScreen", self.gist_id)
            self.app.notify("Gist deleted", severity="information")
            self.app.pop_screen()
        except RuntimeError as e:
            logger.exception("Failed to delete gist {}", self.gist_id)
            self.app.notify(f"Delete failed: {e}", severity="error")
