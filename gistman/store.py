"""Data layer — abstracts GitHub Gist storage via the `gh` CLI.

Applies Dependency Inversion: screens depend on the `IStore` protocol
rather than on the concrete `GistStore` implementation.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from gistman.constants import CACHE_FILE, CACHE_TTL, GH_CMD, LANGUAGE_MAP
from gistman.log import logger

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False


# ─── Dependency Inversion: abstract contract ────────────────────────────────

@runtime_checkable
class IStore(Protocol):
    """Interface that screens depend on. Swap this out for tests or alternate backends."""

    @property
    def gists(self) -> dict[str, dict]: ...
    @property
    def bookmarks(self) -> set[str]: ...
    @property
    def is_stale(self) -> bool: ...
    @property
    def error(self) -> str | None: ...

    async def refresh_list(self) -> int: ...
    async def fetch_content(self, gist_id: str) -> None: ...
    def get_list_data(self) -> list[dict]: ...
    def search(self, query: str = "", content: str = "",
               file_types: list[str] | None = None,
               date_from: date | None = None, date_to: date | None = None,
               visibility: str | None = None,
               bookmarks_only: bool = False) -> list[dict]: ...
    async def create_gist(self, description: str, files: list[tuple[str, str]],
                          public: bool = False) -> str: ...
    async def update_gist(self, gist_id: str,
                          description: str | None = None,
                          files: list[tuple[str, str]] | None = None) -> None: ...
    async def delete_gist(self, gist_id: str) -> None: ...
    def get_gist(self, gist_id: str) -> dict | None: ...
    def get_stats(self) -> dict: ...
    def copy_to_clipboard(self, text: str) -> bool: ...
    def save_cache(self) -> None: ...


# ─── Concrete store ─────────────────────────────────────────────────────────

class GistStore:
    """Persistent cache + gh CLI bridge for GitHub Gists.

    Responsibilities:
    - Cache gist metadata/contents to ~/.cache/gistman/gists.json
    - Proxy CRUD operations through `gh api` / `gh gist delete`
    - Provide search/filter over cached gists
    - Manage bookmarks locally
    """

    def __init__(self) -> None:
        self.cache_dir = CACHE_FILE.parent
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory gist data: keyed by gist id
        self.gists: dict[str, dict] = {}

        # Locally-persisted bookmark ids
        self.bookmarks: set[str] = set()

        # Recently copied URLs (ring buffer, max 50)
        self.clipboard_history: list[str] = []

        # Timestamp of last successful API fetch; 0 means never fetched
        self.cached_at: float = 0

        # Gist ids whose content is currently being fetched
        self._loading_content: set[str] = set()

        self._error: str | None = None

        self.load_cache()
        logger.debug("GistStore initialised — {} cached gists, {} bookmarks",
                     len(self.gists), len(self.bookmarks))

    # ── Cache persistence ──────────────────────────────────────────────────

    def load_cache(self) -> None:
        """Restore gists/bookmarks/history from disk cache."""
        if not CACHE_FILE.exists():
            logger.debug("No cache file at {}", CACHE_FILE)
            return
        try:
            data = json.loads(CACHE_FILE.read_text())
            self.gists = data.get("gists", {})
            self.bookmarks = set(data.get("bookmarks", []))
            self.clipboard_history = data.get("clipboard_history", [])
            self.cached_at = data.get("cached_at", 0)
            logger.info("Loaded {} gists from cache", len(self.gists))
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Corrupt cache file — starting fresh: {}", exc)

    def save_cache(self) -> None:
        """Persist current state to disk cache."""
        data = {
            "cached_at": self.cached_at or time.time(),
            "gists": self.gists,
            "bookmarks": list(self.bookmarks),
            "clipboard_history": self.clipboard_history,
        }
        CACHE_FILE.write_text(json.dumps(data, indent=2, default=str))
        logger.debug("Cache saved ({} gists)", len(self.gists))

    # ── Staleness ──────────────────────────────────────────────────────────

    @property
    def is_stale(self) -> bool:
        """True when the cache is older than CACHE_TTL or hasn't been populated."""
        return time.time() - self.cached_at > CACHE_TTL

    @property
    def error(self) -> str | None:
        """Last error message from a failed API call, if any."""
        return self._error

    # ── gh CLI helpers ─────────────────────────────────────────────────────

    async def _run_gh(self, args: list[str]) -> str:
        """Execute `gh <args>` and return stdout, or raise RuntimeError."""
        logger.debug("gh {}", " ".join(args))
        proc = await asyncio.create_subprocess_exec(
            GH_CMD, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            msg = stderr.decode().strip()
            logger.error("gh {} failed ({}): {}", " ".join(args), proc.returncode, msg)
            raise RuntimeError(f"gh {' '.join(args)} failed: {msg}")
        out = stdout.decode().strip()
        logger.debug("gh {} → {} bytes", " ".join(args), len(out))
        return out

    # ── Read operations ────────────────────────────────────────────────────

    async def refresh_list(self) -> int:
        """Fetch the user's full gist list from the GitHub API with pagination.

        Returns: number of gists fetched.
        Raises RuntimeError on API failure.
        """
        self._error = None
        logger.info("Refreshing gist list from GitHub API…")

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
                logger.debug("Page {} → {} gists", page, len(batch))
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
                        # Preserve previously-fetched content when the API summary
                        # doesn't include it (lazy load).
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

            # Remove gists that no longer exist on GitHub
            for gid in list(self.gists.keys()):
                if gid not in current_ids:
                    logger.debug("Removing stale gist {}", gid)
                    del self.gists[gid]

            self.bookmarks &= current_ids
            self.cached_at = time.time()
            self.save_cache()
            logger.info("Fetched {} gists total", len(all_gists))
            return len(all_gists)

        except RuntimeError:
            self._error = str(RuntimeError)
            logger.exception("Gist list refresh failed")
            raise
        except json.JSONDecodeError as e:
            self._error = f"Invalid response: {e}"
            logger.exception("Gist list refresh — invalid JSON")
            raise

    async def fetch_content(self, gist_id: str) -> None:
        """Fetch full file contents for a single gist (lazy load).

        Only fetches if not already loading. Populates content in-place.
        """
        if gist_id in self._loading_content:
            logger.debug("Content for {} already being fetched…", gist_id)
            return
        self._loading_content.add(gist_id)
        logger.info("Fetching content for gist {}", gist_id)
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
                logger.debug("Content fetched for gist {}", gist_id)
        except RuntimeError:
            logger.exception("Failed to fetch content for gist {}", gist_id)
        finally:
            self._loading_content.discard(gist_id)

    def get_list_data(self) -> list[dict]:
        """Build a flat list of gist summaries for display and search.

        Each item includes computed fields: file count, total lines, etc.
        """
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
                "description": g.get("description", "") or files[0]["filename"] if files else "(no description)",
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
        """Filter cached gists by the given criteria.

        All filters are AND-ed together. Empty/None filters are skipped.
        """
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

        logger.debug("Search returned {} of {} gists", len(results), len(items))
        return results

    # ── Mutations ─────────────────────────────────────────────────────────

    async def create_gist(
        self,
        description: str,
        files: list[tuple[str, str]],
        public: bool = False,
    ) -> str:
        """Create a new gist via the GitHub API and refresh the local cache."""
        logger.info("Creating gist ({} files, public={})", len(files), public)
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
            logger.info("Gist {} created", gist_id)
            await self.refresh_list()
            await self.fetch_content(gist_id)
            return gist_id
        except RuntimeError:
            logger.exception("Failed to create gist")
            raise
        finally:
            os.unlink(tmp.name)

    async def update_gist(
        self,
        gist_id: str,
        description: str | None = None,
        files: list[tuple[str, str]] | None = None,
    ) -> None:
        """Update a gist's description and/or files in-place."""
        logger.info("Updating gist {}", gist_id)
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
            logger.info("Gist {} updated", gist_id)
        except RuntimeError:
            logger.exception("Failed to update gist {}", gist_id)
            raise
        finally:
            os.unlink(tmp.name)

    async def delete_gist(self, gist_id: str) -> None:
        """Delete a gist via the gh CLI and remove it from local state."""
        logger.info("Deleting gist {}", gist_id)
        await self._run_gh(["gist", "delete", "--yes", gist_id])
        self.gists.pop(gist_id, None)
        self.bookmarks.discard(gist_id)
        self.save_cache()
        logger.info("Gist {} deleted", gist_id)

    # ── Lookup helpers ─────────────────────────────────────────────────────

    def get_gist(self, gist_id: str) -> dict | None:
        """Return the raw gist dict, or None if not cached."""
        return self.gists.get(gist_id)

    def get_stats(self) -> dict:
        """Aggregate statistics over cached gists (file types, timeline, counts)."""
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

    # ── Clipboard ─────────────────────────────────────────────────────────

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to the system clipboard.

        Tries pyperclip first, then xclip, then wl-copy.
        Returns True on success.
        """
        if HAS_CLIPBOARD:
            try:
                pyperclip.copy(text)
                self.clipboard_history.append(text)
                if len(self.clipboard_history) > 50:
                    self.clipboard_history = self.clipboard_history[-50:]
                self.save_cache()
                logger.debug("Copied to clipboard via pyperclip")
                return True
            except Exception:
                logger.debug("pyperclip failed, trying fallback")

        for cmd, args in [
            ("xclip", ["xclip", "-selection", "clipboard"]),
            ("wl-copy", ["wl-copy"]),
        ]:
            try:
                proc = subprocess.Popen(
                    args, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
                )
                proc.communicate(text.encode())
                if proc.returncode == 0:
                    self.clipboard_history.append(text)
                    self.save_cache()
                    logger.debug("Copied to clipboard via {}", cmd)
                    return True
            except FileNotFoundError:
                continue

        logger.warning("No clipboard tool available")
        return False
