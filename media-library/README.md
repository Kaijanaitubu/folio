# Folio — Personal Media Library

[English](README.md) | [日本語](README.ja.md)

A working PC-hosted implementation of Personal Media Database Requirements v2.0. Uses Python's standard library, SQLite, and browser JavaScript. No package installation, paid hosting, Node build, or external account is required.

Future requests, hosting options, and implementation status are tracked in the [development roadmap (Japanese)](ROADMAP.md). Update that file as proposals are discussed, approved, implemented, or deferred.

## Start on this PC

Open PowerShell in this directory and run:

```powershell
.\start.ps1
```

Open **http://localhost:8765**. Keep the terminal/server running. Stop with Ctrl+C. If PowerShell blocks the script, run Python directly instead of changing your machine's execution policy:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" server.py
```

On another PC with Python 3.11 or newer installed:

```powershell
py -3 server.py
```

The launcher prefers the bundled Python available on this PC, then the Python launcher, then `python`. Configuration options:

```powershell
.\start.ps1 -Port 8765 -ListenAddress 0.0.0.0
```

Binding to `127.0.0.1` instead permits access only from this PC. Running two servers against the same database is not supported; stop the old server before starting another.

To run without leaving a terminal open, use `./run-background.ps1`. It starts a hidden server and records its process ID in `data/server.pid`; `./stop.ps1` stops that exact server. Logs are written to `data/server.log` and `data/server-error.log`. The background launcher itself does not change startup settings; use the automatic startup installer below to start it after Windows sign-in. Stop a foreground server with Ctrl+C before using the background launcher.

## Automatic startup on Windows

Run `./autostart.ps1` once to enable automatic startup for your Windows account. It installs one shortcut in your user Startup folder and launches the existing background server silently at sign-in, using port 8765 and the existing database. It does not open a browser. Existing-server checks prevent duplicate launches. This runs after you sign in, rather than before the Windows login screen. Keep the application folder and Python runtime in their current locations; rerun the installer after moving the application.

Run `./autostart.ps1 -Disable` to remove this shortcut. This does not stop a running server; use `./stop.ps1` for that. Startup uses the existing PowerShell execution policy and requires Windows Script Host/VBScript. A managed PC that disables either may block startup. No system execution-policy, firewall, or router settings are changed.

## Access from a phone

1. Connect the phone to the same Wi-Fi/LAN as the PC.
2. Find the PC's active LAN IPv4 address using Windows Network settings or `ipconfig`.
3. Open `http://PC-LAN-IP:8765` in the phone browser.
4. If Windows asks about firewall access, allow the Python server for the **private network** only. A firewall rule, if needed, should be limited to inbound TCP port 8765 on private networks/local subnet. This app does not alter firewall or router settings.

The PC must stay powered on and awake. This release is for a trusted LAN, without account authentication. Do not port-forward it or publish it to the Internet. All browsers see the same server database; no device sync setup is needed. VPN software and Wi-Fi client isolation can prevent LAN access.

## Features

- Responsive gallery, detail pages, manual entry/editing, permanent deletion confirmation. Black/orange dark theme by default, with the original light theme selectable in Settings.
- Persistent utility search input on all pages; Enter or its magnifying glass opens results. Compact icon-only Add/Random controls stay visible on narrow phones. On mobile, focused utility search moves the bar to the top; editing other fields temporarily hides it to avoid keyboard overlap. Save/Delete are inline after the mobile entry form.
- Multiple exact source URLs and one primary link; remote cover URLs, a memory-only Hitomi thumbnail relay, and broken-image fallback.
- Tag/author/circle/series/character directories with clickable filtered searches, preferred display aliases, usage counts, shared editing, explicit merging/deletion, and paginated name/usage/creation sorting. The sort selector replaces the old gender filter.
- Arbitrary rating dimensions with permanent numbered search keys, scales 2–10, ten symbol choices, gallery visibility, and independent sorting.
- Unicode-aware server-side search with NOT → OR → AND precedence; autocomplete, pagination, deterministic seeded shuffle, and uniform random selection over complete results.
- Hitomi metadata-only importer; empty-field filling, multi-value additions, explicit conflicting-value replacement, duplicate-title rejection.
- Bookmark HTML folder/item preview and durable jobs with progress, cancellation, retries, duplicate reports, and restart recovery.
- English/Japanese switch, remembered per browser.
- Automatic daily database backup with seven-copy retention, plus manual backup in Settings.

## Search examples

The library remembers its last selected sort in each browser, including after reload or returning home. An explicit sort in a saved/search URL takes priority; a deleted rating dimension falls back to newest added. Search submissions from other pages also use the remembered sort. Sorting preferences are per browser rather than synchronized between devices.

```text
author:"Alice Smith"/author:Bob rating1:>=4
female:example -tag:another
title:"A/B" pages:>=50
review:"my notes"
bought:yes
```

