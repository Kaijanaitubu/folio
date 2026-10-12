# Future importer and duplicate policy — discussion, 2026-10-11

## 2026-10-12 update: live official API v2 and revised user policy

This update supersedes the earlier access and gender recommendations below. Old title/duplicate policy notes are historical; F-002/F-003/F-013 are already implemented.

Direct HTTPS requests from this PC, with a descriptive `User-Agent` and no cookies/API key, successfully fetched the site's [API docs](https://nhentai.net/api/v2/docs), [OpenAPI schema](https://nhentai.net/api/v2/openapi.json) and `GET /api/v2/galleries/{gallery_id}` for two gallery IDs. These were actual gallery JSON objects, not error envelopes. Repeat reads succeeded. The old `/api/gallery/1` and `/info/` had returned 403. No CAPTCHA was solved, session credentials extracted, artwork downloaded, or library works saved during this research.

Observed fields: gallery ID, media ID, English/Japanese/pretty titles, cover/thumbnail relative paths and dimensions, typed tags (`artist`, `group`, `parody`, `character`, `tag`, `category`, `language`), page count, ordered pages with image/thumbnail paths and dimensions. Tags have ID/type/name/slug/URL/count and no gender field. Both sampled page arrays matched the reported count. Relative paths are not yet verified fetchable image URLs; CDN host selection, allowed relay hosts and image formats/referrers still need a separate check before claiming working covers.

The gallery operation's official description states public access with optional user token/API key, anonymous 20 requests/minute/IP and authenticated 45/minute/IP. The schema also declares authorization mechanisms; successful anonymous responses and the public-access description are the basis for the current unauthenticated plan. Authenticated usage supports `Authorization: Key ...`; a key is not needed for the verified metadata lookup and is not requested or stored. Other endpoints may require it. Do not assume unlimited access or automatic CAPTCHA-solving. Proposed batch behavior: sequential requests paced below the anonymous limit, bounded retries respecting 429/Retry-After, persisted progress, per-item missing/invalid-data errors. The importer remains unimplemented.

User's revised tag policy: neutral by default; single imports remain editable; each batch chooses neutral or automatically the most-used existing attribute for the same tag. An individual-import default preference for frequency is optional. This supersedes the earlier proposal requiring confirmation of each mapping. Proposed details, not yet approved: resolve canonical names/aliases, count distinct active work associations, freeze frequencies before the batch so its own new works do not change decisions, neutral on ties/no match/alias ambiguity. Public-edition user-created attributes remain a future design topic, not a current schema change.

Cross-site matching is now F-014 in ROADMAP.md. Proposal: title/author candidates using aliases and retained original source titles, with page count/language/series as supporting evidence. Tag overlap alone cannot prove identical works. Confirm the intended existing work before adding only a secondary URL; preserve primary URL, title, cover, metadata and personal data. Distinct editions/chapters/pages need separate treatment. Batch candidates can be held for review rather than automatically attached. This is a proposal, not an implemented matching rule.

This is research and a recommendation, not an implemented importer or a change to current title uniqueness.

Update, 2026-10-12: the user's later duplicate-policy decisions are tracked in [ROADMAP.md](ROADMAP.md) and take precedence over the older suggestions below. Matching titles may be registered separately; an already registered identical URL is skipped without a separate-entry override; another page of the same Hitomi work warns but remains registerable. Bookmark imports should offer source-title/bookmark-name selection and retain the original bookmark name internally. Detailed implementation choices and permission to start implementation are still pending.

## Access observations

Direct requests from this PC to https://nhentai.net/ and https://nhentai.net/api/gallery/1 returned HTTP 403 with Cloudflare as the server. The home response was a verification page. No verification challenge was solved and no image bodies were downloaded. The web reader could not open the site's pages either. Therefore the current live metadata schema, displayed-title priority, image-host routing, and automated access cannot yet be guaranteed.

