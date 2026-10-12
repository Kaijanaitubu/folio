# Personal Media Database — Requirements Specification v2.0

**Status:** Implementation baseline  
**Date:** 2026-10-11  
**Document language:** English  
**Supersedes:** Requirements Specification v1.0

**Cover-policy amendment:** 2026-10-11. Supported Hitomi covers now use a memory-only relay as defined in Section 7.2; persistent image storage remains excluded.

**Metadata/mobile amendment:** 2026-10-11. Sections 5 and 8.6 define preferred display aliases, directory navigation/sorting, and mobile keyboard behavior. The later F-002/F-003/F-013 amendment below supersedes title uniqueness and old import behavior. The nhentai importer remains a proposal.

This document is self-contained. It incorporates the agreed changes to v1.0 and defines the behavior needed to implement and verify the current release. Developers do not need the preceding conversation. Where implementation details were not explicitly selected, this document specifies practical defaults. Frameworks, database products, and the precise visual theme remain engineering choices subject to the requirements below.

## 1. Product definition

A mobile-first personal media library for cataloging user-created entries, searching metadata, recording personal assessments, and opening external sources. It initially serves one person from a server running on their own PC, accessed through a browser on that PC or other devices on the same LAN.

**The database is the core product. External websites and metadata importers are optional sources of information and links, not the foundation of the database.**

The initial importer supports Hitomi only. Manual entry and source links must work without any importer. The eventual direction is a hosted general media library with registration and separate libraries per account. The current application is not exclusively modeled around adult comics.

### 1.1 Current release scope

- PC-hosted website, accessible on the local computer and LAN.
- One default library owner; no registration or multi-user UI.
- Mobile-first gallery, detail, new-entry, and edit screens.
- Manual metadata editing and multiple source links with one primary source.
- Remote cover-image URLs only.
- Hitomi metadata import inside entry forms.
- Bookmark HTML batch import with persistent progress and results.
- Tag, author, circle, series, and character directories with editing, preferred display aliases, sorting, and merging.
- Configurable rating dimensions.
- Structured search, autocomplete, sorting, and random selection.
- English and Japanese UI switching, implemented in that order.
- Server-side backup and documented restore procedure.
- Design target of 100,000 works per owner; verified minimum of 30,000.

### 1.2 Out of scope for this release

Public hosting configuration, account registration, public sharing, social features, multiple active users, offline operation, browser extensions, additional site importers, table/list library views, trash/recycle bin, image uploads/download storage, purchase tracking beyond yes/no, and a user-facing general library export/import feature.

Future work must be possible without rebuilding the core entry model: account ownership, hosted deployment, additional importers/categories/views, and optional library portability.

## 2. Deployment, ownership, and persistence

1. The server is the authoritative store. Browser storage must not be the only copy of entries or import jobs.
2. Browsers on different devices access the same database. This release does not require device-to-device synchronization.
3. The PC must be running and awake for access. The UI/documentation must explain this limitation.
4. Configure listening address and port. Provide startup instructions, LAN access instructions, and narrowly scoped firewall guidance. Do not automatically publish the service to the Internet or change router settings.
5. This release assumes a trusted LAN. A public deployment requires authentication and authorization before exposure. Optional private remote access, such as Tailscale, is operational guidance rather than a built-in feature.
6. Store ownership on works, metadata entities, rating dimensions, and import jobs. Use one default owner now. Source URL identity and metadata dictionaries are scoped to that owner.
7. Internal IDs must be stable and independent of titles, URLs, names, and external IDs.
8. Data must survive browser closure, server restart, and application upgrades. Supply versioned database migrations.
9. No specific framework or database engine is mandated. A durable relational database is appropriate. Separate importer adapters, search parsing, persistence, and presentation.
10. On this Windows installation, enable a per-user automatic-startup shortcut that starts the existing LAN server silently at Windows sign-in. Reuse the current port, database, duplicate-process checks, and logs. Provide a disable script; do not change system execution policy or install a privileged service. Sign-in startup does not provide server availability before the user logs in.

## 3. Entry identity and validation

An entry is a library record created by the user manually or through import. The application does not infer edition, translation, chapter, or conceptual-work relationships. Identical titles may represent different entries. Stable internal IDs identify works; normalized source URLs prevent duplicate registration across works, subject to preserving legacy duplicates.

### 3.1 Required title and work identity

- Title is the only required field. Trim outer whitespace; a whitespace-only title is invalid.
- Identical titles are allowed. Exact title comparisons are used for import warnings, not work identity.
- Work IDs are stable internal primary keys. Source links are optional; the primary link is mutable.
- All source links participate in owner-scoped normalized URL comparison. Reject new duplicate URLs atomically, excluding the edited work's existing links. Preserve legacy collisions without automatic merging or deletion.
- Individual imports show same-title entries with authors and primary URLs before proceeding. Batches add same-title entries and summarize warnings afterward.
- Different pages of a Hitomi gallery warn but can register separately. Do not automatically match or update works based on title or gallery ID.
- [F-002/F-003/F-013 implementation specification](media-library/IMPORT-SPEC.md) defines normalization, legacy migration and API contracts.

