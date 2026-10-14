"""Additional fixed image sources sharing the existing volatile relay cache."""
import cover_relay
import momonga
import stores
import pawchive

def load(url):
    if pawchive.valid_image(url):
        def fetch():
            try:return pawchive.fetch_image(url)
            except ValueError as e:raise cover_relay.RelayError(str(e)) from e
        return cover_relay.CACHE.get(url,fetch)
    if stores.valid_image(url):
        def fetch():
            try:return stores.fetch_image(url)
            except (ValueError,OSError) as e:raise cover_relay.RelayError(str(e)) from e
        return cover_relay.CACHE.get(url,fetch)
    if not momonga.valid_image(url): return cover_relay.load(url)
    def fetch():
        try: return momonga.fetch_image(url)
        except ValueError as e: raise cover_relay.RelayError(str(e)) from e
    return cover_relay.CACHE.get(url,fetch)
