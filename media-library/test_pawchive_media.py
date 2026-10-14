import unittest
import pawchive

class MediaTests(unittest.TestCase):
    def test_attachment_classification(self):
        cases=[([], 'unknown'),(['a.jpg'],'image'),(['a.mp4'],'video'),(['a.jpg','a.webm'],'mixed'),(['a.zip'],'uncertain'),(['a.mp4','a.zip'],'uncertain')]
        for paths,expected in cases:
            with self.subTest(paths=paths):
                self.assertEqual(pawchive.media_kind({'attachments':[{'path':p} for p in paths]}),expected)
    def test_video_rejected_without_download(self):
        data={'service':'fanbox','user':'1','id':'2','title':'Video','file':{'path':'/clip.mp4'}}
        with self.assertRaises(pawchive.VideoPostSkipped):
            pawchive.parse_post(data,{},'https://pawchive.pw/fanbox/user/1/post/2')
    def test_mixed_requires_review(self):
        data={'service':'fanbox','user':'1','id':'2','title':'Mixed','file':{'path':'/clip.mp4'},'attachments':[{'path':'/preview.jpg'}]}
        self.assertEqual(pawchive.parse_post(data,{},'https://pawchive.pw/fanbox/user/1/post/2')['media_kind'],'mixed')