## 4. Work fields

| Field | Type / cardinality | Rules |
|---|---|---|
| Title | Required text, one | Section 3.1 |
| Cover URL | Optional URL, one | HTTP/HTTPS image URL; no stored image bytes |
| Authors | Zero or more references | Individually searchable; directory-managed |
| Circles / groups | Zero or more references | Individually searchable; directory-managed |
| Category | Optional, one | Six initial categories below |
| Tags | Zero or more references | Canonical name + gender identity |
| Series | Zero or more names/references | Individually searchable; `Original` is an ordinary usable value |
| Characters | Zero or more names/references | Individually searchable |
| Language | Optional text, one | Simple value; no translation-management feature |
| Page count | Optional integer, one | Nonnegative; missing is null, not zero |
| Ratings | Zero or one score per dimension | Section 6 |
| Review | Optional plain text, one | Explicit review search only |
| Bought | Boolean | Default false; no unknown state, date, price, or store |
| Source links | Zero or more | Section 7 |
| Created at | System timestamp | Set when entry is first saved |
| Updated at | System timestamp | Set on persisted content changes |
| Last opened at | Optional system timestamp | Updated when the detail page is opened |

Initial categories: **Manga, Doujinshi, Artist CG, Image Set, Game CG, Anime**. Keep stable internal category keys and localized UI labels. Do not make future additions require a schema redesign.

All optional fields may be empty. Missing author/circle information must not become a literal `N/A` entity. Multi-value fields must not contain duplicate associations. Personal text and metadata names retain their original language; switching UI language does not translate stored content.

## 5. Metadata entities and directories

### 5.1 Tags

Each tag has a stable ID, owner ID, canonical name, aliases, and gender:

- `female`
- `male`
- `neutral` — includes unqualified, unspecified, and genderless tags as one concept.

Tag identity is the pair **canonical name + gender** within the owner’s library. The same name can exist separately for each gender. For entity uniqueness, trim outer whitespace and compare remaining canonical names exactly. Aliases are alternate lookup names, not separate tags.

Example: `female:futanari` can resolve through aliases `futa` and `ふたなり`. Importing an unqualified `futa` does not automatically choose the female version merely because its alias exists: resolution is constrained by the importer’s gender, with missing gender interpreted as neutral.

### 5.2 Authors, circles, series, and characters

Each has a stable ID, owner ID, canonical name, and zero or more aliases. They are separate entity types. An author and a circle may share a name without becoming the same entity. Names are unique within the corresponding directory using the same trimmed exact comparison rule.

### 5.3 Directory screens and entry-form controls

Provide a clearly accessible **Manage metadata** area containing Tags, Authors, Circles, Series, and Characters. Each directory supports:

- Search by canonical name or alias. No gender-filter selector in this release; tag gender remains visible on each row.
- Create and edit, including aliases, preferred display name, optional sort reading, and tag gender.
- Tap/click the item's displayed name to open library search using its canonical name, quoted/escaped as necessary. Tags use the specific `female:`, `male:`, or `neutral:` field; other types use `author:`, `circle:`, `series:`, or `character:`. Selecting a neutral tag must not broaden the search to other genders. URL state holds the search query.
- Sort with a selector next to the metadata search field: name ascending/descending (A–Z / kana gojuon), work usage descending/ascending, and creation newest/oldest. Sort the entire matching dataset before pagination; provide Load more without the previous 300-item directory ceiling.
- View how many entries use an item.
- Merge duplicates into a selected survivor.
- Delete with confirmation showing the number of affected entries.

Entry forms support searching/selecting existing items, creating an item, and opening its metadata editor without discarding the entry draft. Use removable chips or equivalent touch-friendly controls for multi-value fields.

Each work-editor metadata field (authors, circles, tags, series, characters) provides a localized Remove all action, disabled when empty. Confirm which field will be cleared, then remove its associations only from the current draft. Save commits the change; canceling the confirmation or discarding the draft preserves saved associations. Shared dictionary records and other works remain unchanged.

Editing shared metadata updates all entries referencing it. Display this fact in the metadata editor. Removing a chip affects only the current entry. Deleting an entity removes its associations but never deletes works.

Merging is explicit and atomic: reassign associations to the survivor, deduplicate associations, preserve useful alternate names as aliases, and remove the absorbed entity. Tag merges are restricted to the same gender; change gender deliberately first if needed. Canceling or failing a merge must not leave partial changes.

### 5.4 Alias resolution

- Exact canonical-name matches within the requested entity type/gender take priority.
- Otherwise resolve an exact alias if it identifies a single eligible entity.
- Ambiguous aliases must prompt the user to select an entity in interactive forms. Never silently merge entities.
- Batch imports with unresolved ambiguity report the item as needing review and skip it; other items continue.
- Search may match all entities sharing an alias because searching does not modify data.
- Do not infer synonyms or translate names automatically.

Series and characters have the same reusable identity, alias, editing, navigation, and directory capabilities as authors and circles.

