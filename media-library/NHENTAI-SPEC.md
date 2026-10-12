# nhentai imports and Favorites — implemented specification

Approved 2026-10-13. This document supersedes the historical proposals in `NHENTAI-AND-DUPLICATES.md` for F-004 and F-014. The personal edition retains male/female/neutral attributes; arbitrary user-created attributes belong to the later public edition.

## Official API and adapter

- Official reference: https://nhentai.net/api/v2/docs and https://nhentai.net/api/v2/openapi.json.
- Metadata: `GET /api/v2/galleries/{gallery_id}`. Public retrieval was verified without cookies or a key. Japanese title → English title → pretty title. Retain available originals as searchable matching evidence and title-editing suggestions.
- Maps `artist` to author, `group` to circle, `parody` to series, `character` to character, and `tag` to tag. Recognized categories map to Folio categories. Unknown categories produce warnings. `translated` and `rewrite` are qualifiers, not language names.
- Supports `http(s)://[www.]nhentai.net/g/ID[/]` and `/g/ID/PAGE[/]`. A reader-page URL remains distinct from the gallery URL, including page 1. Trailing slashes, HTTP/HTTPS, www, tracking queries and fragments do not create separate comparison identities. Stored URLs remain intact.
- Individual URL imports, bookmark HTML, bookmarklet and share-target registration use the same adapter. Exact matches across primary/secondary links (including Trash) open the registered entry or skip batch registration before a metadata request. Another page warns and remains independently registerable. Identical titles do not block registration.
- Explicit edit-screen re-import retains F-013 overwrite/merge/keep behavior, empty-result preservation and unchanged-value no-op behavior.
- Metadata is parsed as JSON, never executed. Requests use a fixed public TLS host with pinned public addresses, bounded response size and timeouts; credentials are sent only in `Authorization: Key ...` to that host. No login passwords, browser cookies or verification-challenge automation.

## Display images

Save the cover URL, not image bytes. Use the verified `t.nhentai.net/galleries/MEDIA/cover.EXT` path; interior-page links use the matching page thumbnail `PAGEt.EXT`. Missing/out-of-range page information warns and falls back to the cover. Gallery media IDs come from API paths, not from gallery IDs.

Allow only verified thumbnail CDN hosts `t.nhentai.net`, `t1.nhentai.net`, `t2.nhentai.net`, `t3.nhentai.net`, fixed gallery image paths, HTTPS port 443, and supported image formats. Never send API keys to image hosts. No redirects to arbitrary hosts or general-purpose image proxy. Validate content type, magic bytes, response size and public socket address. Gallery, details and edit preview use the same relay.

The existing bounded RAM cache applies: 2 MiB maximum image, 32 MiB LRU budget, five-minute TTL, four concurrent relay slots. Responses are `no-store`. No image files, database blobs, backup images or offline image service-worker cache. This does not prevent a user's browser/OS from managing its own transient memory.

## Tag policy

- Individual imports default to neutral, editable before saving. The Imports screen allows changing the individual default to frequency.
- Every bookmark/Favorites job selects neutral or frequency independently.
- Match NFKC/case/whitespace-normalized original names and aliases across attributes. Frequency counts distinct active work associations, excluding Trash, per same-name tag. Never use nhentai's global tag count.
- Freeze frequencies and name-to-entity candidates in the job record at creation. That job's own additions never influence its subsequent choices.
- Unique most-used attribute wins only when there is an unambiguous entity for that attribute. Ties, zero uses, unknown names and ambiguous aliases fall back to neutral. Reuse an unambiguous existing neutral entity; otherwise use/create the literal neutral name rather than silently accepting an ambiguous alias.
- Changes apply to imported data, without rewriting existing work assignments or the source's original metadata. Missing/deleted entity IDs are revalidated before saving.

## Cross-site matching (F-014)

Candidate extraction requires an exact normalized title variant (current/retained original titles). NFKC, case and whitespace normalization are allowed; chapters, volumes, punctuation and edition markers are not stripped. Existing author names/aliases are compared with incoming authors; conflicting known authors exclude a candidate. Missing authors cannot prove identity and are explicitly indicated. Language and page count are displayed as supporting evidence, with mismatches flagged. Tags are not an identity test.

Only entries with a different supported source provider are automatic candidates; same-site page differences follow the existing page-warning workflow. Matching-title indexes support large libraries. Display up to 100 compatible candidates; a manual library search is also available, including when no automatic candidate appears.

Individual imports offer the candidates before saving a new draft. The user can add the source to an existing active work, continue as a separate work, or cancel. A manual "Link this URL to an existing work" button is also available in new-entry editing.

Confirmed attachment adds **only a secondary URL**, retained original-title evidence and import provenance. It preserves primary URL, title, cover, metadata, personal notes, purchased state and ratings. The link edit is recorded in operation history and can be undone. A UUID remains the actual work identity.

Batch items with candidates persist metadata as `match_review` and wait for a decision; other items continue importing. Candidate review supports:

1. Add secondary link to the selected existing work.
2. Register as a separate work.
3. Optional **Apply to all in this import job**.

Apply-to-all attaches each other item to its own candidate when there is exactly one; multiple candidates remain for explicit selection. It does not attach all imported items to the work selected for the first item. Separate-work apply-to-all registers every pending match separately. Both decisions are saved as a per-job policy and apply to candidates discovered later. The policy can be reset to Ask in the job screen. Existing pending review items are resolved by the confirmation's apply-to-all operation; changing the future policy alone does not resolve earlier items.

