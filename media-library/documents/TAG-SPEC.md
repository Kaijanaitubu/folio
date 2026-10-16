# Tag editing and identity — implemented 2026-10-13

This supplements section 5 of the requirements and the nhentai tag policy. It changes personal-library tag behavior; arbitrary user-defined attributes for the public release remain deferred.

## No attribute

- `neutral` remains the compatible internal value for no attribute. Input `none` is also accepted. No additional unspecified/genderless identity is introduced.
- Attribute selectors show **None** / **未指定（none）**, Female and Male. Normal chips, directory rows, pickers and warning labels omit the no-attribute suffix/badge.
- Directory navigation uses `none:"canonical name"` for no-attribute-only results. Existing `neutral:` searches and saved searches remain valid. `tag:` still includes every attribute.

## Work-scoped editing

- Clicking a tag chip in a work editor opens **Tag on this work**, with an attribute selector and **Edit shared tag** button.
- Changing the attribute matches the primary name and every alias against names/aliases with that attribute. Reuse one candidate; ask when several match, without preferring an exact spelling over a conflicting alias.
- When absent, prepare a draft tag retaining the original name, aliases and display/sort preferences. Create it only when the work is saved. Cancel/discard creates no shared tag.
- Replace only this work's association, deduplicating a target already on the work. Other work associations and the original shared tag stay intact.
- **Edit shared tag** opens the shared editor inside the dialog, keeping unsaved work fields. Shared saves/merges take effect immediately and show the existing all-works warning. Return to the local attribute dialog afterward. A newly pending tag without an ID becomes globally editable after saving the work.

## Canonical names and aliases

- Match tag names and aliases together within the requested attribute, using NFKC, case folding and collapsed whitespace. Keep original stored/displayed spelling. A canonical match must not silently outrank another tag's alias.
- One candidate: reuse it in individual/batch imports. Multiple candidates: ask in individual imports; persist a `tag_review` item with its metadata and candidate IDs in bookmark/Favorites jobs. Other items continue.
- The import-results page offers **Choose tags**, including a filter for tag-review items. Select an existing tag for each ambiguous name, then continue registration or cross-source work matching without another remote fetch. Review progress survives restart. Revalidate choices and URL uniqueness inside the transaction.
- Manual create/rename/alias addition checks newly introduced names. Warn with existing names, attributes, aliases and usage. A new manual tag can use an existing tag, retain separate tags when exact canonical uniqueness permits, or cancel.
- Editing an existing shared tag offers an explicit merge into a conflicting tag, preserving unsaved aliases in that same atomic merge. Cancel returns to the populated editor. Keeping separate tags requires acknowledging the current collision set; a changed set is checked again.
- Different attributes remain separate identities. An alias belonging only to a different attribute does not trigger automatic reuse or merge.
- nhentai retains its neutral/frequency choice and frozen usage policy. Frequency ties, unknown names and ambiguous attribute candidates fall back to no attribute. If several tags match that chosen attribute, require a tag decision instead of manufacturing a literal duplicate. Earlier frozen entity IDs follow explicit merge redirects; fresh imports still respect their chosen attribute policy.

## Shared merge and recovery

- List every other tag as a potential target, including same-name/different-attribute tags. Search names/aliases and show display name, non-empty attribute, aliases and usage.
- Preview source → target, affected work count and the shared effect; confirm before applying. Reject a stale preview.
- Transfer all associations, including Trash, deduplicate, and union source aliases plus source names. Do not add the target's canonical name as a redundant new alias. Preserve the target's primary name, attribute and sort reading.
- Store old-ID redirects. Existing drafts, frozen importer IDs, old work history and Trash snapshots can resolve them. Chained merges flatten redirects. These are ID redirects, never permanent name-to-attribute rules.
- Record the merge in operation history for 30 days. Undo restores source/target aliases, original association sets and preceding redirects atomically. Refuse undo if the target metadata, target association set or relevant redirects changed afterward. Unrelated work fields may change without being overwritten.
- Shared directory rename/delete remains outside operation undo. Merge recovery is available through History; restore a pre-update SQLite backup if reverting to an older application version without this schema.

## Persistence and verification

Migration 7 adds redirects and normalized lookup indexes without changing existing names, attributes or associations. API conflicts return 409 and structured choices; mutation endpoints retain the existing request token/origin guards. No media or credential storage changes are involved.

`test_tags.py`, the tag HTTP cases and `test_tag_flow.mjs` cover work scope, deduplication, deferred creation, normalized collisions, collision acknowledgments, ambiguous-job review, cross-attribute merge, Trash/history/frozen-ID compatibility, chained merge undo, stale guards and English/Japanese UI. Browser verification uses a disposable library, not the personal collection.