### 5.5 Preferred display names, sorting, and migration

- Store canonical names independently of display choice. An item uses either its canonical name (default) or one registered alias as its primary display name. This preference belongs to the owner's shared metadata entity, not a device or individual work. UI language switching does not select another alias automatically.
- Apply this label to directory rows, work cards/details/editor chips, metadata selection/merge/ambiguity controls, and search suggestions. Imported drafts resolving to existing metadata immediately inherit the display preference. Canonical names and all aliases remain searchable; choosing a display name must not rename, merge, or re-identify the entity.
- Validate the preferred alias against the saved aliases. Removing it in the editor resets the choice to the canonical name. A merge preserves the survivor's display choice and copies useful source aliases.
- Name sorting uses an optional user-supplied sort reading, otherwise the selected display name. Normalize width/case and kana variants for sorting only; retain names unchanged. An optional kana reading enables pronunciation ordering for Kanji. Without one, Kanji sort by Unicode order, not inferred pronunciation. Latin names precede kana in the combined order; punctuation and other scripts follow their normalized Unicode ordering. Stable tie-breakers are displayed name, gender, and entity ID.
- Record an immutable UTC creation timestamp for newly created metadata. Previous releases did not record it: migrated entries keep an unknown/null timestamp and their insertion order as a fallback. They sort before timestamped entries in oldest-first and after them in newest-first. Editing does not change creation order; usage counts count distinct linked works.
- Apply an idempotent additive schema migration, preserving works, IDs, names, aliases, associations, scores, links, and import records. Existing entities default to canonical display and an empty sort reading. Back up the current SQLite database before activating the upgrade.

## 6. Configurable rating dimensions

### 6.1 Dimension definition

The owner can create any number of rating dimensions; impose no fixed product-level maximum. Each dimension has:

- Stable internal ID and owner ID.
- Permanent positive number used as the search identifier: `rating1`, `rating2`, etc.
- Required display name.
- Maximum score: integer from 2 through 10.
- One symbol choice from ten presets.
- Whether it appears on gallery cards.

Allocate numbers in creation order, monotonically, without reusing deleted numbers. Renaming, deleting, or changing a symbol must never renumber other dimensions. Display dimensions in number order. Duplicate display names are permitted because numbers identify dimensions unambiguously.

No rating dimension is mandatory. Start with an empty configuration and provide a clear Add rating dimension action. The user may create dimensions such as Quality and Erotic appeal.

### 6.2 Scores and display

- Each work can have one integer score from 1 through that dimension’s maximum, or no score.
- Zero is not a valid score. **Clear rating** stores an unrated/null state.
- Display all configured dimensions on detail/edit screens, including unrated dimensions.
- Show number, name, and filled/unfilled positions. Also expose a readable numerical value for accessibility.
- Example: `1. Quality: ★★★☆☆ (3/5)` and `2. Erotic appeal: ♥♥♥♥♡ (4/5)`.
- Do not average dimensions or compute an overall rating.

Ten symbol presets: Star, Heart, Circle, Diamond, Square, Triangle, Flower, Sun, Moon, and Sparkle. Use consistent icon pairs (filled/outline or filled/muted) rather than relying on platform emoji rendering. All presets must represent selected and unselected states, including at a maximum of ten.

### 6.3 Dimension management

- Renaming or changing the symbol retains scores.
- Changing the maximum in either direction converts existing scores after a preview and explicit confirmation. With old maximum `M`, new maximum `N`, and score `s`, compute `1 + (s - 1) * (N - 1) / (M - 1)`. Round fractional parts <= 0.5 down and > 0.5 up (五捨五超入), using exact integer arithmetic. An old full score (`s = M`) always becomes `N`; all other scores are capped at `N - 1`. Unrated stays unrated. Unchanged scales do not convert scores.
- Preview every old-to-new score mapping and the count of works at each old score, plus rated and changed counts. Explain that reducing the scale loses distinctions and increasing it again cannot recover original scores. Cancel changes nothing. Recheck the preview against the current scale and score distribution on save; if another client changed either, require a fresh preview.
- Commit scale, scores, name, symbol, and visibility together in one transaction. Retain rating identifiers, other dimensions, unrated entries, and work timestamps. Example: 3→5 maps `[1,2,3]` to `[1,3,5]`; 5→3 maps `[1,2,3,4,5]` to `[1,1,2,2,3]`; 9/10→2/3 and 10/10→3/3.
- Deletion requires confirmation and removes all scores for that dimension.
- Gallery visibility is configurable per dimension. Default new dimensions to hidden on cards to avoid unlimited card growth.
- Sorting and autocomplete identify each dimension by both its number and display name.
- Search syntax is `ratingN:`. The old generic `rating:` is not supported; explain the available numbered fields when it is entered.

## 7. Source links and covers

### 7.1 Source links

Each link belongs to one work and includes a stable ID, URL, optional label, optional detected source type/external reference, and display order. Multiple external services and arbitrary HTTP/HTTPS links are allowed now, even though only Hitomi has an importer.

