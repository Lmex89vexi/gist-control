# gist-control

Interactive TUI for managing your GitHub Gists.

Built with [Textual](https://textual.textualize.io/) and the `gh` CLI.

## Features

- Browse, search, and filter gists by name, content, file type, date, visibility
- View gist content with syntax highlighting
- Create, edit, and delete gists
- Bookmark gists for quick access
- Copy URLs, clone locally, open in browser
- Statistics dashboard (file types, timeline, counts)
- Structured logging via loguru (`~/.cache/gistman/gistman.log`)

## Requirements

- Python 3.10+
- [gh](https://cli.github.com/) CLI installed and authenticated

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install textual pyperclip loguru
python3 -m gistman
```

Or if installed as a package:

```bash
pip install -e .
gistman
```

## Project Structure

```
gistman/                 # Python package (SOLID-compliant modules)
├── __init__.py
├── __main__.py          # `python3 -m gistman` entry point
├── app.py               # GistManager App
├── store.py             # IStore protocol + GistStore (data layer)
├── log.py               # loguru logging setup
├── css.py               # All Textual CSS
├── constants.py         # Constants, LANGUAGE_MAP
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

## Keybindings

| Key       | Action          |
|-----------|-----------------|
| `Ctrl+F`  | Search          |
| `Ctrl+N`  | New gist        |
| `Ctrl+O`  | Filters         |
| `Ctrl+R`  | Refresh         |
| `Ctrl+S`  | Stats           |
| `Ctrl+B`  | Bookmarks       |
| `Enter`   | View gist       |
| `Esc`     | Back / Clear    |
| `Q`       | Quit            |
| `?`       | Help            |