## Primary names — 2026-10-15

- Tags, authors, circles, series and characters all use **Primary name / 主名称** and **Choose primary name / 主名称を選択**. Choosing an alias swaps the form fields immediately: the chosen name becomes the primary name; the previous primary moves to aliases. Save commits the draft; Cancel discards it. Repeated switches retain the other names without duplicating the primary in aliases.
- This is a real `entities.name` change, not a presentation override. Keep entity ID, creation time, sort reading, attribute, all active/Trash associations and redirects. A directly typed rename also retains the former primary as an alias; a later edit can remove unwanted aliases.
- Primary and former names remain searchable, selectable and resolvable by imports. Tag attribute replacement searches all names, and the existing frequency snapshot indexes all aliases as before. No name-based reassignment of works occurs.
- Tag promotions use the existing normalized same-attribute collision review. Other metadata promotions into another exact primary name now offer a reviewed merge instead of a database uniqueness error. Show candidate names, aliases and uses; cancel retains the draft. Merges use the existing preview, signature guard, redirects and recoverable history. Do not merge ambiguous metadata automatically.
- Migration **14** promotes existing display aliases and retains the former primary in aliases. It runs once, performs name exchanges in two phases to respect unique constraints, and does not touch work IDs or associations. `display_alias` remains only for older API compatibility and unresolved legacy conflicts; new saves store an empty value. Older clients explicitly sending a valid display alias receive the same primary-name promotion behavior.
- If two legacy entries would have the same primary name, preserve their existing visible names/IDs and defer that group (and dependent blocked promotions). Expose the former canonical name in aliases in pickers/directories; the shared editor explains the collision and saving offers an explicit merge. Choosing another unique name is also possible. Keep all data until a decision is made.
- Deployment takes a SQLite backup before migration. Old fixed share snapshots remain fixed; new snapshots use the new primary names. Historical metadata-merge undo may be refused by the existing stale-state guard when migration changed the target's names; do not bypass that guard. Work-edit history continues to use stable IDs.

Verification: `test_primary_names.py` covers every metadata kind, old-client compatibility, importer and attribute lookup, collision review, merge/undo, cyclic name exchanges, blocked migration groups, Trash and idempotency. `test_tag_flow.mjs` verifies English/Japanese draft swapping, repeated selection, save/cancel and all metadata editors; HTTP checks confirm persisted names and import/attribute reuse. Browser checks use a disposable library.


### Existing-library rollout (2026-10-15)

The owner explicitly approved merging the two conflicting author pairs into their Japanese primary names. The rollout takes a complete SQLite backup, promotes the other existing display choices, then performs both merges through the regular history/redirect implementation. It verifies every work/source/score record is unchanged and compares the complete association set after replacing only the two merged author IDs. These are collection-specific maintenance decisions, not automatic name-based merge rules shipped to other libraries.

## Work-editor metadata merge repair — 2026-10-16

- Imported work drafts can contain a metadata name without `kind` or a persisted entity ID. The shared editor previously knew the field kind only in its form data, while its merge picker queried `kind=undefined` from the original item. Reproduced an empty author target list; pass the work field's kind into all picker and editor paths.
- Saved metadata retains the existing preview/signature-confirmed shared merge, aliases/associations, redirects and History recovery. Same-name/different-attribute tags remain eligible targets; different metadata kinds are excluded.
- Unsaved imported metadata offers **Use existing metadata**, selecting the existing item for the work draft without a shared merge or alias/name changes. The message states that scope. Saving a new metadata name uses POST /entities instead of PUT /entities/undefined. Cancelling selection creates nothing.
- Disable the target selector and next button while loading or when no matches exist, show an empty-result explanation, and ignore late/closed/out-of-order search results. Candidate queries still support names and aliases; refine the query to find items beyond the first300 results.
- After selecting/merging a non-tag field from work editing, deduplicate the target ID within that field. Preserve other unsaved work fields and ignore responses after switching to another draft. Merely opening the picker never performs a merge.


Rollout checks passed: 69 Python tests plus English/Japanese UI checks; the private HTTPS API and public shared-server health both returned 200. In the existing library, 6,109 metadata entries became 6,107 solely from the two approved author merges. All 4,869 work records, source links and scores remained unchanged. All 74,725 associations matched the expected ID substitutions, foreign keys and SQLite integrity passed, and no legacy display overrides remained. The pre-change database backup is retained on the VPS outside the web-served files.
