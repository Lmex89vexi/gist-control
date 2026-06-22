#!/usr/bin/env python3
"""gistman — Interactive TUI for managing GitHub Gists."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import time
from collections import Counter
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll, Container
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen
from textual.theme import Theme
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label, ListItem,
    ListView, LoadingIndicator, RadioButton, RadioSet, RichLog,
    Select, Static, TabbedContent, TabPane, TextArea,
)

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

# ─── Constants ───────────────────────────────────────────────────────────────

CACHE_DIR = Path.home() / ".cache" / "gistman"
CACHE_FILE = CACHE_DIR / "gists.json"
CACHE_TTL = 300
GH_CMD = "gh"

LANGUAGE_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".md": "markdown", ".sh": "bash",
    ".bash": "bash", ".ps1": "powershell", ".txt": None,
    ".csv": None, ".xml": "xml", ".html": "html", ".css": "css",
    ".go": "go", ".rs": "rust", ".java": "java",
}


# ─── Gist Store (Data Layer) ────────────────────────────────────────────────

class GistStore:
    def __init__(self) -> None:
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.gists: dict[str, dict] = {}
        self.bookmarks: set[str] = set()
        self.clipboard_history: list[str] = []
        self.cached_at: float = 0
        self._loading_content: set[str] = set()
        self._error: str | None = None
        self.load_cache()

    def load_cache(self) -> None:
        if not CACHE_FILE.exists():
            return
        try:
            data = json.loads(CACHE_FILE.read_text())
            self.gists = data.get("gists", {})
            self.bookmarks = set(data.get("bookmarks", []))
            self.clipboard_history = data.get("clipboard_history", [])
            self.cached_at = data.get("cached_at", 0)
        except (json.JSONDecodeError, KeyError):
            pass

    def save_cache(self) -> None:
        data = {
            "cached_at": self.cached_at or time.time(),
            "gists": self.gists,
            "bookmarks": list(self.bookmarks),
            "clipboard_history": self.clipboard_history,
        }
        CACHE_FILE.write_text(json.dumps(data, indent=2, default=str))

    @property
    def is_stale(self) -> bool:
        return time.time() - self.cached_at > CACHE_TTL

    @property
    def error(self) -> str | None:
        return self._error

    async def _run_gh(self, args: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            GH_CMD, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            msg = stderr.decode().strip()
            raise RuntimeError(f"gh {' '.join(args)} failed: {msg}")
        return stdout.decode().strip()

    async def refresh_list(self) -> int:
        self._error = None
        try:
            all_gists: list[dict] = []

            page = 1
            while True:
                result = await self._run_gh([
                    "api", f"gists?per_page=100&page={page}",
                ])
                batch = json.loads(result)
                if not batch:
                    break
                all_gists.extend(batch)
                if len(batch) < 100:
                    break
                page += 1

            current_ids: set[str] = set()
            for g in all_gists:
                gid = g["id"]
                current_ids.add(gid)
                files_dict: dict[str, dict] = {}
                for fname, fdata in g.get("files", {}).items():
                    ext = Path(fname).suffix.lower()
                    files_dict[fname] = {
                        "filename": fname,
                        "language": LANGUAGE_MAP.get(ext, fdata.get("language")),
                        "raw_url": fdata.get("raw_url", ""),
                        "size": fdata.get("size", 0),
                        "type": fdata.get("type", ""),
                        "content": (
                            self.gists.get(gid, {})
                            .get("files", {})
                            .get(fname, {})
                            .get("content", "")
                        ),
                    }

                self.gists[gid] = {
                    "id": gid,
                    "description": g.get("description", ""),
                    "files": files_dict,
                    "created_at": g.get("created_at", ""),
                    "updated_at": g.get("updated_at", ""),
                    "visibility": "public" if g.get("public") else "secret",
                }

            for gid in list(self.gists.keys()):
                if gid not in current_ids:
                    del self.gists[gid]

            self.bookmarks &= current_ids
            self.cached_at = time.time()
            self.save_cache()
            return len(all_gists)
        except RuntimeError as e:
            self._error = str(e)
            raise
        except json.JSONDecodeError as e:
            self._error = f"Invalid response: {e}"
            raise

    async def fetch_content(self, gist_id: str) -> None:
        if gist_id in self._loading_content:
            return
        self._loading_content.add(gist_id)
        try:
            result = await self._run_gh(["api", f"gists/{gist_id}"])
            data = json.loads(result)
            if gist_id in self.gists:
                g = self.gists[gist_id]
                for fname, fdata in data.get("files", {}).items():
                    if fname in g["files"]:
                        g["files"][fname]["content"] = fdata.get("content", "")
                        g["files"][fname]["size"] = fdata.get("size", 0)
                        g["files"][fname]["truncated"] = fdata.get("truncated", False)
                self.save_cache()
        except RuntimeError:
            pass
        finally:
            self._loading_content.discard(gist_id)

    def get_list_data(self) -> list[dict]:
        items: list[dict] = []
        for g in self.gists.values():
            files = list(g["files"].values())
            file_types: list[str] = []
            total_lines = 0
            for f in files:
                ext = Path(f["filename"]).suffix.lower() or "unknown"
                file_types.append(ext)
                content = f.get("content")
                if content:
                    total_lines += content.count("\n") + 1
                elif f.get("size") and f["size"] > 0:
                    total_lines += max(1, f["size"] // 40)
            items.append({
                "id": g["id"],
                "description": g.get("description", "") or "(no description)",
                "files": files,
                "file_types": file_types,
                "file_count": len(files),
                "total_lines": total_lines,
                "created_at": g.get("created_at", ""),
                "updated_at": g.get("updated_at", ""),
                "visibility": g.get("visibility", "secret"),
                "bookmarked": g["id"] in self.bookmarks,
                "has_content": any(f.get("content") for f in files),
            })
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return items

    def search(
        self,
        query: str = "",
        content: str = "",
        file_types: list[str] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        visibility: str | None = None,
        bookmarks_only: bool = False,
    ) -> list[dict]:
        items = self.get_list_data()
        query = query.lower().strip()
        content = content.lower().strip()

        results: list[dict] = []
        for item in items:
            g = self.gists[item["id"]]

            if bookmarks_only and not item["bookmarked"]:
                continue

            if visibility and visibility != "all" and item["visibility"] != visibility:
                continue

            if query:
                desc_match = query in item["description"].lower()
                name_match = any(
                    query in f["filename"].lower() for f in item["files"]
                )
                if not desc_match and not name_match:
                    continue

            if content:
                content_match = False
                for f in g.get("files", {}).values():
                    fcontent = f.get("content", "")
                    if content in fcontent.lower():
                        content_match = True
                        break
                if not content_match:
                    continue

            if file_types:
                item_types = set(item["file_types"])
                if not item_types.intersection(file_types):
                    continue

            if date_from or date_to:
                try:
                    dt = datetime.fromisoformat(
                        item["updated_at"].replace("Z", "+00:00")
                    )
                    if date_from and dt.date() < date_from:
                        continue
                    if date_to and dt.date() > date_to:
                        continue
                except (ValueError, AttributeError):
                    pass

            results.append(item)

        return results

    async def create_gist(
        self,
        description: str,
        files: list[tuple[str, str]],
        public: bool = False,
    ) -> str:
        payload = {
            "description": description,
            "public": public,
            "files": {name: {"content": content} for name, content in files},
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        try:
            json.dump(payload, tmp)
            tmp.close()
            result = await self._run_gh([
                "api", "-X", "POST", "gists", "--input", tmp.name,
            ])
            data = json.loads(result)
            gist_id = data["id"]
            await self.refresh_list()
            await self.fetch_content(gist_id)
            return gist_id
        finally:
            os.unlink(tmp.name)

    async def update_gist(
        self,
        gist_id: str,
        description: str | None = None,
        files: list[tuple[str, str]] | None = None,
    ) -> None:
        payload: dict[str, Any] = {}
        if description is not None:
            payload["description"] = description
        if files is not None:
            payload["files"] = {name: {"content": content} for name, content in files}
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        try:
            json.dump(payload, tmp)
            tmp.close()
            await self._run_gh([
                "api", "-X", "PATCH", f"gists/{gist_id}", "--input", tmp.name,
            ])
            await self.fetch_content(gist_id)
            self.save_cache()
        finally:
            os.unlink(tmp.name)

    async def delete_gist(self, gist_id: str) -> None:
        await self._run_gh(["gist", "delete", gist_id])
        self.gists.pop(gist_id, None)
        self.bookmarks.discard(gist_id)
        self.save_cache()

    def get_gist(self, gist_id: str) -> dict | None:
        return self.gists.get(gist_id)

    def get_stats(self) -> dict:
        items = self.get_list_data()
        total_gists = len(items)
        total_files = sum(i["file_count"] for i in items)
        total_lines = sum(i["total_lines"] for i in items)

        type_counter: Counter[str] = Counter()
        for item in items:
            for t in item["file_types"]:
                type_counter[t] += 1

        months: Counter[str] = Counter()
        for item in items:
            try:
                dt = datetime.fromisoformat(
                    item["created_at"].replace("Z", "+00:00")
                )
                months[dt.strftime("%Y-%m")] += 1
            except (ValueError, AttributeError):
                pass

        return {
            "total_gists": total_gists,
            "total_files": total_files,
            "total_lines": total_lines,
            "file_types": type_counter.most_common(10),
            "months": dict(sorted(months.items())),
            "bookmarked_count": len(self.bookmarks),
            "avg_files": round(total_files / total_gists, 1) if total_gists else 0,
            "avg_lines": round(total_lines / total_files, 1) if total_files else 0,
        }

    def copy_to_clipboard(self, text: str) -> bool:
        if HAS_CLIPBOARD:
            try:
                pyperclip.copy(text)
                self.clipboard_history.append(text)
                if len(self.clipboard_history) > 50:
                    self.clipboard_history = self.clipboard_history[-50:]
                self.save_cache()
                return True
            except Exception:
                pass

        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(text.encode())
            if proc.returncode == 0:
                self.clipboard_history.append(text)
                self.save_cache()
                return True
        except FileNotFoundError:
            pass

        try:
            proc = subprocess.Popen(
                ["wl-copy"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
            proc.communicate(text.encode())
            if proc.returncode == 0:
                self.clipboard_history.append(text)
                self.save_cache()
                return True
        except FileNotFoundError:
            pass

        return False


# ─── CSS ─────────────────────────────────────────────────────────────────────

APP_CSS = """
Screen {
    background: #1a1b26;
}