- Zero links are valid.
- When links exist, exactly one is primary. The first added link becomes primary; the user can change it.
- Removing the primary link selects the first remaining link by display order; removing the last leaves no primary source.
- Repeating an identical URL within the same work is prevented as redundant.
- An equivalent normalized URL in another work blocks new registration. Preserve existing legacy duplicates when editing their unchanged source keys.
- Preserve the user’s saved URL, including path, query, and fragment. Do not rewrite it to a canonical gallery URL for opening.
- Importer resolution may derive an external ID or metadata lookup URL separately, without replacing the saved link.
- Open Source and the detail-page cover open the primary saved URL in a separate browsing context, preserving the app’s navigation state.
- Display all links on the detail page so other sources are accessible.
- With no source, show the cover normally and omit/disable source-opening actions clearly.

### 7.2 Covers

- Store a remote image URL only; it can be imported or manually entered/replaced.
- Hitomi reader links with a valid one-based `#N`, `#N-M`, or `#N-` fragment use page N's thumbnail as the imported cover. A spread uses its first referenced page. Interior pages use `webpsmalltn`; first-page covers use `webpbigtn`. Invalid/out-of-range pages or missing page hashes fall back to the first page with a warning. No fragment or non-reader URLs retain the first-page cover. Apply this to both interactive and bookmark imports. Existing saved covers are unchanged until explicitly reimported/replaced; source URLs retain their original fragments.
- No file upload, persistent image-byte storage, disk image cache, generated thumbnail storage, or offline image cache is permitted.
- Supported Hitomi thumbnail URLs are displayed through a server relay. Read the target from the saved, owner-scoped work; never accept an arbitrary proxy target from a request. Canonicalize legacy thumbnail URLs using the current source routing table without modifying saved URLs. Fetch over TLS with the source-site referrer, pin a validated public DNS address, and reject redirects, unsupported hosts/paths/formats, oversized or incomplete responses, and non-image content. Other manually supplied image hosts continue to display directly in the browser.
- Relay image bytes may exist only in volatile RAM and the response sent to the browser. Keep an LRU cache capped at 32 MiB, with a five-minute TTL. Coalesce concurrent requests for the same URL. Limit each thumbnail to 2 MiB and the complete fetch/send operation to four concurrent requests. Fetch in bounded chunks with a 20-second upstream deadline; apply a 30-second client-send timeout. Do not preload an owner's entire library.
- Expired cache entries must stop being served immediately and be pruned periodically. Restarting the process starts with an empty image cache. With four active requests, transient image buffers can add approximately 16 MiB beyond the 32 MiB cached-payload cap; this is not a cap on total Python/process/browser memory.
- Relay responses send `Cache-Control: no-store, max-age=0`, `Pragma: no-cache`, `Expires: 0`, correct image content type/length, and `X-Content-Type-Options: nosniff`. No service worker, browser persistence API, image-file writer, database BLOB, image backup, or body logging may retain relayed images. Browser/OS behavior beyond these controls is outside the application's storage guarantees.
- Missing, broken, or externally blocked images show a stable placeholder without preventing browsing or saving.
- Use lazy loading and fixed/aspect-ratio image areas to minimize layout shifts.
- The application must remain usable when external images or sources stop working.

## 8. Library, navigation, and editing

### External source entry amendment (2026-10-12)

Provide a bilingual Settings setup for a navigation-only Hitomi bookmarklet and a pasted-URL fallback. Configure the Folio HTTP/HTTPS origin, prohibit credentials, and explain that phones need the PC LAN address. The bookmarklet accepts only Hitomi/www Hitomi pages and preserves the complete current URL in the `/#/source?url=` hash route. Do not expose the library to the source site or fetch arbitrary URLs.

Check all owner-scoped source links without remote access or work writes. One exact source match opens its detail; multiple exact matches require selection. If only other URLs/pages of the same Hitomi gallery ID match, show a dialog containing registered titles and source URLs before navigation. Offer existing entry, cancel, or importing the current link as new. A new draft retains the submitted URL, fetches supported metadata, and is never saved automatically. Preserve the URL on failure. Same-title imports show an explicit warning with authors and primary URLs and can save as separate entries. Registered exact URLs open detail without reimport; different URLs never cause automatic updates. Late lookup/import responses must not overwrite another route or draft. Validate bookmark execution on the actual mobile browser separately from API/function tests.

### 8.1 Library/home

Opening the app shows the library, not a dashboard. Default to newest added. Use a responsive gallery, prioritizing smartphones while supporting desktop mouse/keyboard interaction.

Cards display cover/placeholder, title, authors, category, a bounded tag preview, and selected rating dimensions. Long lists/text use truncation or expansion rather than unbounded card growth. Selecting a card opens its detail page; clicking a library cover does not bypass the detail page.

Fetch entries in batches rather than loading the entire collection. Display loading, empty-library, no-results, and retryable failure states distinctly.

### 8.2 Persistent actions

Library and detail screens provide a persistent bottom bar: **Search, Random, Add**. Respect mobile safe areas and do not obscure content or input controls.

