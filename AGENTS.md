# gist-control

Textual TUI for GitHub Gists. All GitHub access goes through an authenticated `gh` CLI — there is no separate app token. `gh auth status` must succeed.

## Run and verify

```bash
bash start.sh                  # or: fish start.fish — creates venv, then reinstalls editable on every launch
venv/bin/python -m gistman     # run once the venv exists
venv/bin/python -m compileall -q gistman   # fastest syntax check
```

- No test suite, linter, formatter, or CI is configured, so there is no single-test command. For runtime checks, launch the TUI in a real terminal or drive it with a Textual `run_test`/Pilot script; `compileall` only catches syntax errors.
- Dependencies are duplicated in `pyproject.toml` and `requirements.pip` (fallback only) — keep both in sync.
- Root `gistman.py` is a launcher shim that execs `venv/bin/python -m gistman`; it does not bootstrap the venv. The application lives in `gistman/`.
- Commit only source and docs; leave generated `venv/`, `__pycache__/`, `gistman.egg-info/`, and `.codegraph/` untracked.

## Entrypoints and structure

- `python -m gistman` → `gistman/__main__.py` → `gistman.app.main()`. The console script resolves `gistman:app.run`, where `app` is a module-level `GistManager` instance.
- Importing `gistman` has side effects: it constructs that App/Store (creating `~/.cache/gistman/`) and configures loguru. Use `GistManager()` to construct a separate instance, and keep import-time side effects limited to that existing setup.
- `GistManager` owns one `GistStore`; screens access it as `self.app.store`.
- Flow: `MainScreen` (browser/search/filter) → `DetailScreen` (file viewer/actions) → `EditScreen` (create/edit). `FilterModal`, `StatsModal`, and `ConfirmModal` are modals.
- Screens type against `IStore` in `store.py`, not `GistStore`. Existing exception: `DetailScreen.clone_gist` calls `store._run_gh`; extend `IStore` when adding store APIs instead of widening that leak.
- External editing (`config.py`) writes temp files, opens the editor under `app.suspend()`, and reads files back. Config lives at `~/.config/gistman/config.json` (`{"editor": ...}`, default `nvim`); `$EDITOR` wins, and config is cached for the process lifetime.

## Data and cache behavior

- `~/.cache/gistman/gists.json` stores gists, bookmarks, and clipboard history. `CACHE_TTL` is 300s; `MainScreen.on_screen_resume` refreshes when the cache is stale or empty.
- Listing uses paginated `gh api gists?per_page=100&page=N` because `gh gist list` has no `--json`. Create/update use `gh api -X POST/PATCH --input <tempfile>`; delete uses `gh gist delete --yes`.
- Contents are lazy-loaded by `fetch_content()` (`gh api gists/<id>`). Content search only sees cached content; `DetailScreen` fetches missing content on mount, and external edit also fetches missing content before opening.
- Bookmarks are local-only (never synced to GitHub). `refresh_list` prunes gists and bookmarks deleted remotely.
- `~/.cache/gistman/gistman.log` records every `gh` call at DEBUG; check it first when debugging UI behavior.

## Textual quirks

- The local venv currently runs Textual 8.2.7, while `pyproject.toml` only requires `>=0.50.0`; treat 8.2.7 as the tested API surface rather than the declared floor.
- Single-letter bindings (`q`, `j`, `k`) do not fire while an `Input` has focus; use `Ctrl+` combos for new shortcuts. `MainScreen` implements j/k itself and skips them while search is focused.
- `Esc` on `MainScreen` clears search, then filters; it is not an exit.
- Global CSS is `gistman/css.py`; `EditScreen` and `ConfirmModal` also define local `CSS` blocks. Notifications use `self.app.notify(...)`; `widgets/notification.py` is currently unused.
- `pyperclip` is declared but import-guarded; clipboard falls back to `xclip`, then `wl-copy`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues and are managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles map 1:1 to GitHub label strings. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