The first example means `(Alice Smith OR Bob) AND rating1 >= 4`. Field searches for metadata names use exact names/aliases; free words and `title:`/`review:` use substrings. Reviews are excluded from free-word search. `tag:` includes all genders; `female:`, `male:`, and `neutral:` restrict them. `rating:` is intentionally invalid: use numbered rating dimensions. Quoted values support `\"` and `\\` escapes. Parentheses are not supported. Query errors are shown instead of silently ignored.

Titles are trimmed and otherwise compared exactly, case-sensitively, within the library. Tag identity is canonical name plus female/male/neutral. Unspecified and genderless are both neutral. Aliases never trigger automatic entity merging.

In a metadata editor, add aliases and choose **Primary display name**. This label appears on works, directory rows, selection controls, and search suggestions; the original name stays intact and both names remain searchable. The preference applies to the shared entity across all browsers. Neutral-tag links use `neutral:` rather than a search across all genders.

Name sorting combines A–Z and kana order, using width/case/kana normalization only for sorting. For Kanji names, optionally enter **Sort reading** in kana; otherwise no pronunciation is guessed. New metadata records creation time; older records have an unknown date and use their original insertion order, before dated entries in oldest-first sorting. Edits do not change this order. All matching items are sorted on the server before 100-item directory pagination.

## Importing

### Open a Hitomi page in Folio

In Settings, find **Open from Hitomi**. Configure the Folio address for the device you will use; on a phone, open Folio with the PC LAN address rather than localhost. Copy the generated bookmark address into a browser bookmark named **Folio**. On desktop, you can instead drag the Folio link into the bookmarks bar.

On a Hitomi work/reader page, run this bookmark. Android Chromium browsers may require typing the bookmark name in the address bar and selecting the saved bookmark suggestion rather than opening it from the bookmark manager. Actual Brave Android behavior still needs device verification. If it does not execute, use the Hitomi URL field in Folio Settings as a fallback.

- An exact source link, including a secondary source, opens its work detail. HTTP/HTTPS and www variants are treated alike. Multiple exact matches offer an entry chooser.
- Another page or URL of the same Hitomi gallery opens a confirmation showing the registered link. Choose an existing entry, cancel, or import the current link as a new draft.
- An unregistered gallery imports metadata into a new editor with the original URL, query, and page fragment preserved. Nothing is saved until Save. Import failure retains the URL for retry or manual editing.
- Source-entry imports may preview a duplicate title with a warning; rename it before saving. Title uniqueness remains enforced, and ordinary interactive/batch duplicate handling is unchanged.

The bookmark only navigates to Folio. It does not inspect your library from Hitomi, send page contents, or require an extension, CORS access, or a public server. The Folio PC must be running and reachable on your LAN. `/#/source?url=ENCODED_URL` is the incoming route; source checking itself never fetches remote data or modifies works.

To check the source-flow logic without a browser (optional Node.js requirement), run `node test_source_flow.mjs` from this directory. These tests do not replace testing the saved bookmark on your phone.

### Editing and bookmark imports

Each metadata field in the work editor has a Remove all button. Confirm to clear that field in the draft, then Save to apply. Discarding edits restores saved associations. Shared dictionary records and other works are kept.

Hitomi reader links such as `/reader/ID.html#7` use page 7's thumbnail as the cover; `#7-8` and `#7-` also use page 7. Interior pages use the source's smaller `webpsmalltn` format because large gallery thumbnails are not available for every page. Invalid/out-of-range fragments or missing page hashes fall back to the first page with a warning. No page fragment or a non-reader URL uses the first page. This also applies to bookmark imports. Existing covers stay unchanged until reimported; select the Cover replacement when prompted and save to apply it.

For one work, add a URL in New/Edit and use Import metadata. The work is not saved until you press Save. With multiple links, choose the one to import from. Partial metadata is usable. Existing personal ratings/reviews/purchase status remain unchanged. A duplicate retrieved title aborts metadata application without modifying the draft.

For many works, export browser bookmarks to HTML, open Bookmark imports, upload, choose folders/items, and start. Each successful item becomes a new work. Unsupported links are excluded in preview. Duplicate titles, missing titles, ambiguous aliases, and fetch failures are reported without silently merging works. Failed/cancelled items can be retried. Closing the page does not stop the job. Cancellation keeps completed entries and allows an already running request to finish.

Supported source URL shapes include `/galleries/ID.html`, `/reader/ID.html#page`, and `/category/name-ID.html`. Saved URLs are never rewritten. Other URL shapes can still be saved manually. Import requests are restricted to known source hosts, pinned to public resolved addresses, bounded by time and response size, and do not follow redirects. The adapter reads gallery JSON and the thumbnail routing table from the source's current metadata host. It prefers `japanese_title` like the original page and derives the selected-page WebP thumbnail URL. Importing remains metadata-only and executes no source JavaScript. Viewing a supported Hitomi cover uses the separate volatile relay described below.

## Memory-only covers

Hitomi covers, including already-saved legacy thumbnail URLs, now load through Folio using the source-site referrer. The server receives thumbnail bytes in RAM and sends them to the browser. It never writes them to image files, SQLite, backups, or logs. Only visible/near-visible covers load through the browser's lazy loading. Unavailable covers keep the stable fallback. Other manual image hosts continue to load directly from the browser.

