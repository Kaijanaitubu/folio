// Test actual source-flow functions without a browser, remote fetches, or DOM packages.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const load=async name=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('static/'+name,import.meta.url),'utf8')).toString('base64'));
const {bookmarklet}=await load('source-link.js');
const {isPixivSource}=await load('pixiv-sources.js');
const {isStoreSource,isDLsitePlaySeries}=await load('store-sources.js');
const {isPawchiveSource}=await load('pawchive-sources.js');
const {en,ja}=await load('i18n.js');
const {applyImported,metadataKinds,sameMetadataSet,hasImportedChanges}=await load('import-policy.js');
const target='http://192.168.0.140:8765';
const source='https://hitomi.la/reader/123.html?x=a&y=b#7-8';
const script=bookmarklet(target);
const location={hostname:'hitomi.la',href:source};
vm.runInNewContext(script.slice(11),{location,alert:()=>assert.fail('unexpected alert')});
assert.equal(new URLSearchParams(location.href.split('?')[1]).get('url'),source);
assert.ok(location.href.startsWith(target+'/#/source?url='));
for(const host of ['pawchive.pw','www.pawchive.pw','momon-ga.com','www.momon-ga.com','www.dlsite.com','play.dlsite.com','dlsharing.com','www.dmm.co.jp','book.dmm.com','book.dmm.co.jp']){
 const sourceURL='https://'+host+'/fanzine/mo123/';
 const momongaLocation={hostname:host,href:sourceURL};
 vm.runInNewContext(script.slice(11),{location:momongaLocation,alert:()=>assert.fail('unexpected momon-ga rejection')});
 assert.equal(new URLSearchParams(momongaLocation.href.split('?')[1]).get('url'),sourceURL);
}
assert.throws(()=>bookmarklet('javascript:alert(1)'));
assert.throws(()=>bookmarklet('http://user:pass@localhost/'));
let warned=false;
const other={hostname:'evil.test',href:'https://evil.test/'};
vm.runInNewContext(script.slice(11),{location:other,alert:()=>warned=true});
assert.ok(warned);assert.equal(other.href,'https://evil.test/');
for(const value of ['https://play.dlsite.com/work/RJ01654100','https://play.dlsite.com/work/BJ151862/?utm=x','https://www.dlsite.com/maniax-touch/work/=/product_id/RJ364167.html/?utm_source=dlsite_play','https://www.dmm.co.jp/dc/doujin/-/detail/=/cid=d_123/?utm=x','https://book.dmm.co.jp/product/123/book123/?utm=x'])assert.ok(isStoreSource(value),value);
for(const value of ['https://play.dlsite.com/series/TITLE00053978','https://play.dlsite.com/work/VJ123456','https://www.play.dlsite.com/work/RJ123456','https://play.dlsite.com.evil/work/RJ123456','https://play.dlsite.com:444/work/RJ123456','https://u:p@play.dlsite.com/work/RJ123456'])assert.equal(isStoreSource(value),false,value);
const app=readFileSync(new URL('static/app.js',import.meta.url),'utf8');
const openCode=app.slice(app.indexOf('async function openSource('),app.indexOf('\nfunction settings('));
const importCode=app.slice(app.indexOf('async function interactiveImport('),app.indexOf('\nlet metadataKind='));
const fixture={title:'Imported fixture',cover:'',category:'manga',language:'Japanese',pages:10,author:[{name:'QA Author'}],circle:[],tag:[],series:[],character:[],warnings:[],ambiguities:[]};
function setup(match,matches){
 const calls=[],nodes={},buttons=matches.map(w=>({dataset:{sourceWork:w.id}}));
 const context={isPixivSource,isStoreSource,isDLsitePlaySeries,isPawchiveSource,routeVersion:1,draft:null,baseline:'',location:{hash:''},previousHash:'',
  route:()=>({params:new URLSearchParams({url:source})}),
  api:async(path,method,body)=>{calls.push({path,method,body});return path==='source-check'?{url:source,match,matches}:structuredClone(fixture)},
  blank:()=>({title:'',cover:'',category:'',language:'',pages:null,author:[],circle:[],tag:[],series:[],character:[],links:[],ratings:{}}),
  esc:s=>String(s).replaceAll('<','&lt;'),t:k=>ja[k]||en[k]||k,heading:()=>'',btn:()=>'',
  shell:()=>{},modal:html=>{context.modalHTML=html},closeModal:()=>{},dialog:{},
  $:selector=>nodes[selector]??=( {isConnected:true} ),$$:()=>buttons,
  history:{replaceState:(_,__,hash)=>context.location.hash=hash},
  edit:async()=>{},nav:path=>context.navigation=path,toast:()=>{},localizeError:s=>s,
  error:(_,e)=>{throw e},structuredClone,applyImported,metadataKinds,sameMetadataSet,hasImportedChanges};
 context.trashSourceUI={prepare:async()=>true,attach:(url,target,titles)=>context.api('source-attach','POST',{url,target,source_titles:titles})};
 vm.createContext(context);vm.runInContext(openCode+'\n'+importCode,context);
 return {context,calls,nodes,buttons};
}
const entry={id:'saved-id',title:'QA saved',source_url:'https://hitomi.la/reader/123.html#3'};
{
 const {context,calls}=setup('exact',[entry]);await context.openSource(1);
 assert.equal(context.navigation,'/work/saved-id');assert.equal(calls.length,1);assert.equal(context.draft,null);
}
{
 const {context,calls}=setup('none',[]);await context.openSource(1);
 assert.equal(context.location.hash,'#/new');assert.equal(context.draft.links[0].url,source);
 assert.equal(context.draft.title,fixture.title);assert.equal(calls[1].body.exclude,'');assert.equal(calls[1].body.allow_duplicate_title,undefined);
 assert.ok(calls.every(c=>c.path!=='works')); // Nothing is saved automatically.
}
for(const choice of ['existing','cancel','new']){
 const {context,calls,nodes,buttons}=setup('gallery',[entry]);const pending=context.openSource(1);
 await new Promise(resolve=>setImmediate(resolve));
 assert.ok(context.modalHTML.includes(entry.source_url));assert.equal(context.navigation,undefined);
 if(choice==='existing')buttons[0].onclick();
 else nodes[choice==='new'?'#source-import-new':'#source-cancel'].onclick();
 await pending;
 if(choice==='existing')assert.equal(context.navigation,'/work/saved-id');
 if(choice==='cancel')assert.equal(context.navigation,'/library');
 if(choice!=='new')assert.equal(calls.length,1);
 else assert.equal(context.draft.title,fixture.title);
}
{
 const {context,calls}=setup('none',[]);
 let finish;context.api=()=>new Promise(resolve=>finish=resolve);
 context.draft=context.blank();context.draft.links=[{url:source,is_primary:true}];
 const pending=context.interactiveImport(null,true);await new Promise(resolve=>setImmediate(resolve));context.routeVersion=2;
 const replacement=context.blank();context.draft=replacement;finish(structuredClone(fixture));await pending;
 assert.equal(context.draft,replacement);assert.equal(context.draft.title,'');
}
console.log('Source-flow checks passed: exact lookup, related-page choices, unsaved import, URL preservation, and stale-import protection.');

