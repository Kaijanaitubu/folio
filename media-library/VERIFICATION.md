# Verification record — 2026-10-11

## Mobile search slide — 2026-10-12

The utility bar now uses a 320 ms ease-out translation on mobile search focus/blur, including interruption from its current drawn position. Desktop and reduced-motion preferences bypass the slide; viewport changes do not restart it. JavaScript syntax and the existing source-flow/rating-editor checks pass. No backend or saved library data changed.

Browser verification at 586×884 observed the focused bar moving from y=812 through y≈247 to y=0 while the same `query` input retained focus. Blur also produced an intermediate return position before settling at the bottom. Focusing another form input still hides the bar, with no console errors. This verifies browser rendering, not a physical Android/iOS keyboard. A cropped screenshot of the settled top bar is in ignored `test-output/search-motion-mobile.png`.

## Rating scale conversion — 2026-10-12

60 Python checks passed (39 core, 13 HTTP/job, 8 relay/cache), plus `node test_rating_flow.mjs`, `node test_source_flow.mjs`, and JavaScript syntax checks. All database tests used isolated disposable databases. Conversion covers all 81 scale pairs from 2–10, exact half ties rounding down, monotonic scores, exclusive full marks, the specified 3↔5 examples, unrated entries, unchanged scales, stable dimension numbers, other-dimension and timestamp preservation, preview cancellation, stale/missing confirmations, HTTP token enforcement, and atomic rollback.

The actual editor handlers were exercised with DOM stubs in Node for English/Japanese preview and confirm, cancellation, changing the proposed scale, unchanged/new dimensions, stale previews, and late responses after dismissal. This is not a browser rendering test. Browser inspection was rejected by the browser URL policy while selecting the QA tab; no alternate browser automation was used. Mobile/desktop layout has not been visually verified for this dialog. QA data and helpers remain excluded from Git and the distribution ZIP.

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

## Import identity, bookmark provenance and explicit reimport (F-002/F-003/F-013)

2026-10-12. The approved [implementation specification](IMPORT-SPEC.md) was committed and pushed as `a427f28` before implementation began. Work IDs remain stable; normalized source keys, not titles, prevent new duplicate registration.

- **69 Python tests passed**: `test_app`, `test_imports`, `test_server`, `test_cover_relay`. Isolated tests verify same-title works, URL normalization and meaningful differences, primary/secondary matching, concurrent saves with one winner, self-edit exclusion, title warnings with author/primary link summaries, bookmark title priorities and fallbacks, provenance preservation, skip-before-fetch, cancellation after fetch, job restart and v2 migration. Historical conflicting URLs survive migration and editing; deleting a legacy representative reassigns its source claim. Migration checks all original columns and foreign keys. Tests use temporary databases; no personal entries are created or edited.
- **Three JavaScript suites passed**: `test_source_flow.mjs`, `test_import_flow.mjs`, `test_rating_flow.mjs`. Actual application functions verify registered-link navigation without import, related-page choices, unsaved drafts, English/Japanese controls, overwrite/merge/keep, empty-field behavior, unchanged ratings/reviews/purchase state, same-title confirmation, cancellation, ambiguous-alias cancellation, and stale response guards.
- **Browser verification** used a separate fixture server on 8766 with fictional entries and a mocked importer. Original bookmark name appeared on title focus and selecting it changed only the draft. Per-field Author=Overwrite and Tags=Keep applied correctly; saving retained the review and rating. HTML upload preview excluded an HTTP/www/empty-query equivalent URL and permitted a related page with a warning. Batch completion added same-title works and showed an expandable report containing the existing author's name and primary URL. Both English and Japanese rendered correctly; console errors were absent.
- **Phone-size viewport**: 390×844. Title candidates fit without horizontal overflow; focus hid the utility bar. This is viewport/focus testing, not a physical Android keyboard test.
- **Live activation**: no active jobs; SQLite integrity and foreign-key checks passed. Migration created a backup in `data/migration-backups/`. Fingerprints of every original column in owners, works, entities, aliases, associations, links, dimensions, scores, jobs and job items matched before/after. All **1,700 works** were preserved, **1,684 historical bookmark names** recovered and **1,700 source claims** created. The server restarted on the original LAN port 8765. Read-only API lookup returned exact matches; importing a registered URL returned 409 before source retrieval. No personal works were modified for testing.