MainScreen {
    layout: vertical;
}

#search-row {
    dock: top;
    height: 3;
    padding: 0 1;
    align: center middle;
}

#search-input {
    width: 60%;
}

#refresh-btn {
    width: 12;
    margin-left: 1;
}

#filter-bar {
    dock: top;
    height: 1;
    padding: 0 1;
    color: #565f89;
}

#filter-bar Label {
    padding: 0 1;
}

#gist-count {
    dock: top;
    height: 1;
    padding: 0 1;
    color: #565f89;
}

DataTable {
    height: 1fr;
    margin: 0 1;
}

DataTable > .datatable--header {
    color: #7aa2f7;
    background: #1f2335;
}

DataTable > .datatable--cursor {
    background: #3b4261;
}

Footer {
    background: #1f2335;
    color: #a9b1d6;
}

.detail-container {
    layout: vertical;
    height: 100%;
}

.detail-header {
    dock: top;
    height: 3;
    padding: 0 1;
    align: center middle;
}

.detail-header Label {
    width: 1fr;
}

.detail-body {
    height: 1fr;
}

.detail-meta {
    dock: bottom;
    height: 4;
    padding: 0 1;
    background: #1f2335;
}

.detail-files {
    width: 20;
    dock: left;
    background: #1f2335;
}

