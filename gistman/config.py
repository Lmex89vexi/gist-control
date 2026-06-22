"""Configuration loader — reads ~/.config/gistman/config.json.

Fields:
    editor: str — Editor command (default: $EDITOR env → "nvim")
"""

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from gistman.log import logger

CONFIG_DIR = Path.home() / ".config" / "gistman"
CONFIG_FILE = CONFIG_DIR / "config.json"

_config: "Config | None" = None


@dataclass
class Config:
    editor: str = "nvim"

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_FILE.exists():
            logger.debug("No config file at {}", CONFIG_FILE)
            return cls()
        try:
            data = json.loads(CONFIG_FILE.read_text())
            logger.debug("Loaded config from {}", CONFIG_FILE)
            return cls(editor=data.get("editor", "nvim"))
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Failed to load config: {}", exc)
            return cls()

    def resolve_editor_cmd(self) -> list[str]:
        env_editor = os.environ.get("EDITOR")
        if env_editor:
            logger.debug("Using editor from $EDITOR: {}", env_editor)
            return env_editor.split()
        return [self.editor]


def load_config() -> Config:
    global _config
    if _config is None:
        _config = Config.load()
    return _config


async def edit_files_in_editor(
    files: list[dict],
    editor_cmd: list[str] | None = None,
) -> list[dict]:
    """Write *files* to a temp directory, open the editor, return updated files.

    Each file dict: {"filename": str, "content": str}

    Returns updated file dicts with content read back from disk after
    the editor exits.
    """
    if editor_cmd is None:
        editor_cmd = load_config().resolve_editor_cmd()

    with tempfile.TemporaryDirectory(prefix="gistman_") as tmpdir:
        tmp_path = Path(tmpdir)
        file_paths: list[Path] = []
        for f in files:
            fpath = tmp_path / f["filename"]
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(f.get("content", ""))
            file_paths.append(fpath)

        logger.info("Opening editor: {} on {} files", " ".join(editor_cmd), len(files))
        try:
            proc = await asyncio.create_subprocess_exec(
                *editor_cmd, *[str(p) for p in file_paths],
            )
            await proc.wait()
        except FileNotFoundError:
            logger.error("Editor not found: {}", editor_cmd[0])
            raise RuntimeError(f"Editor not found: {editor_cmd[0]}")
        except Exception:
            logger.exception("Editor failed")
            raise

        updated: list[dict] = []
        for f in files:
            fpath = tmp_path / f["filename"]
            content = fpath.read_text() if fpath.exists() else f.get("content", "")
            updated.append({"filename": f["filename"], "content": content})

        logger.debug("Editor closed — read back {} files", len(updated))
        return updated
