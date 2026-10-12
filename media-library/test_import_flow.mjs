// Actual import functions and policy; no remote calls or saved user entries.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const load=async name=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('static/'+name,import.meta.url),'utf8')).toString('base64'));
const {applyImported,mergeMetadata,metadataKinds}=await load('import-policy.js');
const {en,ja}=await load('i18n.js');
const tag=(name,gender='neutral',id)=>({name,gender,...id?{id}:{}});
const old=[tag('A','female','idA'),tag('B')],incoming=[tag('Alias','female','idA'),tag('A','male','idM')];
assert.deepEqual(mergeMetadata(old,incoming,'keep'),old);
assert.deepEqual(mergeMetadata(old,incoming,'overwrite'),incoming);
assert.deepEqual(mergeMetadata(old,incoming,'merge'),[...old,incoming[1]]);
for(const mode of ['keep','merge','overwrite']){
 assert.deepEqual(mergeMetadata(old,[],mode),old);
 assert.deepEqual(mergeMetadata([],incoming,mode),incoming);
}
const app=readFileSync(new URL('static/app.js',import.meta.url),'utf8');
const code=app.slice(app.indexOf('function summaryCards('),app.indexOf('\nlet metadataKind='));
const work=()=>({title:'Existing title',cover:'',pages:5,category:'',language:'',author:[tag('Old author')],circle:[],tag:structuredClone(old),series:[],character:[],ratings:{quality:4},review:'Keep review',bought:true,links:[{url:'https://hitomi.la/reader/1.html'}],bookmark_names:['Original name']});
const imported=()=>({title:'New title',cover:'https://example.org/cover',pages:8,author:[tag('New author')],tag:structuredClone(incoming),series:[tag('Series')],circle:[],character:[],warnings:[],ambiguities:[],title_matches:[]});
function setup(language='en'){
 const nodes=new Map(),context={draft:work(),routeVersion:1,applyImported,metadataKinds,displayName:e=>e.name,esc:s=>String(s).replaceAll('<','&lt;'),t:k=>(language==='ja'?ja:en)[k]||k,btn:()=>'',dialog:{},localizeError:s=>s,modal:html=>context.html=html,closeModal:()=>{},api:async()=>structuredClone(context.incoming),edit:()=>context.edited=true,toast:()=>{},error:(_,e)=>{throw e}};
 context.incoming=imported();context.$=s=>{if(!nodes.has(s))nodes.set(s,{isConnected:true});return nodes.get(s)};
 context.$$=s=>s==='[data-import-mode]'?context.modes||[]:s==='[data-replace]:checked'?context.replacements||[]:context.aliasButtons||[];
 vm.createContext(context);vm.runInContext(code,context);return {context,nodes};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
for(const language of ['en','ja']){
 for(const mode of ['merge','overwrite','keep']){
  const {context,nodes}=setup(language),before=structuredClone(context.draft);
  const pending=context.interactiveImport('work');await tick();
  assert.ok(context.html.includes(language==='ja'?'上書き':'Overwrite'));
  assert.ok(context.html.includes('Old author'));assert.ok(context.html.includes('New author'));
  context.modes=[{dataset:{importMode:'tag'},value:mode},{dataset:{importMode:'author'},value:'overwrite'}];
  context.replacements=[{dataset:{replace:'title'}}];nodes.get('#replacement-apply').onclick();await pending;
  assert.deepEqual(context.draft.tag,mergeMetadata(before.tag,context.incoming.tag,mode));
  assert.equal(context.draft.author[0].name,'New author');assert.equal(context.draft.title,'New title');
  assert.equal(context.draft.series[0].name,'Series');assert.equal(context.draft.ratings.quality,4);assert.equal(context.draft.review,'Keep review');assert.equal(context.draft.bought,true);
 }
 const {context,nodes}=setup(language),before=JSON.stringify(context.draft);
 const pending=context.interactiveImport('work');await tick();nodes.get('#replacement-cancel').onclick();await pending;
 assert.equal(JSON.stringify(context.draft),before);assert.equal(context.edited,undefined);
}
{
 const {context,nodes}=setup();context.incoming.title_matches=[{id:'other',title:'New title',authors:['Other author'],primary_url:'https://example.org/existing'}];
 const before=JSON.stringify(context.draft),pending=context.interactiveImport('work');await tick();
 assert.ok(context.html.includes('Other author'));assert.ok(context.html.includes('https://example.org/existing'));
 nodes.get('#import-warning-cancel').onclick();await pending;assert.equal(JSON.stringify(context.draft),before);
}
{
 const {context,nodes}=setup(),pending=context.interactiveImport('work');await tick();
 const replacement=work();context.draft=replacement;context.routeVersion++;
 nodes.get('#replacement-apply').onclick();await pending;assert.equal(context.draft,replacement);assert.equal(context.edited,undefined);
}
{
 const {context,nodes}=setup(),before=JSON.stringify(context.draft);
 context.incoming.ambiguities=[{kind:'author',name:'New author',gender:'neutral',choices:[tag('Choice','neutral','choice')]}];
 context.aliasButtons=[{dataset:{aliasId:'choice'}}];
 const pending=context.interactiveImport('work');await tick();nodes.get('#alias-cancel').onclick();await pending;
 assert.equal(JSON.stringify(context.draft),before);
}
console.log('Import flow checks passed: EN/JA, overwrite/merge/keep, empty fields, stable ratings/notes, same-title warning, cancellation and stale responses.');