- Search on a detail page returns to the library search interface.
- Random on the library uses all matching entries for its current filter.
- Random on a detail page uses the entire library, regardless of the query used to reach it.
- Add opens a blank entry form.

### 8.3 Detail

Prioritize cover, title, ratings, category/page count, and source access. Author and Circle remain visible when empty, using a localized Not specified label. Other empty optional fields may be hidden, except rating dimensions which explicitly show Unrated.

Provide Edit and Back to library actions. Opening the detail page updates Last opened at; fetching a card, importing, or opening an external link alone does not. Reloading a detail page counts as opening it. Timestamps use server time, store UTC, and display in the browser’s locale/time zone.

### 8.4 Navigation restoration

Remember the library's last selected sort per browser across home navigation and reloads. A library URL without a sort uses that preference; an explicit URL sort takes priority and becomes the remembered choice. Validate remembered rating dimensions against the current configuration, falling back to Newest added if a dimension was deleted. Search submissions from other pages inherit this preference. Write the resolved sort into the URL, including Newest added, so history and detail-page return links retain their own sorting state. Do not retain search filters merely because the user returns home.

Preserve the library query, sort selection, loaded browsing position, and scroll position when navigating to a detail/edit screen and returning via Back to library or browser Back. Store navigable query/sort state in the URL where practical; use session/history state for scroll restoration.

Restore scroll after the relevant cards have loaded. Random sort must retain its session seed during this round trip. If entries were deleted, restore to the nearest valid position. A full browser restart is not required to retain scroll state.

### 8.5 New/edit forms

Use the same understandable form layout for new and existing entries. All metadata must be editable without using import. New forms are empty except Bought=false and unfilled rating controls.

- Existing entry bottom actions: Save and Delete.
- New entry bottom action: Save; no Delete.
- Cancel near the top. No search bar inside the form.
- Cancel/navigation with changed form data prompts Keep editing or Discard.
- Imported changes count as unsaved edits.
- Disable duplicate save submission while saving; on failure retain the draft and show an actionable error.
- Save persists the complete entry atomically and opens its detail page.
- Metadata directory edits are separate explicit saves; warn that discarding the entry draft does not undo already saved directory changes.
- Delete requires confirmation stating that deletion is permanent. Remove associations, source links, and scores, but retain reusable directory items. No trash in this release.

### 8.6 Mobile utility bar and keyboard

- Keep the search input, magnifying-glass submit button, icon-only Random, and icon-only Add controls available across pages. Typing alone does not navigate; submitting opens the library results for that input.
- On phone widths (700 CSS pixels or narrower), Save/Delete are ordinary in-page controls after the entry form, with enough bottom padding to scroll above the utility bar. They must not float above the keyboard. Desktop may retain floating editor actions.
- Animate the mobile utility bar between its bottom idle position and top search position with a 320 ms ease-out translation. Preserve the same focused input and typed text; interrupted movement starts from the currently drawn position. Viewport resize/pan events and focus changes within the bar must not restart the animation. Other-field editing hides the bar immediately. Respect `prefers-reduced-motion` by moving without animation; desktop positioning is unchanged.
- When the utility search input has focus, move the entire utility bar to the top of the visible viewport, covering the mobile brand/menu area. Keep it there while focus moves to its submit/suggestion/Random/Add controls so taps are not lost during a layout move. Suggestions open downward and remain bounded by the visible viewport. Honor safe-area padding.
- While another text input, textarea, select, or editable field has focus on mobile, temporarily hide the utility bar. This avoids keyboard overlap on browsers that resize either the layout or visual viewport. Restore its normal bottom position after editing loses focus; do not add the keyboard height to the bar's bottom offset.
- Observe focus and VisualViewport changes, including panning and orientation. Verify at 320 and 390 CSS-pixel widths and a reduced-height viewport. Browser simulation cannot establish physical Android/iOS keyboard behavior; retain a phone acceptance check.

## 9. Search and sorting

### 9.1 Search grammar

The precedence is **NOT, then OR, then AND**. OR binds more tightly than AND, unlike many conventional query languages.

```text
author:alp/author:bob rating1:>=4
```

means `(author:alp OR author:bob) AND rating1 >= 4`.

- Unquoted whitespace separates AND groups.
- `/` separates OR alternatives within a group.
- Leading `-` negates one term, e.g. `-tag:example`.
- Each OR alternative is a full expression: `author:alp/author:bob`, not abbreviated `author:alp/bob` (the latter means author Alp OR free word bob).
- Parentheses are not supported in this release. Report unsupported grouping rather than ignoring it.
- Double quotes preserve spaces and reserved characters in values: `author:"Alice Smith"`, `title:"A/B"`.
- Inside quoted values, support `\"` for a literal quote and `\\` for a literal backslash.
- Field names and gender prefixes are case-insensitive.
- Unknown fields, malformed operators, unmatched quotes, empty alternatives, or nonexistent rating dimensions show a readable query error. Do not silently broaden a malformed query.
- An empty query matches the entire collection.

Implement a parser producing a structured query representation, not ad hoc replacement of query text into database statements.