The [public client implementation](https://github.com/Zekfad/nhentai-api/blob/master/src/api.js) builds a gallery-metadata endpoint `/api/gallery/{id}` separately from cover/page paths. Its [gallery model](https://github.com/Zekfad/nhentai-api/blob/master/src/book.js) describes gallery ID, a distinct media ID, English/Japanese/short title variants, page count, upload time, image information, and typed tags. Its [tag model](https://github.com/Zekfad/nhentai-api/blob/master/src/tag.js) describes ID, type, name, URL, and site-wide usage count, with no gender field. These are source-code observations from an unofficial client, not proof of today's live responses or a supported public API contract. Do not equate the repository name `nhentai-dev` with site ownership; the older [API wrapper](https://github.com/nhentai-dev/API) explicitly describes itself as unofficial and deprecated.

## Proposed mapping

| Source type | Folio field |
|---|---|
| artist | Author |
| group | Circle / group |
| parody | Series |
| character | Characters |
| tag | Tag, with the gender policy below |
| category | Recognized Folio category; warn/preserve context for unknown values |
| language | Language; treat labels such as translated as qualifiers rather than spoken languages |

Keep source tag IDs for stable adapter mapping and source gallery IDs for import identity. Neither replaces the user's library IDs. Preserve the saved source URL. Titles should follow the site's actual display choice, once verified, with a documented fallback among available variants. A short/pretty title may omit edition or chapter context and should not be used blindly for uniqueness.

Cover handling needs its own live host/format/referrer check. The existing relay allows Hitomi hosts only; it must not simply accept every nhentai URL or become a general proxy. The approved RAM-only storage policy can apply to a future separate, narrowly scoped adapter.

## Gender recommendation

The proposed frequency rule is useful as a suggestion. It is unreliable as a silent factual assignment: a library's popular female variant does not establish the gender represented in a newly imported work, and mistakes would reinforce themselves as imports grow.

Use this order:

1. An owner-confirmed mapping from nhentai tag ID to a Folio tag ID takes priority. This remains stable even if usage counts change or names gain preferred display aliases.
2. Find same-name canonical tags and registered aliases across genders. If one eligible entity exists, suggest reusing it; ambiguous aliases need review.
3. When several gender variants exist, suggest the variant used by the most distinct works in the owner's library. Count work associations, not entity rows, and not nhentai's site-wide `count`. Show the choice and allow correction before remembering it. Do not recompute confirmed mappings on every import.
4. For ties, no matches, or uncertain meanings, use neutral/unspecified under the current model or mark the item for review. Do not introduce another gender state without agreement. Unknown neutral mappings should remain editable and should not be treated as a confirmed inference automatically.

For a large bookmark job, review unique tag mappings once before the job starts, rather than opening a dialog for every work. Neutral technical tags can be mapped explicitly; gender-associated names can receive a frequency-based suggestion. Retain a distinction in import provenance between source information, suggestions, and confirmed mappings. Missing upstream gender itself stays missing; the mapping is a library organization choice.

## Duplicate and bookmark-title recommendation

Allow identical titles as ordinary library entries and use titles only for a warning. A title-plus-primary-URL pair still lets the same URL be imported twice merely by renaming a title; checking only the primary URL also misses a URL already stored as a secondary source.

For bookmark jobs, default to skipping a source URL already in any saved source link or already selected in the same job. Optionally recognize equivalent URL shapes using a source adapter's identity. Preserve saved URLs and meaningful reader/chapter/page fragments: collapsing every link to a gallery ID would erase intentional magazine-chapter bookmarks. Offer an explicit “separate entry” choice for such conflicts instead of silently merging.

Add a per-job title choice: **Source title** or **Bookmark name**. Preview the resulting titles; fall back to source title when a bookmark label is empty. Keep both original values as import provenance so changing the chosen title does not lose context. Bookmark naming preserves chapter descriptions while duplicate-title allowance also handles different works with identical source titles. For entries without a source, allow matching titles with a warning.

This requires a separate schema migration removing the existing owner/title unique constraint, updated manual-save and interactive-import checks, updated durable-job status/report behavior, and revised tests. Existing entries should remain separate, with no automatic merging or renaming. The current release retains the old checks until the user authorizes this change.
