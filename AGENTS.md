# gist-control

Multi-module Textual TUI package (`gistman/`) backed by `gh` CLI.

## Quick start

```bash
cd scripts/gist
source venv/bin/activate
python3 -m gistman
```

## Structure

```
gistman/
├── __init__.py          # Exports app, GistManager, main
├── __main__.py          # `python3 -m gistman` entry
├── app.py               # GistManager App
├── store.py             # IStore protocol + GistStore (data layer)
├── log.py               # loguru setup — console INFO+, file DEBUG+ with rotation
├── css.py               # All Textual CSS
├── constants.py         # CACHE_DIR, LANGUAGE_MAP, GH_CMD
├── screens/
│   ├── main.py          # MainScreen (DataTable browser + search/filter)
│   ├── detail.py        # DetailScreen (file tabs, content, actions)
│   ├── edit.py          # EditScreen (create/edit gist form)
│   ├── filter_modal.py  # FilterModal (advanced filters)
│   ├── stats_modal.py   # StatsModal (statistics dashboard)
│   └── confirm.py       # ConfirmModal (Yes/No dialog)
└── widgets/
    └── notification.py  # Auto-dismissing notification
```

## Key facts

- **No API token needed** — all operations go through `gh` CLI
- **Cache**: `~/.cache/gistman/gists.json` — auto-refreshes after 300s
- **Logs**: `~/.cache/gistman/gistman.log` — rotates at 1 MB, keeps 3 archives
- **Textual 8.x** — single-letter keybindings won't work while an `Input` has focus; use `Ctrl+` combos
- **`gh gist list` has no `--json` flag** — the store uses `gh api gists?per_page=100` with pagination
- **Content is lazy-loaded** — list shows metadata immediately; file contents are fetched on-demand
- **pyperclip is optional** — clipboard falls back to `xclip` / `wl-copy`
- **`push_screen_wait` requires a Worker** — use the callback pattern (`push_screen` with `on_dismiss`) instead of `await push_screen_wait` in event handlers
- **Dependency Inversion** — screens depend on `IStore` protocol, not `GistStore` directly

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