### 9.2 Fields and matching

| Field | Behavior |
|---|---|
| `title:` | Substring matching |
| `author:` | Exact canonical name or alias |
| `circle:` / `group:` | Exact canonical name or alias |
| `category:` | Exact stable category key or localized label |
| `tag:` | Exact canonical name or alias, any gender |
| `female:` | Tag match restricted to female |
| `male:` | Tag match restricted to male |
| `neutral:` | Tag match restricted to neutral |
| `series:` | Exact value |
| `character:` | Exact value |
| `language:` | Exact value |
| `review:` | Substring matching; explicit only |
| `pages:` | Integer comparison |
| `ratingN:` | Integer comparison for that permanent dimension number |
| `bought:` | `true`/`false` or `yes`/`no`, case-insensitive |

Text search is Unicode-aware and case-insensitive where Unicode case folding exists. Trim outer search-value whitespace; do not equate underscores with spaces, alter punctuation, transliterate, or collapse distinct Japanese spellings. Alias matching handles explicitly registered alternative spellings. Case-insensitive search may return several entities whose identity comparisons are case-sensitive; this is acceptable.

Free words perform substring searches over title, author names/aliases, circle names/aliases, category labels/keys, tag names/aliases, series, characters, and language. Exclude reviews, URLs, rating names, and timestamps. Each free word can match any included field; multiple words still obey the grammar.

### 9.3 Numeric comparisons and missing values

Support `>`, `>=`, `=`, `<`, `<=`. A bare integer means equality, e.g. `pages:50`. Invalid numeric values show an error. Rating comparison thresholds must be within 1 through the selected dimension’s maximum; pages thresholds must be nonnegative integers.

Missing values do not satisfy numeric comparisons. Negation is logical complement across works, so `-rating1:>=4` also includes unrated works. Empty multivalue fields match no positive entity term and therefore satisfy its negation.

### 9.4 Autocomplete

Suggest metadata from the current owner’s library while typing partial values. Show entity type, canonical name, aliases where useful, and tag gender. Suggest rating fields with number, display name, and scale. Selecting a suggestion inserts a complete structured term and quotes/escapes it as necessary.

Suggestions use partial matching even where completed structured queries require exact matching. Support touch and keyboard selection; debounce requests and discard stale responses. Never suggest another owner’s metadata in future multi-user operation.

### 9.5 Sorting

Support Newest added, Oldest added, Recently opened, Least recently opened, Highest rated by a selected dimension, and Random order.

- Unopened entries come last for Recently opened and first for Least recently opened.
- Unrated entries come last in Highest rated sorting.
- Deterministic sorts use a stable entry ID as final tie-breaker.
- Random order uses a stable seed for the current browsing session/query so pagination does not repeat or omit entries. Provide an explicit reshuffle action; a new query may create a new seed.
- Sorting does not alter filter membership.
- Deleted rating dimensions cease to be sorting options; fall back to Newest added if the active sorting dimension disappears.

### 9.6 Random selection

The Random button chooses uniformly from the full eligible set on the server, not just the loaded page. It opens the selected detail page; it does not automatically open the external source. With zero eligible entries, display a message without navigating. Repeat choices are permitted; no history-exclusion feature is required.

## 10. Metadata import

### 10.1 Adapter boundary

Provide a Hitomi adapter that recognizes supported URLs, resolves any available work reference, and returns a partial structured metadata result plus warnings. It must not own or dictate the library schema. Verify actual source behavior during implementation; do not assume every saved page/chapter URL is extractable.

- The importer runs on the server and has bounded requests, timeouts, and response sizes.
- Fetch metadata only; do not download media content or cover image bytes.
- An arbitrary saved link remains valid even if no importer recognizes it.
- Import support cannot be guaranteed for every page URL; failure never makes the source URL invalid.
- Isolate source-specific parsing and test it with fixtures so upstream changes can be addressed independently.

### 10.2 Interactive import in entry forms

Import is explicit in New/Edit. Check registered normalized URLs before remote retrieval, excluding the edited work itself. Show same-title matches with authors and primary links; proceeding is allowed. Another Hitomi page warns but is eligible. Resolve ambiguous aliases with the user's choice.

Fill empty scalar fields automatically; use the existing replacement checkboxes for conflicting title, cover, category, language and page count. For author, circle, tag, series and character fields, offer per-field Overwrite / Merge / Keep, defaulting to Merge. Empty existing fields are filled; empty incoming fields leave existing values unchanged regardless of mode. Overwrite replaces associations with the complete imported set; Merge adds only missing identities; Keep preserves existing values. Never delete the metadata dictionary or modify ratings, review or purchase state.

Equal imported fields are unchanged and omitted from the replacement dialog. Compare metadata as resolved identity sets, ignoring order and duplicates but preserving tag gender. Preserve existing order/display data for equal sets. If every importable field is equal or chosen modes produce no actual changes, show No information to change and retain the draft without re-rendering.