for(const value of ['https://pawchive.pw/fanbox/user/123/post/456','http://www.pawchive.pw/patreon/post/456/?tracking=1'])assert.ok(isPawchiveSource(value));
for(const value of ['https://pawchive.pw/fanbox/user/123','https://pawchive.pw/discord/user/123/post/456','https://pawchive.pw.evil/fanbox/post/456','https://u:p@pawchive.pw/fanbox/post/456','https://pawchive.pw:444/fanbox/post/456'])assert.equal(isPawchiveSource(value),false);
{
 const {context,calls}=setup('none',[]);
 const paw='https://pawchive.pw/fanbox/user/123/post/456';
 context.route=()=>({params:new URLSearchParams({url:paw})});
 const api=context.api;context.api=async(...args)=>{const result=await api(...args);return args[0]==='source-check'?{...result,url:paw}:result};
 await context.openSource(1);
 assert.equal(context.draft.links[0].url,paw);assert.equal(calls[1].body.url,paw);
 assert.ok(calls.every(c=>c.path!=='works'));
 const start=app.indexOf('function importerSourceURL(');
 vm.runInContext(app.slice(start,app.indexOf('\n',start)),context);
 assert.ok(context.importerSourceURL(paw));
 assert.equal(context.importerSourceURL('https://pawchive.pw/favorites'),false);
}
console.log('Pawchive source-flow checks passed');
