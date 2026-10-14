import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import dlsite_purchases as p
import importer,db,import_jobs,stores

def work(pid='RJ123456',kind='MNG',name=None):
    return {'workno':pid,'work_type':kind,'name':name if name is not None else {'ja_JP':'試験作品 & <確認>','en_US':'Translated'}}

def bundle(rows,expected=None,sales=None):
    return {'format':p.FORMAT,'count':{'user':len(rows) if expected is None else expected},
            'sales':sales if sales is not None else [{'workno':r['workno']} for r in rows], 'works':rows}

class ProtocolTests(unittest.TestCase):
    def test_all_ids_batched_sequentially_and_no_account_fields_retained(self):
        ids=['RJ'+str(100000+n) for n in range(205)]
        calls=[];progress=[]
        def request(method,path,body):
            calls.append((method,path,body))
            if path==p.COUNT:return {'user':205,'account':'private'}
            if path==p.SALES:return [{'workno':pid,'sales_date':'private','order_number':'private'} for pid in ids]
            return {'works':[dict(work(pid),cookie='private',name={'ja_JP':'Original','session':'private'}) for pid in body],'token':'private'}
        result=p.collect(request,progress=lambda done,total:progress.append((done,total)))
        self.assertEqual([len(c[2]) for c in calls if c[0]=='POST'],[100,100,5])
        self.assertEqual(progress,[(0,205),(100,205),(200,205),(205,205)])
        self.assertNotIn('private',json.dumps(result));self.assertTrue(p.normalize(result)['complete'])
        self.assertTrue(all(path in (p.COUNT,p.SALES,p.WORKS) for _,path,_ in calls))
    def test_cancel_auth_failure_and_empty_inventory(self):
        with self.assertRaisesRegex(p.InventoryError,'cancelled'):p.collect(lambda *args:self.fail('called'),cancelled=lambda:True)
        calls=[]
        def expired(method,path,body):
            calls.append(path)
            if path==p.COUNT:return {'user':1}
            raise PermissionError('Authentication expired')
        with self.assertRaises(PermissionError):p.collect(expired)
        self.assertEqual(calls,[p.COUNT,p.SALES])
        result=p.collect(lambda method,path,body:{'user':0} if path==p.COUNT else [])
        self.assertTrue(p.normalize(result)['complete'])
        with self.assertRaisesRegex(p.InventoryError,'No eligible'):p.bookmarks(p.normalize(result))
    def test_unexpected_and_duplicate_api_rows(self):
        for rows in ([work('RJ654321')],[work(),work()]):
            def request(method,path,body):
                return {'user':1} if path==p.COUNT else [{'workno':'RJ123456'}] if path==p.SALES else {'works':rows}
            with self.assertRaises(p.InventoryError):p.collect(request)

class ConversionTests(unittest.TestCase):
    def test_types_titles_and_html_use_existing_importer(self):
        rows=[work(),work('BJ123456'),work('RJ123457','ICG'),work('RJ123458','SOU'),work('RJ123459','RPG'),work('VJ123456')]
        result=p.normalize(bundle(rows))
        self.assertTrue(result['complete']);self.assertEqual(result['counts']['eligible'],3);self.assertEqual(result['counts']['excluded'],3)
        self.assertEqual([i['category'] for i in result['items']],['doujinshi','manga','artist cg'])
        self.assertTrue(all(i['label']=='試験作品 & <確認>' for i in result['items']))
        text=p.bookmarks(result);self.assertIn('&amp; &lt;確認&gt;',text)
        parsed=importer.bookmarks(text);self.assertEqual(len(parsed),3);self.assertTrue(all(i['supported'] for i in parsed))
        self.assertEqual(parsed[0]['label'],'試験作品 & <確認>');self.assertEqual(parsed[0]['folder'],'DLsite purchases')
        self.assertEqual(stores.label(parsed[0]['url']),'DLsite Play')
    def test_missing_and_unknown_data_blocks_export(self):
        cases=[bundle([work()],expected=2),bundle([],expected=1,sales=[{'workno':'RJ123456'}]),bundle([work(kind='FUTURE')]),bundle([work(name='')]),bundle([{'workno':'RJ123456','name':'Title'}])]
        for value in cases:
            result=p.normalize(value)
            with self.assertRaises(p.InventoryError):p.bookmarks(result)
        result=p.normalize(bundle([work(kind='FUTURE')]))
        self.assertEqual(result['review'][0]['reason'],'unknown_work_type')
        self.assertEqual(result['excluded'],[])
    def test_duplicates_id_validation_counts_and_format(self):
        result=p.normalize(bundle([work()],sales=[{'workno':'RJ123456'},{'workno':'RJ123456'}]))
        self.assertEqual(result['counts']['duplicate_sales_ids'],1);self.assertEqual(len(importer.bookmarks(p.bookmarks(result))),1)
        for bad in (None,{}, {'format':'other'},bundle([work('RJ123456/../login')]),bundle([work()],expected=True),bundle([work(),work()]),bundle([work('RJ654321')],sales=[{'workno':'RJ123456'}])):
            with self.assertRaises(p.InventoryError):p.normalize(bad)
    def test_title_bounds_and_export_limits(self):
        with self.assertRaises(p.InventoryError):p.normalize(bundle([work(name='x'*4097)]))
        with patch.object(p,'MAX_BYTES',100):
            with self.assertRaisesRegex(p.InventoryError,'12 MB'):p.bookmarks(p.normalize(bundle([work()])))
    def test_existing_product_is_still_a_duplicate_job_item(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(db,'PATH',Path(tmp)/'library.sqlite3'):
            db.init()
            with db.transaction() as c:
                w=db.save_work(c,{'title':'Existing','links':[{'url':'https://www.dlsite.com/maniax/work/=/product_id/RJ123456.html','is_primary':True}],'marks':[4]})
                text=p.bookmarks(p.normalize(bundle([work()])))
                job=import_jobs.create(c,{'items':importer.bookmarks(text)})
                self.assertEqual(c.execute('SELECT status FROM job_items WHERE job_id=?',(job['id'],)).fetchone()[0],'duplicate_url')
                self.assertEqual(db.get_work(c,w['id'])['marks'],[4])
    def test_cli_private_report_partial_and_no_overwrite(self):
        script=str(Path(__file__).with_name('convert_dlsite_purchases.py'))
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.json';out=Path(tmp)/'bookmarks.html';report=Path(tmp)/'report.json'
            source.write_text(json.dumps(bundle([work()]),ensure_ascii=False),encoding='utf-8')
            args=[sys.executable,script,'--input',str(source),'--output',str(out),'--report',str(report)]
            result=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);before=out.read_bytes()
            result=subprocess.run(args,capture_output=True,text=True);self.assertNotEqual(result.returncode,0);self.assertEqual(out.read_bytes(),before)
            source.write_text(json.dumps(bundle([work()],expected=2)),encoding='utf-8')
            partial=Path(tmp)/'partial.html';details=Path(tmp)/'partial.json'
            result=subprocess.run([sys.executable,script,'--input',str(source),'--output',str(partial),'--report',str(details)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse(partial.exists());self.assertIn('count_mismatch',json.loads(details.read_text(encoding='utf-8'))['warnings'])

if __name__=='__main__':unittest.main()