.detail-content {
    height: 1fr;
}

.detail-actions {
    dock: bottom;
    height: 3;
    padding: 0 1;
    align: center middle;
}

.detail-actions Button {
    margin: 0 1;
}

.filter-dialog {
    width: 50;
    height: auto;
    padding: 1 2;
    background: #1f2335;
    border: thick #565f89;
    margin: 1 2;
}

.filter-dialog > .title {
    text-style: bold;
    color: #7aa2f7;
    padding-bottom: 1;
}

.filter-dialog Input,
.filter-dialog Select {
    margin-bottom: 1;
}

.filter-dialog > Horizontal {
    height: 3;
    align: center middle;
}

.filter-dialog Button {
    margin: 0 1;
}

.edit-dialog {
    width: 80%;
    height: 85%;
    padding: 1 2;
    background: #1f2335;
    border: thick #565f89;
}

.edit-dialog > .title {
    text-style: bold;
    color: #7aa2f7;
    padding-bottom: 1;
}

.edit-dialog Input {
    margin-bottom: 1;
}

#edit-files {
    height: 1fr;
    border: solid #3b4261;
    margin-bottom: 1;
}

#edit-actions {
    dock: bottom;
    height: 3;
    align: center middle;
}

#edit-actions Button {
    margin: 0 1;
}

