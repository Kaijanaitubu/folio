// Test actual source-flow functions without a browser, remote fetches, or DOM packages.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const load=async name=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('static/'+name,import.meta.url),'utf8')).toString('base64'));
const {bookmarklet}=await load('source-link.js');
const {en,ja}=await load('i18n.js');
const {applyImported,metadataKinds,sameMetadataSet,hasImportedChanges}=await load('import-policy.js');
const target='http://192.168.0.140:8765';
const source='https://hitomi.la/reader/123.html?x=a&y=b#7-8';
const script=bookmarklet(target);
const location={hostname:'hitomi.la',href:source};
vm.runInNewContext(script.slice(11),{location,alert:()=>assert.fail('unexpected alert')});
assert.equal(new URLSearchParams(location.href.split('?')[1]).get('url'),source);
assert.ok(location.href.startsWith(target+'/#/source?url='));
for(const host of ['momon-ga.com','www.momon-ga.com']){
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
const app=readFileSync(new URL('static/app.js',import.meta.url),'utf8');
const openCode=app.slice(app.indexOf('async function openSource('),app.indexOf('\nfunction settings('));
const importCode=app.slice(app.indexOf('async function interactiveImport('),app.indexOf('\nlet metadataKind='));
const fixture={title:'Imported fixture',cover:'',category:'manga',language:'Japanese',pages:10,author:[{name:'QA Author'}],circle:[],tag:[],series:[],character:[],warnings:[],ambiguities:[]};
function setup(match,matches){
 const calls=[],nodes={},buttons=matches.map(w=>({dataset:{sourceWork:w.id}}));
 const context={routeVersion:1,draft:null,baseline:'',location:{hash:''},previousHash:'',
  route:()=>({params:new URLSearchParams({url:source})}),
  api:async(path,method,body)=>{calls.push({path,method,body});return path==='source-check'?{url:source,match,matches}:structuredClone(fixture)},
  blank:()=>({title:'',cover:'',category:'',language:'',pages:null,author:[],circle:[],tag:[],series:[],character:[],links:[],ratings:{}}),
  esc:s=>String(s).replaceAll('<','&lt;'),t:k=>ja[k]||en[k]||k,heading:()=>'',btn:()=>'',
  shell:()=>{},modal:html=>{context.modalHTML=html},closeModal:()=>{},dialog:{},
  $:selector=>nodes[selector]??=( {isConnected:true} ),$$:()=>buttons,
  history:{replaceState:(_,__,hash)=>context.location.hash=hash},
  edit:async()=>{},nav:path=>context.navigation=path,toast:()=>{},localizeError:s=>s,
  error:(_,e)=>{throw e},structuredClone,applyImported,metadataKinds,sameMetadataSet,hasImportedChanges};
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
 const pending=context.interactiveImport(null,true);context.routeVersion=2;
 const replacement=context.blank();context.draft=replacement;finish(structuredClone(fixture));await pending;
 assert.equal(context.draft,replacement);assert.equal(context.draft.title,'');
}
console.log('Source-flow checks passed: exact lookup, related-page choices, unsaved import, URL preservation, and stale-import protection.');
