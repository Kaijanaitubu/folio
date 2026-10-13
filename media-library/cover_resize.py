"""Resize reader covers in RAM; never write or retain original image files."""
from io import BytesIO

COVER_SIZE = (450, 640)
MAX_PIXELS = 16_000_000

def thumbnail(mime, data):
    # Optional dependency: callers fall back to source thumbnails if unavailable.
    from PIL import Image, ImageOps
    with Image.open(BytesIO(data), formats=('WEBP', 'JPEG', 'PNG', 'AVIF')) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError('Reader cover exceeds the decoded pixel limit')
        with ImageOps.exif_transpose(source) as oriented:
            if oriented.width <= COVER_SIZE[0] and oriented.height <= COVER_SIZE[1]:
                return mime, data
            with oriented.convert('RGBA' if 'A' in oriented.getbands() else 'RGB') as image:
                # Integer area reduction first, then Lanczos: prefilter dense
                # screen tones instead of letting the browser undersample them.
                image.thumbnail(COVER_SIZE, Image.Resampling.LANCZOS, reducing_gap=2.0)
                with BytesIO() as output:
                    image.save(output, format='WEBP', quality=90, method=6)
                    return 'image/webp', output.getvalue()