.stats-dialog {
    width: 60;
    height: auto;
    padding: 1 2;
    background: #1f2335;
    border: thick #565f89;
}

.stats-dialog > .title {
    text-style: bold;
    color: #7aa2f7;
    padding-bottom: 1;
}

.stats-dialog > .stat-row {
    height: 1;
    padding: 0 1;
}

.stats-dialog Button {
    dock: bottom;
    margin-top: 1;
    align: center middle;
}

#file-tabs {
    height: 100%;
}

Label.loading {
    color: #565f89;
    text-style: italic;
}

Button {
    background: #3b4261;
    color: #a9b1d6;
}

Button:hover {
    background: #565f89;
}

Button.-primary {
    background: #7aa2f7;
    color: #1a1b26;
}

Button.-error {
    background: #f7768e;
    color: #1a1b26;
}

#empty-state {
    align: center middle;
    height: 1fr;
    color: #565f89;
}

TextArea {
    background: #1f2335;
    color: #a9b1d6;
}

Select {
    background: #1f2335;
}
"""


# ─── Notification ───────────────────────────────────────────────────────────

class Notification(Static):
    """Auto-dismissing notification bar."""

    def on_mount(self) -> None:
        self.set_timer(3, self.remove)


# ─── Filter Modal ───────────────────────────────────────────────────────────

class FilterModal(ModalScreen[dict | None]):
    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel", show=False),
    ]

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

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
        name_q = self.query_one("#f-name", Input).value
        content_q = self.query_one("#f-content", Input).value
        ftype = self.query_one("#f-type", Select).value
        visibility = self.query_one("#f-visibility", Select).value
        date_from = self.query_one("#f-date-from", Input).value
        date_to = self.query_one("#f-date-to", Input).value
        return {
            "name": name_q,
            "content": content_q,
            "file_type": ftype if ftype and ftype != "" else None,
            "visibility": visibility if visibility != "all" else None,
            "date_from": date_from if date_from else None,
            "date_to": date_to if date_to else None,
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


# ─── Stats Modal ────────────────────────────────────────────────────────────

class StatsModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close_stats", "Close", show=False),
    ]

    def action_close_stats(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        store: GistStore = self.app.store
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


# ─── Edit Screen (Create / Edit Gist) ───────────────────────────────────────

class EditScreen(Screen):
    CSS = """
    EditScreen {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def action_cancel(self) -> None:
        self.app.pop_screen()

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
        store: GistStore = self.app.store
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
                yield TextArea(id="edit-content", language="python")

            with Horizontal(id="edit-file-actions"):
                yield Button("+ Add File", id="add-file")
                yield Button("- Remove File", id="rm-file")

            with Horizontal(id="edit-actions"):
                yield Button("Save", variant="primary", id="edit-save")
                yield Button("Cancel", id="edit-cancel")

    def on_mount(self) -> None:
        if self.mode == "edit" and self.gist_id:
            store: GistStore = self.app.store
            gist = store.get_gist(self.gist_id)
            if gist:
                self.query_one("#edit-desc", Input).value = gist.get("description", "")
                vis = gist.get("visibility", "secret")
                rs = self.query_one("#edit-visibility", RadioSet)
                if vis == "secret":
                    rs.index = 0
                else:
                    rs.index = 1

                files = list(gist["files"].values())
                self._files = [
                    {
                        "filename": f["filename"],
                        "content": f.get("content", ""),
                    }
                    for f in files
                ]
                self._rebuild_file_list()
                if self._files:
                    self._select_file(0)

    def _rebuild_file_list(self) -> None:
        lv = self.query_one("#edit-file-list", ListView)
        lv.clear()
        for f in self._files:
            lv.append(ListItem(Label(f["filename"])))
        if self._files:
            lv.index = len(self._files) - 1
            self._select_file(len(self._files) - 1)

    def _select_file(self, index: int) -> None:
        if not self._files or index < 0 or index >= len(self._files):
            return
        f = self._files[index]
        ta = self.query_one("#edit-content", TextArea)
        ta.text = f["content"]
        ext = Path(f["filename"]).suffix.lower()
        lang = LANGUAGE_MAP.get(ext)
        if lang:
            ta.language = lang

    @on(ListView.Selected)
    def on_file_selected(self, event: ListView.Selected) -> None:
        if event.item:
            idx = list(self.query_one("#edit-file-list", ListView).children).index(
                event.item
            )
            self._select_file(idx)

    @on(Button.Pressed, "#add-file")
    def add_file(self) -> None:
        name = f"file{len(self._files) + 1}.txt"
        for i in range(1, 100):
            candidate = f"untitled{i}.txt"
            if not any(f["filename"] == candidate for f in self._files):
                name = candidate
                break
        self._files.append({"filename": name, "content": ""})
        self._rebuild_file_list()

    @on(Button.Pressed, "#rm-file")
    def remove_file(self) -> None:
        lv = self.query_one("#edit-file-list", ListView)
        if lv.index is not None and 0 <= lv.index < len(self._files):
            self._files.pop(lv.index)
            self._rebuild_file_list()

    @on(Button.Pressed, "#edit-save")
    async def save(self) -> None:
        lv = self.query_one("#edit-file-list", ListView)
        ta = self.query_one("#edit-content", TextArea)
        if lv.index is not None and 0 <= lv.index < len(self._files):
            self._files[lv.index]["content"] = ta.text

        desc = self.query_one("#edit-desc", Input).value
        files = [(f["filename"], f["content"]) for f in self._files if f["filename"].strip()]
        rs = self.query_one("#edit-visibility", RadioSet)
        public = rs.index == 1

        store: GistStore = self.app.store
        try:
            if self.mode == "create":
                await store.create_gist(desc, files, public)
                self.app.notify("Gist created!", severity="information")
            elif self.mode == "edit" and self.gist_id:
                await store.update_gist(self.gist_id, desc, files)
                self.app.notify("Gist updated!", severity="information")
            self.app.pop_screen()
        except RuntimeError as e:
            self.app.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#edit-cancel")
    def cancel(self) -> None:
        self.app.pop_screen()


# ─── Detail Screen ──────────────────────────────────────────────────────────

class DetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
    ]

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def __init__(self, gist_id: str) -> None:
        super().__init__()
        self.gist_id = gist_id
        self._current_file: str | None = None

    def compose(self) -> ComposeResult:
        store: GistStore = self.app.store
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
                yield Button("Copy URL", id="copy-btn")
                if HAS_CLIPBOARD or True:
                    pass
                yield Button(
                    "⋆" if store and self.gist_id in store.bookmarks else "☆",
                    id="bookmark-btn",
                )
                yield Button("Clone", id="clone-btn")
                yield Button("Open in Browser", id="open-btn")
                yield Button("Delete", variant="error", id="delete-btn")

    def on_mount(self) -> None:
        store: GistStore = self.app.store
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

        if not any(f.get("content") for f in files):
            ta = self.query_one("#detail-text", TextArea)
            ta.text = "⏳ Loading content from GitHub..."
            self.app.call_later(self._fetch_content)

    async def _fetch_content(self) -> None:
        store: GistStore = self.app.store
        await store.fetch_content(self.gist_id)
        gist = store.get_gist(self.gist_id)
        if gist:
            files = list(gist["files"].values())
            lv = self.query_one("#file-list", ListView)
            if lv.index is not None and 0 <= lv.index < len(files):
                self._show_file(files[lv.index])
            self._update_meta(gist)

    def _show_file(self, f: dict) -> None:
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

    @on(ListView.Selected, "#file-list")
    def on_file_selected(self, event: ListView.Selected) -> None:
        store: GistStore = self.app.store
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

    @on(Button.Pressed, "#copy-btn")
    def copy_url(self) -> None:
        store: GistStore = self.app.store
        url = f"https://gist.github.com/{self.gist_id}"
        if store.copy_to_clipboard(url):
            self.app.notify("URL copied!", severity="information")
        else:
            self.app.notify("Clipboard not available", severity="warning")

    @on(Button.Pressed, "#bookmark-btn")
    def toggle_bookmark(self) -> None:
        store: GistStore = self.app.store
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
            store: GistStore = self.app.store
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
    async def delete_gist(self) -> None:
        store: GistStore = self.app.store
        try:
            await store.delete_gist(self.gist_id)
            self.app.notify("Gist deleted", severity="information")
            self.app.pop_screen()
        except RuntimeError as e:
            self.app.notify(f"Delete failed: {e}", severity="error")


