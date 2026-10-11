# Verification record — 2026-10-11

## External source entry — 2026-10-12

54 Python regression tests pass: 34 core, 12 HTTP/job, 8 cover/cache. New checks cover all-source lookup, exact/related page discrimination, multiple registrations, unsupported/unsafe URLs, no remote fetch or opened-at change during lookup, token protection, and duplicate-title preview with unchanged save uniqueness. `node test_source_flow.mjs` verifies actual source-flow functions for direct opening, related-page dialog choices/cancel/new import, full URL preservation, no automatic saving, and ignoring stale import responses. It also executes the generated bookmarklet in a sandbox to check its target, fragment/query encoding, unsupported source rejection, and unsafe target rejection. JavaScript syntax and patch whitespace checks pass.

No connected browser was available in this session, so rendered UI, clipboard/drag setup, actual bookmarklet execution in Android Brave, and mobile layout have not been verified for this feature. A pasted-URL fallback is provided; no claim of verified native Android share-sheet or extension integration is made. QA uses a separate database and fictional metadata without remote image fetching.

## Bulk metadata clearing and linked-page covers

The updated suite passes 50 tests: 32 core, 10 HTTP/job, and 8 relay/cache checks. New cases verify per-kind association clearing preserves dictionary records and other works, one-based reader-page and spread selection, original first-page behavior, invalid/out-of-range fragments, missing hashes, and the interior-page thumbnail format. JavaScript syntax checks pass.

Browser checks used two fictional works in a separate disposable database, each with 20 associations of every kind. All five clear controls worked; cancel preserved the chips, edits did not change saved data before Save, and discarding restored 20 authors. Saving cleared only the chosen work and retained the other work and all 100 dictionary items. Japanese labels and disabled empty-field buttons fit a 390×844 viewport without horizontal overflow.

Official Hitomi reader JavaScript confirms one-based numeric fragments and spread fragments selecting their first page, using gallery file order. A live page-7 `webpbigtn` request returned 404; `webpsmalltn` succeeded. The implemented importer and RAM-only relay returned `image/webp`, 13,604 bytes, with no warnings. No artwork was displayed or written to files. Existing saved covers were not modified. Source: https://ltn.gold-usergeneratedcontent.net/reader.js

## Automated checks

29 core regression tests passed. These cover title-only persistence, trimmed exact title uniqueness, invalid-write rollback, tag gender identity, aliases and ambiguity, preferred display labels across all five entity types without changing identity/search, invalid preferred aliases and removal fallback, immutable creation order, name/usage/date sorting and pagination beyond 300 entities, kana normalization and explicit Kanji readings, idempotent migration from the old schema, merge display-choice retention, OR-before-AND semantics, review exclusion, quoted values and Unicode case folding, numeric comparisons and null negation, invalid-query rejection, more than ten dimensions, permanent dimension numbering, score bounds and dimension deletion, exact source URLs and duplicate warnings, directory merges/deletion, detail timestamps, seeded pagination, bookmark folders, importer fixtures, Japanese-title priority/English fallback, restricted CDN routing/legacy URL resolution, and full backup restoration including job state.

10 HTTP/job tests passed. These cover preferred alias editing/retrieval, paged metadata queries, suggestions displaying preferred aliases while inserting canonical names, inherited display labels in imported drafts, request token/origin rejection, create/update/open/search/delete API behavior, duplicate-title/partial interactive imports, bookmark parsing, persisted job recovery with duplicate-title skipping and successful atomic item creation, thumbnail URL resolution, and the volatile cover endpoint. Relay checks verify binary bytes/content type, repeated-request caching, HEAD behavior, browser no-store headers, cross-site rejection, unsupported/missing saved targets, failure fallback, unchanged saved metadata, no image files, and exclusion of image bytes from a real SQLite backup.

8 dedicated cache/upstream tests passed. These cover LRU eviction and byte budgets, expiry and pruning, empty cache initialization, oversize rejection, concurrent request coalescing, failed fetch cleanup, public-address socket pinning, source referrer, redirects, MIME/signature validation, announced and unannounced response size limits, truncation, and rejected private/unapproved targets. Total: 47 tests.

Python compilation and JavaScript syntax checks passed.

Windows automatic-startup follow-up: installed a shortcut in the current user's Windows Startup folder, targeting Windows Script Host and the application's hidden launcher. The launcher invokes the existing background script under the existing RemoteSigned policy. After stopping the recorded app process, launching this exact shortcut created a new recorded server process; `/api/config` returned HTTP 200 and the port 8765 listener matched that process. Invoking the shortcut while the earlier server was running also completed without launching another server. This verifies the installed launch path; an actual Windows reboot/sign-in was not performed. The reversible installer supports `-Disable`, which removes only its matching startup shortcut and leaves the running server alone. No privileged service, execution-policy change, or firewall change was made.

Library-sort preference follow-up: JavaScript syntax passed. An isolated browser test selected Oldest added, visited Metadata, returned via the Library link, and reloaded: Oldest added remained selected. An explicit Recently opened URL took priority, and a search submitted from Metadata retained Recently opened. No live library entries or server settings were changed. Invalid/deleted rating sort choices resolve to Newest added.

## Live importer

