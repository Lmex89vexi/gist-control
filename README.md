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

## Requirements

- Python 3.10+
- [gh](https://cli.github.com/) CLI installed and authenticated

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install textual pyperclip
python3 gistman.py
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