Keep all changes in the draft until Save. Cancellation, failure or stale responses leave the draft unchanged. A user-entered title is preserved unless explicitly replaced. Source URLs are not rewritten. Partial metadata is usable. See [implementation specification](media-library/IMPORT-SPEC.md).

### 10.3 Bookmark HTML import

Parse browser-export HTML without executing it or loading embedded resources; preserve nested folders and original labels. Preview unsupported, normalized duplicate, registered and related-page links. Let the user select eligible folders/items.

Choose one job-wide title preference: Source title first (default) or Bookmark name first. Remember it in the browser and persist it in the job. If the preferred value is blank, use the other; if both are blank, fail for review. Metadata retrieval failures remain failures.

Skip normalized URLs already registered in any source link or repeated in the batch, rechecking before retrieval and inside the save transaction. Same-title results create separate works; never update an existing work. Another page of the same Hitomi gallery is allowed with a warning. Commit each work, immutable bookmark provenance and final item result atomically.

Store original bookmark name, source URL, source title, folder, title preference and import time separately from editable link labels. Preserve this history during normal saves and reimport. Show original names as title candidates only while editing the title. Tapping/clicking/keyboard-activating a candidate replaces the entire draft title; it does not append or save automatically. Backfill recoverable successful historical job labels; do not infer unavailable names. Legacy import time uses the recorded job start time.

Show progress and durable Added / Skipped registered URL / Unsupported / Failed / Needs review results. Summarize same-title and related-page warnings in expandable final reports with authors and primary links. Keep legacy duplicate-title skip reports readable.

Jobs survive browser closure and resume pending items after server restart. Provide bounded retries and cancellation; completed entries remain and cancelled in-flight retrieval must not create a new work. Source-entry bookmarklet/share routing opens registered detail without invoking this importer. F-013 applies only to explicit edit-screen reimport.

## 11. Localization and accessibility

- Implement English first, then Japanese. Both are required for completion of this release.
- English is the default and fallback language. Provide an explicit language selector and remember the choice per browser.
- Use localization resources for interface text, validation, dialogs, menus, import status, category labels, and accessibility labels. Avoid building Japanese translations into business logic.
- Keep search field identifiers (`author`, `rating1`, etc.) stable English identifiers in both UI languages. Autocomplete/help can explain them in the selected language.
- Do not translate user-entered names, reviews, rating names, or imported titles automatically.
- Use accessible control names, visible focus, sufficient contrast, keyboard support, and touch targets approximately 44 CSS pixels or larger for main controls.
- Symbols must have text/numeric equivalents and not convey scores through color alone.
- At typical phone widths, avoid page-level horizontal scrolling. Forms and ten-position ratings must fit or wrap cleanly.

## 12. Error states and protection of data

Provide clear loading, success, empty, validation, network-failure, and retry states. Never discard form drafts on server validation or network failure. Display errors near the relevant input and in a readable summary when needed.

Use parameterized database operations, escape user/imported text when rendering, protect state-changing requests against cross-site abuse, and validate source/cover URL schemes as HTTP/HTTPS. Restrict server-side importer requests to explicitly supported public source hosts; validate redirect destinations and prevent requests to local/private network addresses. Saving an arbitrary source URL must not itself cause the server to fetch it.

Log operational failures without retaining unnecessary imported payloads or image bytes. Do not place reviews or entire bookmark collections in routine logs. Apply transactional writes to work saves, uniqueness enforcement, metadata merges/deletes, and rating-dimension changes.

## 13. Capacity and performance

- Target 100,000 works per owner. At least 30,000 works must be tested before release.
- Use indexed owner-scoped lookup and relationships, bounded pagination, and server-side filtering/sorting.
- Cover loading must not block metadata rendering.
- A supported search or random action must operate over all qualifying entries, regardless of pagination.
- Use realistic benchmark data with multiple authors/tags/source links and multiple rating dimensions, not just title-only rows.
- Suggested acceptance budget on the documented development PC: first metadata page, representative queries, and random selection each complete within 2 seconds at 30,000 entries under normal single-user use, excluding external image/import latency. Record hardware, dataset, and measurements. Treat 100,000 as a measured design target, not an untested guarantee.
- If a query class misses the budget, document and address the bottleneck before claiming scale support. Source fetching speed depends on the external service and is evaluated separately.

## 14. Backup, restore, and delivery

Provide an automated or one-command consistent database backup and a documented restore procedure. Store backups outside the live database location and allow configuring the destination. A default daily backup with retention of seven successful copies is an appropriate operational baseline. Explain that another disk/location is needed to protect against disk failure.

Backups include entries, all metadata dictionaries/associations, links, rating configuration/scores, timestamps, ownership, and persistent import-job state. They contain cover URLs but no image files. Back up through a database-supported method; do not assume copying an actively written database file is safe.

Restore must be tested into a fresh application instance. User-facing library export is not required. Deliver source code, dependency/setup instructions, startup instructions, environment/configuration example, migration procedure, backup/restore instructions, and validation results. Include no credentials in source or examples.

## 15. Conceptual data relationships

Equivalent implementations are allowed, but must preserve these relationships:

