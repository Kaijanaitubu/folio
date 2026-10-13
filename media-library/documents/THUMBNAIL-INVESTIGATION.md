# Hitomi titles and remote covers — 2026-10-11

**Implemented follow-up:** The user approved a memory-only relay after this investigation. Supported saved Hitomi covers now pass through Folio with the source referrer, using a 32 MiB RAM cache (five-minute TTL), a 2 MiB per-image limit, four concurrent requests, and browser `no-store` headers. Live verification returned a 28,900-byte WebP image with HTTP 200, with no new files created during the requests. No imported image bytes are written to files, database, backups, or logs. The direct-embedding observations below remain the historical reason for this change; the old “no relay” result is superseded. Details: `README.md`, Memory-only covers.

The importer now uses the title shown by the source page and generates thumbnail URLs using the source's current CDN routing. Direct image embedding still fails in the tested environment because the CDN checks the request's referrer.

## Source behavior

The public [gallery page code](https://ltn.gold-usergeneratedcontent.net/gallery.js) displays `japanese_title` when present, falling back to `title`. The old importer chose the other field first, which could produce a romanized title. The revised adapter follows the page's priority without translating the title. Existing saved titles can be refreshed through Edit → Import metadata → select Title in the replacement dialog → Save.

For its cover, the page takes the first file's hash and creates an AVIF picture with a WebP fallback. The [shared URL code](https://ltn.gold-usergeneratedcontent.net/common.js) constructs a hash-based path and selects `atn` or `btn` on `gold-usergeneratedcontent.net`. The selection comes from the current [routing table](https://ltn.gold-usergeneratedcontent.net/gg.js). The adapter parses that restricted integer table without executing source JavaScript, caches it for one hour, and saves a WebP thumbnail URL. Legacy URLs can be resolved for display without rewriting saved data.

The old `tn.hitomi.la` hostname did not resolve during this investigation. A generic `tn.gold-usergeneratedcontent.net` URL happened to work with the source referrer for the tested hash, so sharding alone is not the decisive display fix.

## Header experiment

Public gallery ID 1036181 was used. Requests used the same thumbnail hash; GET response headers were inspected, then the connection was closed without reading or saving the image body.

| Request | Referrer | Result |
|---|---|---|
| Generic thumbnail HEAD | None | 404 |
| Routed WebP HEAD | None | 404 |
| Routed WebP GET | None | 404 |
| Routed WebP GET | `http://localhost:8765/` | 404 |
| Routed WebP GET | `https://hitomi.la/` | 200, `image/webp` |
| Generic WebP GET | `https://hitomi.la/` | 200, `image/webp` |
| Routed AVIF GET | `https://hitomi.la/` | 200, `image/avif` |

Inference: the CDN applies referrer-based hotlink protection. A 404 here does not establish that the image is missing. The source referrer changes the result to 200.

An image's [referrer policy](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/referrerPolicy) controls how much of the embedding page's referrer is sent. It does not let an ordinary web app choose an unrelated site's URL as its referrer. Changing the policy to send the local app's origin therefore does not solve this observed restriction.

## Result in Folio

Folio keeps cover URLs and attempts direct browser display. Failed known Hitomi URLs get one routing refresh; if still blocked, the cover shows “Cover unavailable / View on the source site.” Opening the work's source link remains available. The server fetches metadata and routing text only, and has no image proxy or image cache.

For reliable covers under a URL-only design, use a thumbnail URL from a host that permits external embedding, or view Hitomi's images on its own page. A server image relay would require the server to receive and forward image bytes even without writing them to disk. That is a different design choice from the current metadata-only server and has not been implemented.

These observations cover one public hash and the source scripts as served on this date. CDN rules and routing can change; they are not a guarantee for every gallery, region, or browser.
