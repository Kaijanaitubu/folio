# Tag editing and identity — implemented 2026-10-13

This supplements section 5 of the requirements and the nhentai tag policy. It changes personal-library tag behavior; arbitrary user-defined attributes for the public release remain deferred.

## No attribute

- `neutral` remains the compatible internal value for no attribute. Input `none` is also accepted. No additional unspecified/genderless identity is introduced.
- Attribute selectors show **None** / **未指定（none）**, Female and Male. Normal chips, directory rows, pickers and warning labels omit the no-attribute suffix/badge.
- Directory navigation uses `none:"canonical name"` for no-attribute-only results. Existing `neutral:` searches and saved searches remain valid. `tag:` still includes every attribute.

## Work-scoped editing

- Clicking a tag chip in a work editor opens **Tag on this work**, with an attribute selector and **Edit shared tag** button.
- Changing the attribute selects the same canonical name with that attribute when it exists. If several normalized canonical names exist, exact spelling takes precedence; otherwise ask which existing tag to use.
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
- Transfer all associations, including Trash, deduplicate, and union source aliases plus source names. Do not add the target's canonical name as a redundant new alias. Preserve the target's name, attribute, display alias and sort reading.
- Store old-ID redirects. Existing drafts, frozen importer IDs, old work history and Trash snapshots can resolve them. Chained merges flatten redirects. These are ID redirects, never permanent name-to-attribute rules.
- Record the merge in operation history for 30 days. Undo restores source/target aliases, original association sets and preceding redirects atomically. Refuse undo if the target metadata, target association set or relevant redirects changed afterward. Unrelated work fields may change without being overwritten.
- Shared directory rename/delete remains outside operation undo. Merge recovery is available through History; restore a pre-update SQLite backup if reverting to an older application version without this schema.

## Persistence and verification

Migration 7 adds redirects and normalized lookup indexes without changing existing names, attributes or associations. API conflicts return 409 and structured choices; mutation endpoints retain the existing request token/origin guards. No media or credential storage changes are involved.

`test_tags.py`, the tag HTTP cases and `test_tag_flow.mjs` cover work scope, deduplication, deferred creation, normalized collisions, collision acknowledgments, ambiguous-job review, cross-attribute merge, Trash/history/frozen-ID compatibility, chained merge undo, stale guards and English/Japanese UI. Browser verification uses a disposable library, not the personal collection.