The temporary RAM cache uses LRU eviction, a 32 MiB payload cap, and five-minute expiration. Concurrent requests for the same thumbnail share one fetch. Each thumbnail is limited to 2 MiB; at most four complete relay requests run simultaneously. A response is buffered and validated in RAM before sending, so malformed, oversized, or incomplete upstream responses cannot produce a cached partial image. Transient read/copy buffers can add about 16 MiB to the cached-payload cap; total process/browser memory also includes normal application overhead.

The upstream deadline is 20 seconds, with a 30-second client-send timeout. DNS resolution uses the system resolver; pathological resolver delays can exceed the upstream deadline before a socket is opened. Targets come only from saved works and the supported thumbnail hosts/paths. Public IP pinning, TLS verification, no redirects, MIME/signature checks, and same-origin image responses keep this from becoming a general URL proxy.

Relayed images request no browser persistence through `Cache-Control: no-store, max-age=0`, `Pragma: no-cache`, and `Expires: 0`. There is no service worker or browser image database. Restarting Folio clears its image cache; expired entries are pruned during the background worker loop. The application's guarantee concerns its own file/database/cache writes, rather than operating-system memory paging or browser internals. The source can still change access rules. See [THUMBNAIL-INVESTIGATION.md](THUMBNAIL-INVESTIGATION.md) for the original investigation and implemented follow-up.

## Data, configuration, backup, and restore

Live data: `data/library.sqlite3`. Backups: `backups/library-*.sqlite3`. These are ignored by version control. Schema migration 2 adds metadata display aliases, sort readings, and creation timestamps without replacing existing records. Migration versions are recorded in the `migrations` table; initialization is idempotent and occurs at startup. Future changes must add explicit migrations without resetting user data.

Environment variables (set in the same terminal before starting):

```powershell
$env:MEDIA_DB = 'D:\Folio\library.sqlite3'
$env:MEDIA_BACKUPS = 'E:\Folio-backups'
$env:MEDIA_HOST = '0.0.0.0'
$env:MEDIA_PORT = '8765'
```

Backups use SQLite's consistent online-backup API, include dictionaries/ratings/links/job state, and contain URLs rather than images. The server creates a backup at startup and every 24 hours while running, keeping seven copies in the selected backup directory. Another physical disk or separately backed-up location is needed to protect against disk loss.

To create a backup without running the website:

```powershell
py -3 server.py --backup
```

To restore: **stop all servers first**, then run:

```powershell
py -3 server.py --restore 'E:\Folio-backups\library-TIMESTAMP.sqlite3'
```

An existing live database is backed up first. The restore command checks database integrity, restores through SQLite's backup API, and exits. Start normally afterward. Pending/in-flight import items recover on startup; completed work/item writes are atomic. If using the bundled Python here, substitute its full path for `py -3`.

## Changing a rating scale

Edit a dimension in Rating dimensions, change its maximum, then choose Preview conversion. Review the old-to-new values and work counts, then Convert and save. Cancel leaves saved data unchanged. Conversion keeps 1 as the lowest score, rounds exact half ties down, and reserves full marks for works that already had full marks. Unrated remains unrated. For example, 3→5 maps 1/2/3 to 1/3/5; 5→3 maps 1/2/3/4/5 to 1/1/2/2/3. Reducing the scale loses distinctions; increasing it later does not restore them. Create a backup in Settings before converting if you need to restore the original ratings. A preview invalidated by another browser must be refreshed before saving.

## Verification

```powershell
py -3 -m unittest -v test_app test_server test_cover_relay
node test_rating_flow.mjs
node test_source_flow.mjs
py -3 benchmark.py --count 30000
py -3 benchmark.py --count 100000
py -3 check_live_import.py
py -3 check_live_relay.py
```

Tests and benchmarks use isolated temporary databases inside `test-output/` and never seed the real library. HTTP tests need permission to bind a local test port. The live check fetches public metadata but does not save a work. See `VERIFICATION.md` for recorded results and remaining verification limits.

## Source layout

| File | Responsibility |
|---|---|
| `server.py` | HTTP API, request protection, persistent import worker, startup/restore |
| `db.py` | SQLite schema, transactions, relationships, directory/rating rules, backups |
| `search.py` | Search lexer and parameterized SQL compiler |
| `importer.py` | Hitomi adapter and safe bookmark HTML parser |
| `cover_relay.py` | Restricted thumbnail fetches, bounded RAM cache, volatile image buffers |
| `static/app.js` | Browser routes, forms, dialogs, gallery, imports |
| `static/i18n.js` | English/Japanese interface resources |
| `static/style.css`, `static/theme.css` | Responsive visual design, themes, persistent utility bar |
| `test_app.py`, `test_server.py`, `test_cover_relay.py` | Core, HTTP/job, relay and cache regression checks |
| `benchmark.py` | Realistic scale benchmarks |

The owner is currently `local`. Persistence is owner-scoped so future registration can attach records to accounts; actual registration/authentication/public operation remains a separate release.
