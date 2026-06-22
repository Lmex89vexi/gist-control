# gist-control

Single-file Textual TUI (`gistman.py`) backed by `gh` CLI.

## Quick start

```bash
cd scripts/gist
source venv/bin/activate
python3 gistman.py
```

## Structure

| File | Role |
|---|---|
| `gistman.py` | Entire app (~1350 lines) — `GistStore` (data) + 5 Textual screens |
| `pyproject.toml` | Deps: `textual>=0.50.0`, `pyperclip>=1.8` |

## Key facts

- **No API token needed** — all operations go through `gh` CLI (must be installed + authenticated)
- **Cache**: `~/.cache/gistman/gists.json` — auto-refreshes after 300s. Delete it to force a clean fetch
- **Textual 8.x** — single-letter keybindings won't work while an `Input` has focus; use `Ctrl+` combos instead
- **`gh gist list` has no `--json` flag** — the store uses `gh api gists?per_page=100` with pagination instead
- **Content is lazy-loaded** — list shows metadata immediately; file contents are fetched on-demand when viewing a gist
- **pyperclip is optional** — clipboard falls back to `xclip` / `wl-copy`

## Architecture

```
GistManager (App)
 ├─ MainScreen  — DataTable browser + search/filter
 ├─ DetailScreen — file tabs, syntax-highlighted content, actions
 ├─ FilterModal  — advanced filters (name, content, type, date, visibility)
 ├─ EditScreen   — create/edit gist form (+/‑ files, inline content editor)
 └─ StatsModal   — file type distribution, monthly timeline
```

Navigation: `Ctrl+F` search, `Ctrl+O` filters, `Ctrl+N` new, `Ctrl+S` stats, `Ctrl+B` bookmarks, `Enter` view, `Esc` back.
