# gist-control

A Textual TUI for browsing and managing GitHub Gists, packaged and launched as `gistman`. GitHub is the source of truth; a local cache serves browsing and search, and every remote operation goes through the authenticated `gh` CLI.

## Language

### Gists

**Gist**:
One GitHub gist: a description and one or more named files. Each gist has an id and is either public or secret.
_Avoid_: snippet, paste

**File**:
A named text file inside a gist. Its filename, size, language, and raw URL are cached with the gist; its full text is cached only after it is fetched.
_Avoid_: attachment, blob

**Content**:
The full text of a gist file, loaded separately from the gist list. GitHub may mark a file as truncated when the API returns only part of it.
_Avoid_: body, text, source

**Description**:
The gist's free-text title. The list column labeled "Name" shows the description, falling back to the first filename when the description is empty.
_Avoid_: name, title

**Metadata**:
The gist fields available without file content: description, timestamps, visibility, filenames, sizes, and derived counts such as file count and line count. The line count is estimated from file size until content is fetched.
_Avoid_: summary, list data, info

**Visibility**:
Whether a gist is public or secret.
_Avoid_: privacy, access

**Secret gist**:
A gist that is unlisted but not private: anyone with its URL can read it. Secret is GitHub's visibility label, not an access-control guarantee.
_Avoid_: private gist, hidden gist

**Public gist**:
A gist discoverable by others and listed in the owner's public gists.
_Avoid_: open gist, shared gist

### Local state

**Cache**:
The local snapshot of gists, any fetched content, bookmarks, clipboard history, and the last refresh time.
_Avoid_: database, store

**Stale**:
The condition of a cache whose last successful list refresh is older than the freshness window, or which has never been refreshed. A stale cache triggers an automatic refresh when the main screen resumes.
_Avoid_: expired, out of date

**Refresh**:
A full paginated re-fetch of the gist list. It preserves content already fetched and drops gists and bookmarks that no longer exist remotely.
_Avoid_: sync, reload, update list

**Lazy load**:
Fetching a gist's full content on demand instead of during the list refresh.
_Avoid_: prefetch, download

**Bookmark**:
A local-only marker on a gist id, used to filter the list. Bookmarks are never sent to GitHub and are discarded when the gist disappears from a refresh.
_Avoid_: favorite, star, pin

### Finding

**Search**:
Free-text matching over cached gists. The search term matches description and filenames; a content term matches only files whose content has already been fetched.
_Avoid_: query, lookup

**Filter**:
A structured, AND-ed set of criteria applied on top of search: file type, date range, visibility, and bookmarks only.
_Avoid_: advanced search, query

**File type**:
The lowercased filename extension used for filtering (`.py`, `.md`). It is not the file's detected language; files without an extension are `unknown`.
_Avoid_: language, format

**Stats**:
Aggregates computed over cached gists only: totals, file-type counts, monthly timeline, and averages. Line counts are estimated from file size until content is fetched.
_Avoid_: analytics, dashboard, metrics

### Actions

**External edit**:
Suspending the TUI, opening temporary copies of a gist's files in the configured editor, then reading them back and updating the gist. `$EDITOR` takes precedence over the configured editor.
_Avoid_: open in editor, edit in place

**Clone**:
Copying a gist's git repository into the current directory with `gh gist clone`.
_Avoid_: download, checkout

### Architecture

**Store**:
The single data layer owned by the app. It owns the cache, calls the `gh` CLI, and serves gists, search, stats, and mutations to every screen.
_Avoid_: repository, backend, model

**IStore**:
The protocol that screens type against instead of the concrete store. It is the seam for swapping the backend or injecting a test double.
_Avoid_: store interface, backend contract
