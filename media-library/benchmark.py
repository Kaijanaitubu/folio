"""Benchmark isolated realistic collections; never writes to the user's library."""
import argparse
import json
import platform
import tempfile
import time
from pathlib import Path
import db

def run(count):
    (db.ROOT/'test-output').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=db.ROOT/'test-output') as temp:
        db.PATH=Path(temp)/'benchmark.sqlite3';db.init()
        with db.transaction() as c:
            for n in range(1,4):db.save_dimension(c,{'name':'Dimension '+str(n),'maximum':5,'symbol':'Star','gallery':True})
            dims=db.dimensions(c)
            entities=[]
            for kind,number in [('author',120),('circle',50),('tag',250),('series',40),('character',100)]:
                for i in range(number):entities.append((kind,db.save_entity(c,{'kind':kind,'name':f'{kind} {i}','aliases':[f'alias {kind} {i}'],'gender':'female' if kind=='tag' and i%2 else 'neutral'})))
            bykind={k:[e for kind,e in entities if kind==k] for k in ['author','circle','tag','series','character']}
            stamp=db.now()
            c.executemany('INSERT INTO works(id,owner,title,category,language,pages,review,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',((f'w{i:06}','local',f'Title {i:06}','doujinshi' if i%2 else 'manga','Japanese',20+i%120,'Review '+str(i),stamp,stamp) for i in range(count)))
            assoc=[];scores=[];links=[]
            for i in range(count):
                wid=f'w{i:06}'
                for k in bykind:
                    assoc.append((wid,bykind[k][i%len(bykind[k])]))
                    if k=='tag':
                        for j in (13,29,47):assoc.append((wid,bykind[k][(i+j)%len(bykind[k])]))
                if i%5:
                    scores.extend((wid,d['id'],1+i%5) for d in dims)
                links.append((db.uid(),wid,f'https://example.org/work/{i}','Source',0,1))
            c.executemany('INSERT INTO work_entities VALUES(?,?)',assoc);c.executemany('INSERT INTO scores VALUES(?,?,?)',scores);c.executemany('INSERT INTO links VALUES(?,?,?,?,?,?)',links)
            c.execute('ANALYZE')
        results={}
        for label,q,kwargs in [('first page','',{}),('title substring','title:000',{}),('entity AND rating','tag:"tag 1" rating1:>=4',{}),('OR before AND','author:"author 1"/author:"author 2" pages:>=50',{}),('free word','tag',{}),('random pick','',{'random_one':True}),('random sort','',{'sort':'random','seed':'123'})]:
            start=time.perf_counter()
            with db.transaction() as c: result=db.list_works(c,q,**kwargs)
            results[label]={'seconds':round(time.perf_counter()-start,3),'matches':result['total']}
        return {'entries':count,'platform':platform.platform(),'python':platform.python_version(),'results':results}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--count',type=int,default=30000);args=parser.parse_args();print(json.dumps(run(args.count),indent=2))
