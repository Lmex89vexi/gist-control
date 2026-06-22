"""Application-wide constants."""

from pathlib import Path

# Cache
CACHE_DIR = Path.home() / ".cache" / "gistman"
CACHE_FILE = CACHE_DIR / "gists.json"
CACHE_TTL = 300  # seconds before auto-refresh
LOG_FILE = CACHE_DIR / "gistman.log"

# External CLI
GH_CMD = "gh"

# Map file extensions to TextArea language identifiers
LANGUAGE_MAP: dict[str, str | None] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".md": "markdown", ".sh": "bash",
    ".bash": "bash", ".ps1": "powershell", ".txt": None,
    ".csv": None, ".xml": "xml", ".html": "html", ".css": "css",
    ".go": "go", ".rs": "rust", ".java": "java",
}