Recheck current candidates, active targets and URL ownership inside the write transaction before attaching. Exact URL claims remain atomic across concurrent imports/edits, and URLs reserved by Trash cannot be attached elsewhere.

## Favorites connection and import

- `GET /api/v2/favorites?page=N&q=...`, using an API key. The list contains lightweight items, so each unregistered gallery also needs a detail request for full metadata.
- Enter the key in Folio's Imports screen. Connect/test retrieves page 1 and shows available titles, page preview and a total only when supplied by the API. Connection testing alone never adds works.
- Optional query uses **nhentai search syntax**, not Folio query syntax. Import either all Favorites matching this query (all pages), or selected works from the displayed first-page preview. First-page checkboxes are enabled only for the selected-preview scope. Empty selections cannot accidentally start an all-Favorites import.
- Manual, additive import only. Repeat runs skip already registered URLs, including secondary links. Upstream unfavoriting never deletes a Folio work. Never change remote Favorites, personal ratings or an existing entry's metadata automatically.
- Retain original source titles/import time. Favorites have no bookmark name; do not invent one. Bookmark imports still retain their actual bookmark names and title-priority choice.
- Collect page URLs in a durable job, deduplicating repeated IDs/pages and committing inserted items and the next-page cursor together. Then process details and registrations. Enumeration and item progress survive browser closure/server restart. Limit jobs to 100,000 works; narrow the Favorites query for larger collections.
- If upstream Favorites change during pagination, repeated URLs are deduplicated; a subsequent import can retrieve items missed by a shifting upstream list. The site does not provide a guaranteed frozen snapshot.
- Jobs show enumeration progress, counts, per-item warnings/failures, candidate review, filtering and incremental display (100 rows initially). Pause, resume, cancel and retry operate on durable state. Match-review payloads survive restart and do not need another remote request to decide.

## Credentials

The key is masked and is never returned by an API response. Without "Remember on this PC", keep it only in server memory. A restart requires reconnecting before continuing a Favorites job.

If remembering is selected, store a Windows-current-user DPAPI envelope at `%LOCALAPPDATA%/Folio/nhentai-api-key.dpapi`. This is outside the repository, SQLite library, OneDrive metadata backups and packages. Use the same Windows account for server startup. The key is removable/replacable from Imports. No key in job JSON, URLs, logs or history.

Favorites jobs store a one-way key fingerprint to prevent a different account/key from silently continuing the original pagination. Reconnect the same original key to resume. A newly generated key requires starting a new additive job; registered URLs are skipped. Disconnect or authentication refusal pauses affected jobs without losing progress. Confirm connection with the user's actual key before claiming real-account Favorites retrieval works.

## Scheduling and error handling

Official gallery limits: anonymous 20/min/IP; authenticated 45/min/IP. Favorites: 15/min/user/key-owner. Shared process pacing uses at least 3.2 seconds between anonymous detail requests, 1.5 seconds authenticated, and 4.2 seconds between Favorites list requests. Remote account usage outside Folio can still consume these shared limits.

429 honors numeric `Retry-After` (bounded to one hour); absent/unrecognized values default to 65 seconds. Persist retry deadlines. Retry transient failures at most four attempts, then leave items failed or pause enumeration for user retry. 401/403 stop for reconnection/access review. 404/invalid schema reports an item failure. Rate-limit waits do not hold a database transaction; cancellation is checked during pacing and before committing fetched information.

## Local API

- `GET /api/nhentai/status`: connected/remembered flags, Windows capability, individual tag default; no key.
- `POST /api/nhentai/connect`: `{key?, remember?, query?}`; read-only remote test, then optional credential replacement.
- `POST /api/nhentai/disconnect`: forget memory and optional DPAPI envelope.
- `POST /api/nhentai/settings`: `{tag_mode: neutral|frequency}`.
- `POST /api/jobs`: existing bookmark items, or `{kind: favorites, query?, tag_mode, items?}`.
- `POST /api/jobs/ID/pause|resume|cancel|retry`: durable control.
- `POST /api/jobs/ID/decide`: `{item_id, action: attach|new, target?, apply_all?}`.
- `POST /api/jobs/ID/policy`: `{policy: ask|attach_unique|new}` for later candidates.
- `POST /api/source-attach`: `{url,target,source_titles?}` for an explicit individual attachment.

Existing same-origin/token guards protect mutations. Work/source/import endpoints retain their previous contracts and now recognize the nhentai provider.

## Verification scope

Automated fixtures exercise official JSON mapping, Japanese fallback, reader pages, fixed hosts, key rejection/rate limits, tag aliases/ties/Trash/snapshot behavior, URL uniqueness, secondary-only changes and undo, apply-to-all/current and future matches, ambiguity preservation, pause/cancel/reconnect, HTTP request guards, DPAPI round trip and absence of keys in library backups. A 2,500-item/100-page fixture restarts enumeration halfway and verifies exact item count.

Live anonymous metadata and RAM relay checks succeeded for gallery 1's cover and page 2 thumbnail. Browser checks use fictional works on a disposable DB for Favorites preview, importing, apply-to-all, manual ambiguous choice, English/Japanese labels and responsive layouts. No real Favorites account has been exercised without a user-supplied key.
