// Execute the actual shared gallery/detail renderer with fictional covers.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {isStoreCover} from './static/store-sources.js';
import {isPawchiveCover} from './static/pawchive-sources.js';
const app=readFileSync(new URL('static/app.js',import.meta.url),'utf8');
const context={isStoreCover,isPawchiveCover,esc:s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;'),t:s=>s,placeholder:()=>'<span>Empty</span>'};
vm.createContext(context);
vm.runInContext(app.slice(app.indexOf('const relayCover='),app.indexOf('\nconst field=')),context);
vm.runInContext(app.slice(app.indexOf('function image('),app.indexOf('\nfunction images(')),context);
const cover=hash=>'https://tn.hitomi.la/webpbigtn/3/12/'+hash+'.webp';
const work={id:'fixture',title:'Cover fixture',cover:cover('a'.repeat(64))};
const src=w=>context.image(w).match(/src="([^"]+)"/)[1];
const old=src(work),changed=src({...work,cover:cover('b'.repeat(64))});
assert.notEqual(old,changed,'Saving another cover must change browser image identity');
assert.equal(src({...work,title:'Renamed'}),old,'Unrelated edits retain image identity');
assert.equal(new URL(old,'http://localhost').searchParams.get('v'),work.cover);
assert.equal(new URL(changed,'http://localhost').pathname,'/api/works/fixture/cover');
assert.equal(src({...work,cover:'https://example.org/new.png'}),'https://example.org/new.png');
assert.equal(src({...work,id:null}),work.cover,'Unsaved covers use the direct preview target');
assert.equal(new URL(src({...work,cover:'https://t.nhentai.net/galleries/9/cover.jpg'}),'http://localhost').pathname,'/api/works/fixture/cover');
assert.ok(!context.image({...work,cover:''}).includes('<img'));
assert.equal(new URL(src({...work,cover:'https://img.dlsite.jp/modpub/images2/work/books/BJ01310000/BJ01309208_img_main.jpg'}),'http://localhost').pathname,'/api/works/fixture/cover');
console.log('Cover renderer identity checks passed');

assert.equal(new URL(src({...work,cover:'https://file.pawchive.pw/data/aa/aa/'+ 'a'.repeat(64)+'.jpg'}),'http://localhost').pathname,'/api/works/fixture/cover');