```text
Owner / Library
  -> Works
       -> SourceLinks (one primary when nonempty)
       -> WorkAuthors -> Authors -> AuthorAliases
       -> WorkCircles -> Circles -> CircleAliases
       -> WorkTags -> Tags(name, gender) -> TagAliases
       -> WorkSeries -> Series
       -> WorkCharacters -> Characters
       -> WorkRatings -> RatingDimensions(number, name, maximum, symbol, galleryVisible)
  -> Metadata dictionaries and RatingDimensions
  -> ImportJobs -> ImportJobItems
```

Enforce ownership consistency across associations. Metadata is private to an owner, not a global shared vocabulary. Category definitions may be application-wide stable values. Referential integrity and delete behavior must implement the rules above.

## 16. Acceptance checks

The release is complete only when the following behaviors are verified. Use focused automated checks for persistence/search/import rules and manual browser checks for layout/navigation/localization.

### Entries and sources

1. Save a title-only entry; every other field may be absent.
2. Reject empty/whitespace titles; allow identical titles as separate entries and show appropriate import warnings.
3. Reject concurrent equivalent-source URL saves atomically; allow linkless works and exclude the edited work itself.
4. Save an unsupported source URL and open the exact path/query/fragment supplied.
5. Add multiple links, switch primary, remove primary, and verify fallback selection.
6. Broken covers show placeholders; no server image bytes are stored.
7. Edit/cancel/delete follow draft and confirmation rules; save failures retain values.

### Metadata and ratings

8. Create equal-name female/male/neutral tags as separate entities; reject equal-name/equal-gender duplicates.
9. Resolve an alias appropriately; an ambiguous interactive import prompts rather than merging.
10. Editing, deleting, and merging directory items update affected associations without deleting works.
11. Create at least twelve rating dimensions, demonstrating no hard-coded two-axis or ten-axis limit.
12. Scores support 1 through maximum plus clear/unrated; zero is rejected.
13. Rename/change symbols without score loss. Preview and confirm scale changes, verify the example mappings, half ties, full-score exclusivity, unrated preservation, stale-preview rejection, cancellation, and transactional rollback.
14. Delete dimension 2, create another, and confirm dimension 3 stays `rating3` and number 2 is not reused.
15. Gallery visibility and per-dimension sorting work independently.

### Search and navigation

16. Verify `author:alp/author:bob rating1:>=4` against a fixture where conventional AND-first precedence would produce a different result.
17. Verify NOT, quoted spaces/slashes, quote escaping, all numeric operators, missing values, aliases, and each supported field.
18. Free-word search finds metadata but does not find review-only matches; `review:` does.
19. Invalid queries display errors rather than silently matching the whole library.
20. Autocomplete inserts valid expressions and works by touch/keyboard.
21. Random selects from the complete filtered set on the library; detail-page Random ignores that filter.
22. Returning from detail/edit restores query, sort, and scroll, including stable random order.
23. Detail opening updates Last opened at; card loading and import do not.

### Import, operation, and localization

24. Interactive import accepts partial results, handles total failure, preserves personal fields, and only overwrites conflicts when selected.
25. Same-title imports are allowed with authors/primary-link warnings; equivalent registered URLs are skipped. Verify both bookmark title priorities, fallback, stored name candidates and per-field overwrite/merge/keep.
26. Bookmark HTML with nested folders, unsupported links, repeated URLs, and failed items produces accurate preview/results without executing uploaded content.
27. Closing the browser and restarting the server preserve job progress without re-adding successful items.
28. Retry/cancel behave as specified and do not roll back previously completed entries.
29. At least one end-to-end Hitomi import succeeds against the source during verification; record tested URL types and known limitations. Fixture-only testing is insufficient to claim a working live importer.
30. English and Japanese cover the complete main journeys, dialogs, errors, and management screens; user content remains unchanged.
31. Test smartphone and desktop layouts, keyboard access, and empty/error states.
32. Verify LAN access from another device, persistence after restart, and a full backup/restore round trip.
33. Benchmark realistic 30,000-entry data and report 100,000-entry measurements or remaining limits honestly.

## 17. Suggested implementation sequence

1. Establish persistent owner-scoped schema, migrations, and backup/restore.
2. Build English manual-entry, gallery, detail, edit, and source-link journeys.
3. Add directories and configurable ratings.
4. Implement the specified search parser, autocomplete, sorting, and navigation restoration.
5. Implement and verify the Hitomi adapter and interactive import.
6. Add persistent bookmark batch jobs and result handling.
7. Complete Japanese localization and mobile/accessibility QA.
8. Run acceptance checks, benchmark scale, and document deployment and limitations.

No application feature depends on the importer succeeding. Future hosted accounts must retain existing ownership boundaries, permanent rating numbers, user-editable data, and source-independent work identities.

**Import identity amendment — 2026-10-12:** F-002/F-003/F-013 are approved and implemented. Migration 3 removes work-title uniqueness, adds normalized source identity and bookmark provenance, and preserves existing data. The separate [implementation specification](media-library/IMPORT-SPEC.md) is authoritative for these features.
