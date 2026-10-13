"""Reader-cover sizing, tone antialiasing, and safe relay fallback."""
from io import BytesIO
import unittest
from unittest.mock import patch
import cover_resize
import cover_relay

try:
    from PIL import Image, ImageStat
except ImportError:
    Image = None

@unittest.skipIf(Image is None, 'Optional Pillow is unavailable')
class ResizeTests(unittest.TestCase):
    def encoded(self, image):
        with BytesIO() as stream:
            image.save(stream, 'PNG')
            return stream.getvalue()

    def test_portrait_landscape_and_tall_page_keep_aspect_without_crop(self):
        for size, expected in [((2028,2880),(450,639)), ((1600,900),(450,253)), ((1000,4000),(160,640))]:
            with self.subTest(size=size), Image.new('RGB', size, 'white') as source:
                mime, result = cover_resize.thumbnail('image/png', self.encoded(source))
                self.assertEqual(mime, 'image/webp')
                with Image.open(BytesIO(result)) as output:
                    self.assertEqual(output.size, expected)

    def test_dense_checker_tone_is_averaged_instead_of_aliased(self):
        size = 1800
        pixels = bytes([0,255] * (size // 2) + [255,0] * (size // 2)) * (size // 2)
        with Image.frombytes('L', (size,size), pixels) as source:
            _, result = cover_resize.thumbnail('image/png', self.encoded(source))
        with Image.open(BytesIO(result)) as output:
            self.assertEqual(output.size, (450,450))
            stats = ImageStat.Stat(output.convert('L'))
            self.assertLess(stats.stddev[0], 2)
            self.assertGreater(stats.mean[0], 120)
            self.assertLess(stats.mean[0], 136)

    def test_small_image_is_not_upscaled_and_invalid_data_is_rejected(self):
        with Image.new('RGB',(212,300),'white') as source:
            data = self.encoded(source)
            self.assertEqual(cover_resize.thumbnail('image/png',data), ('image/png',data))
        with self.assertRaises(OSError): cover_resize.thumbnail('image/webp', b'invalid')
        with Image.new('RGB',(100,100),'white') as source, patch('cover_resize.MAX_PIXELS',9999):
            with self.assertRaises(ValueError): cover_resize.thumbnail('image/png',self.encoded(source))

    def test_relay_caches_resized_cover_and_falls_back_on_resize_failure(self):
        hash_value = '0' * 61 + '123'
        small = 'https://atn.gold-usergeneratedcontent.net/webpsmalltn/3/12/' + hash_value + '.webp'
        with Image.new('RGB',(1200,1800),'white') as source:
            high = self.encoded(source)
        with patch('cover_relay.CACHE',cover_relay.MemoryCache()), patch('cover_relay.importer.thumbnail_routes',return_value=(0,set(),0)), patch('cover_relay.reader_image_url',return_value='reader'), patch('cover_relay.fetch_image',return_value=('image/png',high)) as fetch:
            mime, result = cover_relay.load(small)
            self.assertEqual(cover_relay.load(small), (mime,result))
            with Image.open(BytesIO(result)) as output: self.assertEqual(output.size,(427,640))
            fetch.assert_called_once_with('reader')
            self.assertLess(len(result),len(high))
        with patch('cover_relay.CACHE',cover_relay.MemoryCache()), patch('cover_relay.importer.thumbnail_routes',return_value=(0,set(),0)), patch('cover_relay.reader_image_url',return_value='reader'), patch('cover_relay.cover_resize.thumbnail',side_effect=ImportError('Pillow unavailable')), patch('cover_relay.fetch_image',return_value=('image/webp',b'fallback')) as fetch:
            self.assertEqual(cover_relay.load(small), ('image/webp',b'fallback'))
            self.assertEqual([c.args[0] for c in fetch.call_args_list],['reader',small])

if __name__ == '__main__': unittest.main()