Local QA screenshots (ignored by Git): `test-output/import-choices-ja.png`, `test-output/import-report-en.png`, `test-output/import-title-mobile-ja.png`. Database fingerprints and synthetic fixtures remain under ignored `test-output/`; no private database, original bookmark names, credentials or artwork are included in the Git commit/package. Existing source metadata parsing and image relay behavior were not changed; live upstream retrieval was not repeated for this feature.

## Bookmark candidate activation and unchanged reimports

2026-10-12 follow-up. Candidate pointer-up handling now replaces the whole draft title even when touch focus/blur prevents the subsequent click. Click and keyboard activation remain supported. Blur retains candidates while selecting or moving focus to a candidate; cancellation and stale editor handlers leave the draft intact.

All three JavaScript suites passed. Import-flow tests additionally verify pointer-down/blur/pointer-up without a click, keyboard selection, whole-title replacement, resolved aliases and stable IDs, distinct tag genders, reordered/duplicate metadata sets, omitted equal fields, all-equal no-op imports in EN/JA, and no-op results after default merge. Equal arrays retain their original reference/order; ratings, notes and links stay unchanged.

A mocked, isolated fixture server verified title replacement at 390×844, the Japanese no-change notice without a modal, and a confirmation containing only the differing language value while equal authors/tags/series were omitted. Cancelling retained the edited language. No production entries or DB schema were modified; this verifies browser viewport/interaction and simulated pointer event order, not a physical Android device. Screenshot: ignored `test-output/import-only-difference-ja.png`.


## 2026-10-12 — F-006–F-009 and F-012

- All 90 Python behavioral/HTTP tests passed on isolated databases. Added coverage for Trash exclusion/URL reservation/restore review, expiration, field-aware undo, exact scale recovery including Trash, stale-edit rejection, atomic batch conflicts/no-ops/expiry/replay, saved searches and deleted axes, CSRF protection, restricted transient image preview and PWA resources. The legacy migration claim-release check now uses permanent deletion; ordinary deletion intentionally reserves claims in Trash.
- All three existing Node source/import/rating flow suites passed; app and worker syntax checks passed.
- Real browser on disposable port 8766: Japanese and English UI, displayed/all-results selection, batch purchase changes, preview counts, apply and undo, named-search save/open, previewing an unsaved image URL without saving it, cancelling the image edit, deletion to Trash, exact source URL restoration, shared exact Hitomi URL opening details without import. Preview summary uses human-readable modes and values.
- 10,000 disposable works: preview 0.58 s, apply 1.39 s, undo 1.12 s. All 10,000 purchase flags restored. This measures a simple purchase-status batch, not a full metadata-heavy 100,000-work benchmark.
- Production: backup created before restart; 1700 works, 3049 dictionary entities, 1700 links, 120 ratings, 1684 provenance rows and 1700 source claims preserved. SQLite integrity and foreign-key checks passed. Production server restarted on 8765. Test mutations never targeted the production library.
- PWA manifest, share landing route, network-only service worker and install guidance implemented. Private Tailscale Serve setup requests administrator enablement; as of verification, HTTPS/Serve is not enabled and HTTPS cannot yet be checked. Reno5 A / Brave installation and appearance in the Android share sheet require real-device confirmation after HTTPS setup. Public Funnel is not enabled.
- Temporary browser screenshot: `test-output/features-mobile.png` (disposable fixture). Screenshots, fixtures, databases and backups remain excluded from Git.
