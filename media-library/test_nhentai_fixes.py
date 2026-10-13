"""Negotiated CDN formats and credit-prefixed matching, without remote requests."""
import io
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import db
import import_matching as matching
import nhentai
import cover_relay as relay

WEBP=b'RIFF\x18\x00\x00\x00WEBPfixture'

class ImageTests(unittest.TestCase):
    def fetch(self,url,mime='image/webp',body=WEBP):
        response=Mock(status=200)
        response.getheader.side_effect=lambda name:{'Content-Type':mime,'Content-Length':str(len(body))}.get(name)
        response.read1.side_effect=io.BytesIO(body).read1
        connection=Mock();connection.getresponse.return_value=response
        address=(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))
        with patch('cover_relay.socket.getaddrinfo',return_value=[address]),patch('cover_relay.socket.socket'),patch('cover_relay.ssl.create_default_context'),patch('cover_relay.http.client.HTTPSConnection',return_value=connection):
            result=relay.fetch_image(url)
            headers=connection.request.call_args.kwargs['headers']
            self.assertEqual(headers['Referer'],'https://nhentai.net/')
            self.assertNotIn('Authorization',headers)
            return result

    def test_negotiated_cover_and_interior_formats(self):
        for path in ('cover.jpg','cover.png','20t.jpg','2t.png'):
            with self.subTest(path=path):
                self.assertEqual(self.fetch('https://t.nhentai.net/galleries/99/'+path),('image/webp',WEBP))
        self.assertEqual(self.fetch('https://t4.nhentai.net/galleries/99/20t.jpg')[0],'image/webp')

    def test_mime_signature_and_restricted_paths_still_checked(self):
        for mime,body in [('text/html',WEBP),('image/jpeg',WEBP),('image/webp',b'not an image')]:
            with self.subTest(mime=mime),self.assertRaises(relay.RelayError):
                self.fetch('https://t.nhentai.net/galleries/99/cover.jpg',mime,body)
        for url in ('https://t4.nhentai.net/galleries/99/20t.jpg?next=localhost','https://t5.nhentai.net/galleries/99/20t.jpg','https://t4.nhentai.net/../private','https://i4.nhentai.net/galleries/99/20.jpg'):
            self.assertFalse(nhentai.valid_image(url))
            with patch('cover_relay.socket.getaddrinfo') as dns,self.assertRaises(relay.RelayError):relay.fetch_image(url)
            dns.assert_not_called()

    def test_additional_image_suffixes_and_metadata_fallback(self):
        self.assertTrue(nhentai.valid_image(nhentai.image_url('galleries/99/cover.webp.webp')))
        self.assertEqual(self.fetch('https://t.nhentai.net/galleries/99/cover.webp.webp')[0],'image/webp')
        self.assertEqual(self.fetch('https://t.nhentai.net/galleries/99/cover.jpeg')[0],'image/webp')
        self.assertEqual(self.fetch('https://t.nhentai.net/galleries/99/cover.gif','image/gif',b'GIF89afixture')[0],'image/gif')
        gallery={'title':{'japanese':'Fixture'},'num_pages':20,'cover':{},'thumbnail':{'path':'https://t4.nhentai.net/galleries/99/thumb.jpeg'},'pages':[{'number':20,'path':'galleries/99/20.png'}]}
        self.assertEqual(nhentai.parse_gallery(gallery)['cover'],'https://t4.nhentai.net/galleries/99/thumb.jpeg')
        self.assertEqual(nhentai.parse_gallery(gallery,20)['cover'],'https://t.nhentai.net/galleries/99/20t.png')
        gallery['pages'][0]['path']='https://evil.example/20.jpg'
        data=nhentai.parse_gallery(gallery,20)
        self.assertEqual(data['cover'],'');self.assertTrue(data['warnings'])
        self.assertEqual(data['cover_diagnostics']['paths'],['',''])

class TitleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=db.PATH;db.PATH=Path(self.temp.name)/'library.sqlite3';db.init()
    def tearDown(self):db.PATH=self.old;self.temp.cleanup()
    def save(self,title,author='Alice',url='https://hitomi.la/reader/100.html'):
        with db.transaction() as c:return db.save_work(c,{'title':title,'author':[author],'links':[{'url':url}]})

    def test_credit_blocks_preserve_original_and_semantic_qualifiers(self):
        for title in ('[Alice] My Story','[Circle (Alice)] [Other credit] My Story','[Digital Lover (Alice)] My Story','［サークル（作者）］Ｍｙ　Ｓｔｏｒｙ'):
            self.assertEqual(matching.title_key(title),'my story')
        for title in ('[Chapter 2] Story','[Ch2] Story','[Vol. 3] Story','[Japanese] Story','[第2話] Story','[Uncensored] Story','[1] Story','[Alice]'):
            self.assertEqual(matching.title_key(title),matching.key(title))
        self.assertEqual(matching.title_key('[Alice] [Chapter 2] Story'),'[chapter 2] story')
        self.assertNotEqual(matching.title_key('[Alice] Story 1'),matching.title_key('[Alice] Story 2'))

    def test_existing_and_new_titles_match_both_directions(self):
        a=self.save('[Circle (Alice)] My Story')
        b=self.save('My Story',url='https://hitomi.la/reader/101.html')
        with db.transaction() as c:
            for title in ('My Story','[Alice] MY STORY'):
                self.assertEqual({r['id'] for r in db.title_matches(c,title)},{a['id'],b['id']})
            self.assertEqual(db.get_work(c,a['id'])['title'],'[Circle (Alice)] My Story')
            incoming={'title':'[Alice] My Story','author':[{'name':'Alice'}]}
            self.assertEqual({r['id'] for r in matching.candidates(c,incoming,'https://nhentai.net/g/100/')},{a['id'],b['id']})
            self.assertEqual(db.title_matches(c,'My Story',a['id'])[0]['id'],b['id'])

    def test_author_conflict_same_provider_and_linkless_warn_without_auto_candidate(self):
        a=self.save('My Story','Bob',url='https://nhentai.net/g/200/')
        with db.transaction() as c:
            b=db.save_work(c,{'title':'My Story','author':['Bob']})
            data={'title':'[Alice] My Story','author':[{'name':'Alice'}]}
            self.assertEqual(matching.candidates(c,data,'https://nhentai.net/g/201/'),[])
            self.assertEqual({r['id'] for r in db.title_matches(c,data['title'])},{a['id'],b['id']})
            evidence=matching.candidate_evidence(c,db.get_work(c,a['id']),data)
            self.assertTrue(evidence['author_conflict']);self.assertFalse(evidence['author'])
            attached=matching.attach(c,a['id'],'https://nhentai.net/g/201/',[data['title']])
            self.assertEqual(attached['title'],'My Story');self.assertEqual(attached['author'][0]['name'],'Bob')
            self.assertEqual(attached['links'][-1]['is_primary'],0)

    def test_version_six_reindexes_existing_original_variants_idempotently(self):
        a=self.save('[Circle] My Story')
        with db.transaction() as c:
            c.execute('DELETE FROM migrations WHERE version=6')
            c.execute('UPDATE work_titles SET title_key=? WHERE work_id=?',(matching.key(a['title']),a['id']))
        db.init();db.init()
        with db.transaction() as c:
            self.assertEqual([r['id'] for r in db.title_matches(c,'My Story')],[a['id']])
            self.assertEqual(c.execute('SELECT count(*) FROM migrations WHERE version=6').fetchone()[0],1)
            self.assertEqual(db.get_work(c,a['id'])['source_titles'],[a['title']])

if __name__=='__main__':unittest.main()