# ─── Main Screen ────────────────────────────────────────────────────────────

class MainScreen(Screen):
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
        table = self.query_one("#gist-table", DataTable)
        table.add_columns("", "Name", "Type", "Updated", "Files", "Lines")
        self._load_data()
        if self.app.store.is_stale or not self.app.store.gists:
            self.call_later(self._initial_refresh)

    def _load_data(self) -> None:
        self._apply_filters()

    def _to_filter_args(self) -> dict:
        args: dict = {}
        args["query"] = self.search_query

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
        store: GistStore = self.app.store
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
            try:
                table.add_row(
                    bm,
                    desc,
                    ft,
                    ts,
                    str(item["file_count"]),
                    str(item["total_lines"] or ""),
                )
            except Exception:
                pass

        self._update_counts(len(results), len(store.gists))

    def _update_counts(self, shown: int, total: int) -> None:
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

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value
        self._apply_filters()

    @on(DataTable.RowSelected, "#gist-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        store: GistStore = self.app.store
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
        store: GistStore = self.app.store
        self.query_one("#refresh-btn", Button).label = "⟳"
        try:
            count = await store.refresh_list()
            self._apply_filters()
            self.app.notify(f"Loaded {count} gists", severity="information")
        except RuntimeError as e:
            self.app.notify(f"Refresh failed: {e}", severity="error")
        self.query_one("#refresh-btn", Button).label = "↻"

    def action_refresh(self) -> None:
        self.call_later(self._do_refresh)

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
        if self.search_query:
            self.query_one("#search-input", Input).value = ""
            self.search_query = ""
        elif self.active_filters:
            self.active_filters = {}
            self._apply_filters()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.action_pop()
            event.prevent_default()


# ─── App ─────────────────────────────────────────────────────────────────────

class GistManager(App):
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
        self.push_screen(MainScreen())

    def action_help(self) -> None:
        self.notify(
            "Ctrl+F:Search  Ctrl+N:New  Ctrl+O:Filters  "
            "Ctrl+R:Refresh  Ctrl+S:Stats  Ctrl+B:Bookmarks  "
            "Enter:View  Esc:Back  ?:Help  Q:Quit",
            title="Keyboard Shortcuts",
            severity="information",
        )


# ─── Entry Point ─────────────────────────────────────────────────────────────

app = GistManager()


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
