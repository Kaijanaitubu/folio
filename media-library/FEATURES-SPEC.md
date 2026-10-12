# Folio — Personal library features (F-006–F-009, F-012)

Approved: 2026-10-12. These features extend the current single-owner application. English and Japanese UI are supported. Work IDs remain stable; URL identity follows IMPORT-SPEC.md. Images are never persisted by the server.

## F-006 Recovery

- Deleting a work sets `deleted_at`. Work links, scores, associations, bookmark provenance and ID remain intact. Active search, random selection and metadata usage counts exclude deleted works.
- Trash retains entries for 30 days. A server worker checks expiration at startup and hourly; expiration is processed while the server runs. Manual permanent deletion and empty-trash require UI confirmation. Permanent deletion releases source claims and deletes dependent records.
- Exact URL lookup includes Trash. Source entry offers restoration; bookmark jobs skip these URLs and show the Trash label in duplicate reports. Different Hitomi pages remain distinct and can still be imported after the existing warning.
- Restore supports individual and multiple works. Dictionary items and rating axes removed since deletion are listed in a preview; users may restore the remaining information after acknowledgement. A preview signature detects changes before restoration. Global dictionary edits continue to apply to trashed entries.
- Operation history retains saved work edits/reimports, batch edits and scale conversions for 30 days. Unsaved drafts use the existing discard workflow. Creation, import jobs, dictionary deletion/merge and rating-axis deletion are not undoable in this release. There is no redo.
- Work undo restores only fields changed by the chosen operation. Comparisons ignore timestamps and opening history. Metadata is compared by identity; link order, URL, labels and primary designation matter. Ratings are treated as one work field for edit undo. Changes to affected fields block undo; unrelated fields remain intact. Missing required metadata or incompatible rating dimensions also block undo.
- Scale conversion history stores the original maximum and exact original scores, including trashed works. Undo restores these values without reverse approximation. The scale and full score set must still match the post-conversion state. Axis names, symbols and gallery visibility are not reverted.
- Undo validation and changes execute in one SQLite write transaction. History is marked undone only after success. Normal editing also rejects a stale `updated` value submitted by another editor.

## F-007 Named searches

- Save a name (1–200 characters), query (up to 4096 characters) and sort from Library. Empty queries mean all works. The saved-search page supports opening, editing, deletion and server-side reordering.
- Conditions are persisted under the owner, shared across devices. They are not result snapshots. Random sort receives a new seed when opened; scroll positions are not saved here.
- Queries retain their literal text. Dictionary changes do not silently rewrite them. Missing rating axes, invalid comparisons and deleted rating sort axes make a saved search unavailable until edited. Rating numbers remain permanent.

## F-008 Batch editing

- Select mode lets users choose cards, displayed works or all matching active works. Selecting all captures IDs; later matching additions are not silently included. Changing the query or sort clears selection.
- Metadata fields: author, circle, tag, series and character. Each supports keep, add, remove selected, replace and clear. Users choose dictionary entries, retaining alias resolution and gender identity. New dictionary entries can be created through the existing picker.
- Each rating supports keep, set 1–maximum or unset. Purchase status supports keep/yes/no; category and language support keep/set/clear. Title, cover, links, page count and review are not batch fields.
- Preview freezes target states, patch and target count for 15 minutes. It reports changed and unchanged works and lists configured changes. It does not mutate works. Unchanged works keep their timestamp and do not generate history.
- Apply revalidates all targets and patch constraints. A missing, trashed or changed target cancels the batch. All writes and its single undo record commit atomically. A consumed preview cannot be replayed. Expired previews require review again.
- All-result selection supports large libraries without a fixed 1000-item cap. Browser operations show loading state while processing. There is no partial-success mode.

## F-009 PWA and shared URLs

- Manifest supplies stable app ID, standalone display, PNG icons, scope and a GET share target at `/share-target` accepting URL/text/title. The landing handler only opens a review workflow; GET never persists a work.
- Shared fields are scanned for HTTP(S) URLs. Multiple links require selection. No link yields an explanatory page. Credentials embedded in URLs are rejected. Shared content is removed from the address and session buffer after consumption.
- Hitomi uses existing source-check and import behavior: exact URL opens details without import; same gallery/different page warns and permits a new work; new URLs import into an unsaved draft. Trashed exact matches offer restoration. Unsupported sites use exact URL lookup and an unsaved manual entry.
- Install action is available in Settings when the browser supplies an install prompt; otherwise the UI explains using the browser menu. Share-target availability remains dependent on browser/OS installation behavior and requires Reno5 A / Brave verification.
- Service worker performs network-only navigation and supplies a bilingual server-unavailable page. It never caches library APIs, source images or offline library data. PC/server/Tailscale must remain available.
- Recommended deployment is private Tailscale Serve forwarding trusted HTTPS to `http://127.0.0.1:8765`. Do not enable Funnel for this personal app. HTTPS certificates/Serve must be enabled in the owner's Tailscale admin console. `--bg` retains Serve configuration across daemon restarts.
- Windows helper: `./enable-tailscale.ps1 -Port 8765` checks connection and sets private Serve.
- Setup command: `tailscale serve --bg --yes http://127.0.0.1:8765`. Inspect with `tailscale serve status`. Full HTTPS URL is taken from status, not invented. The existing Folio sign-in startup remains in place.

## F-012 Cover preview

- Editing shows the saved image alongside a draft preview (stacked on mobile). Input is debounced 600 ms and has a retry button. Import-driven rerender refreshes the preview.
- States: empty, invalid HTTP(S) URL, loading, success and display failure. Preview failure alone does not prevent saving a valid URL. No preview changes the database or replaces the saved cover until Save.
- Hitomi thumbnail URLs use a token/origin-protected POST `/api/covers/preview`. This reuses the constrained relay's host/path validation, public-address checks, response format/size/time limits and four-request concurrency limit. It is not a general URL proxy. Responses are `no-store`; blob URLs are revoked on input replacement/navigation.
- Other images load directly with `no-referrer`. Their browser caching follows the remote server; Folio does not persist them or create an offline cache. HTTPS mixed-content restrictions and source access restrictions may prevent display.
- Aborted or stale requests cannot overwrite newer previews. Cancelling the editor preserves the saved URL and all work data.

## Verification and deployment

Tests use disposable SQLite databases. Regression coverage includes Trash/URL claims/counts, missing-information confirmation, race-safe undo, exact scale restoration, batch atomicity/no-ops/expiry/replay, saved-search invalidation, token enforcement and restricted image relay. Browser checks cover both locales and source/share workflows. See VERIFICATION.md for results and remaining real-device checks.