Metadata-only verification against `https://hitomi.la/galleries/1036181.html` succeeded: title present, page count 222, cover URL present, no adapter warnings. No work was saved and no media/image bytes were downloaded. Hitomi's metadata host had changed from `ltn.hitomi.la` to `ltn.gold-usergeneratedcontent.net`; the adapter uses the current host. Cover URL extraction was verified; successful display of every external thumbnail is not guaranteed.

The same live metadata import was also verified through the running application's HTTP API, with title, page count, and cover URL retrieved and no work saved.

Revision investigation confirmed referrer-based thumbnail blocking: a routed WebP GET returned 404 with no referrer or the local-app referrer, and 200 with the source-site referrer. AVIF also returned 200 with the source referrer. Only response headers were read; image bodies were not read or stored. The adapter now mirrors the current title/thumbnail rules, but direct external embedding remains blocked in this environment. Full observations: `THUMBNAIL-INVESTIGATION.md`.

A read-only metadata check of the source already present in the user's library confirmed that it has a Japanese title and that the revised parser chooses exactly the source's displayed-title field. No saved work was changed by this check.

## Memory-only relay follow-up

The user subsequently approved receiving thumbnail bytes in RAM. The historical direct-embedding limit above is resolved by a separate Hitomi relay; the importer itself remains metadata-only. A live saved cover returned HTTP 200 with `image/webp`, 28,900 bytes, and `Cache-Control: no-store, max-age=0`. A repeated request returned identical bytes. No new files were created in the data/backups directories during these requests. Image bodies were retained only in memory by the check, not printed or saved.

Browser verification confirmed that the saved cover used the same-origin `/api/works/ID/cover` endpoint, completed successfully, and decoded to 452×640 pixels with no cover placeholder and no console errors. The personal library's cover/title/source fields were not changed by the relay. Its startup cache is volatile: 32 MiB cap, five-minute TTL, 2 MiB image limit, and four concurrent fetch/send requests. Code and regression checks cover cache eviction and failure cases; the live test confirms the current source accepts this relay, not every future source/network condition.

The local startup now refuses a second server on an occupied port. This addresses the older foreground instance found during activation; it was stopped after verifying it served this workspace's application source. The current server preserves the existing database.

## Scale measurements

Windows 11 (build 26100), bundled Python 3.12.14. Isolated datasets include reusable authors/circles/tags/aliases/series/characters, four tag associations per work, source URLs, and three rating dimensions. These are single-run measurements on this PC, excluding external network/image latency; they are not multi-user load guarantees.

| Operation | 30,000 entries | 100,000 entries |
|---|---:|---:|
| First metadata page | 0.044 s | 0.078 s |
| Title substring | 0.196 s | 0.118 s |
| Tag AND rating | 0.755 s | 1.655 s |
| Author OR + page comparison | 0.664 s | 1.484 s |
| Free-word metadata query | 0.414 s | 0.895 s |
| Uniform random pick | 0.028 s | 0.038 s |
| Seeded random order | 0.096 s | 0.171 s |

The sample author OR/page query has no matching records in this synthetic dataset; it still evaluates the query across the dataset. Dedicated regression fixtures verify nonempty OR-first result membership.

## Browser checks and practical limits

Verified browser startup, gallery empty state, rating-dimension creation, work creation/save, persisted detail view/rating score, tag creation with aliases and assignment to a work, English/Japanese switching, and a 390×844 mobile viewport without horizontal overflow. QA entries are stored in an isolated test database, not in the user's live library. Known application validation/search errors have Japanese translations; unexpected external source diagnostics may retain their original English text.

Revision browser checks verified black/orange default styling, light/dark switching, bottom search visibility across routes, explicit magnifying-glass and Enter submission (typing alone stays on the current page), and visible Search/Random/Add controls at 320×844 and 390×844.

Metadata/mobile follow-up checks used a separate `test-output/features.sqlite3` instance with fictional works and no remote covers. Selecting a Japanese display alias preserved its canonical name and appeared on directory rows, gallery cards, detail links, and editor chips. The name link opened `female:"blue archive"` and returned one matching work; a series link opened `series:"Blue sky"` and returned one work. Sort selection visibly reversed the directory order. The optional kana-reading field saved successfully; both languages render the updated controls.

Activation created a consistent SQLite backup before migration 2. A before/after content fingerprint of all existing works, canonical entities, aliases, associations, links, dimensions, scores, owner information, jobs, and item content matched; only new metadata columns and permitted running-job recovery state were excluded. SQLite integrity and foreign-key checks passed. The app was restarted on its original LAN port with the user's existing library.

At 320×844 and 390×844 there is no horizontal overflow. The directory header now wraps its Add action on phones. Focusing an editor title sets utility visibility to hidden while Save/Delete have `position: static`. Focusing utility search sets the entire bar at visible top 0; Search/Random/Add remain within the viewport. A reduced-height 390×440 viewport retains this behavior. Clicking the top-positioned Add control at 320 pixels opens New work and returns the utility bar to its bottom location. `preview-metadata-mobile.jpg` captures the fictional mobile directory. Physical phone software-keyboard behavior remains unverified; this is browser focus/viewport simulation, not Android/iOS device testing.

LAN access from a separate physical phone has not been verified: firewall/Wi-Fi isolation depend on the user's network. Both browser languages are implemented; upstream diagnostics may retain source-specific English text. The single-user server uses Python's standard HTTP server and is intended for trusted private LAN operation. A public/multi-user release needs production deployment, authentication/authorization, and further concurrency/load testing.
