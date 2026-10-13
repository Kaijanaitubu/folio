"""Additional fixed image sources sharing the existing volatile relay cache."""
import cover_relay
import momonga

def load(url):
    if not momonga.valid_image(url): return cover_relay.load(url)
    def fetch():
        try: return momonga.fetch_image(url)
        except ValueError as e: raise cover_relay.RelayError(str(e)) from e
    return cover_relay.CACHE.get(url,fetch)
