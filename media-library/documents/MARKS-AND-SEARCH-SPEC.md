# Five work marks and Search help

Approved and implemented 2026-10-13. This replaces the Purchased checkbox in the personal version; the independent library selection checkboxes are unchanged.

## Fixed definitions and storage

Five independent Boolean slots are shared across all works: **1 ○/●, 2 △/▲, 3 □/■, 4 ♡/♥, 5 ☆/★**. Symbols and numbers cannot be reordered, added or deleted. Settings lets the library owner give each slot a label, up to 80 characters. Blank labels use localized defaults: Purchased for slot 1 and Mark N for 2–5. A custom label is the same string in both interface languages.

Migration 8 adds `works.mark_bits` (integer 0–31) and owner-scoped `mark_labels`. Each bit corresponds to number minus one. All existing Purchased values, including Trash entries, become mark 1; marks 2–5 start off. The legacy `bought` column remains synchronized with bit 1 through database triggers, including legacy clients, raw cleanup-tool writes and old history undo. Labels do not change numbers or saved query meaning.

Work JSON includes `marks: [1,4]` in ascending order. Existing JSON fields remain available. New saves treat `marks` as authoritative; legacy payloads containing `bought` change only mark 1, preserving the other four. Omitting both preserves the existing marks. Invalid numbers, strings or Boolean values in a marks array are rejected.

## Display and editing

- Library: active symbols only, small and at the bottom right of the full card. No mark toggles on cards.
- Detail: a subdued summary beside/beneath the title, expandable to reveal five labeled toggles. A click saves immediately through `POST /api/works/{id}/marks`. The request supplies number, explicit Boolean value and the expected current marks. Only marks and update time change; reviews, ratings, sources and metadata are preserved. Repeated requests for the current state are no-ops. Conflicting snapshots require a refresh. Pending controls are disabled; a late response cannot replace a different page.
- Edit: five toggles update the draft. Save commits them with the other fields; Cancel discards them.
- Settings: five shared labels, saved together through `PUT /api/mark-labels`. The expected previous labels prevent stale overwrites.
- Batch: unchanged / add / remove / replace / clear. Preview shows changed and unchanged work counts and selected labels. Apply is atomic and requires the previewed records to remain unchanged.
- Existing 30-day edit/batch history supports marks and guarded undo. The legacy Bought field is suppressed from new history when the same change is already represented by Marks. Label settings are outside work history.

## Search contract

| Query | Meaning |
|---|---|
| `mark:124` | 1, 2 and 4 all on; 3 and 5 unrestricted |
| `mark:=124` | Only 1, 2 and 4 on; 3 and 5 off |
| `mark:421`, `mark:1124` | Same as `mark:124`; order and repeats do not matter |
| `mark:1/mark:4` | 1 OR 4 on |
| `-mark:2` | 2 off |
| `mark:none` | All off |
| `mark:any` | At least one on |
| `mark1:yes`, `mark5:no` | Single-slot form; yes/no/true/false supported |
| `bought:yes`, `bought:no` | Legacy aliases for slot 1 |

`mark:11010` is invalid: digit lists are slot numbers, not a binary string. `mark:=none` and `mark:=` are invalid; use `mark:none`. `-mark:124` negates the combined all-on condition; it does not require all three off. To require all three off use `-mark:1 -mark:2 -mark:4`. Empty, unknown and out-of-range expressions show an error.

All mark conditions use the existing shared compiler for library results/counts, random selection and all-results batch selection. Existing NOT, slash OR, space AND, quoted values and OR-before-AND semantics stay intact. Example: `author:alice/author:bob mark:14` means `(Alice OR Bob) AND marks 1 and 4 on`.

## Search help dialog

The Library's operator/example line contains an English **Search help** or Japanese **検索ヘルプ** hyperlink. It opens a modal without navigation or changing search, sort, selection or scroll position. The dialog opens at the beginning, supports scrolling, an always-visible Close control, native Escape and keyboard focus containment, and adapts to a narrow phone screen.

Contents cover free-word versus field matching, AND/OR/NOT, precedence, quotes and escapes, title/review/author/circle/group/tag/female/male/none/neutral/series/character/category/language/pages, available numbered rating dimensions, all marks syntax, legacy Bought syntax and combined examples. Current rating names/numbers/scales and mark labels/symbols come from configuration. Rating examples use existing dimensions and valid scores; a library with no dimensions is told how to add them. Custom data is HTML escaped.

English and Japanese are supported. Physical mobile keyboard behavior should be confirmed on the user's phone; desktop viewport checks do not simulate an Android keyboard.
