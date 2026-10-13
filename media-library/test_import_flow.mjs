// Actual import functions and policy; no remote calls or saved user entries.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const load=async name=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('static/'+name,import.meta.url),'utf8')).toString('base64'));
const {applyImported,mergeMetadata,metadataKinds,sameMetadataSet,hasImportedChanges}=await load('import-policy.js');
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
 const nodes=new Map(),context={draft:work(),routeVersion:1,applyImported,metadataKinds,sameMetadataSet,hasImportedChanges,displayName:e=>e.name,esc:s=>String(s).replaceAll('<','&lt;'),t:k=>(language==='ja'?ja:en)[k]||k,btn:()=>'',dialog:{},localizeError:s=>s,modal:html=>context.html=html,closeModal:()=>{},api:async()=>structuredClone(context.incoming),edit:()=>context.edited=true,toast:text=>context.lastToast=text,error:(_,e)=>{throw e}};
 context.incoming=imported();context.$=s=>{if(!nodes.has(s))nodes.set(s,{isConnected:true});return nodes.get(s)};
 context.$$=s=>s==='[data-import-mode]'?context.modes||[]:s==='[data-replace]:checked'?context.replacements||[]:context.aliasButtons||[];
 context.trashSourceUI={prepare:async()=>true,attach:(url,target,titles)=>context.api('source-attach','POST',{url,target,source_titles:titles})};
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
// Equality uses resolved identity, ignores order/duplicates, and keeps gender distinct.
assert.ok(sameMetadataSet(old,[...old].reverse()));
assert.ok(sameMetadataSet(old,[old[1],old[0],old[0]]));
assert.ok(sameMetadataSet([old[0]],[tag('Alias','female','idA')]));
assert.ok(!sameMetadataSet([tag('A','female')],[tag('A','male')]));
assert.ok(!sameMetadataSet([tag('A','female','one')],[tag('A','female','two')]));
assert.equal(mergeMetadata(old,[...old].reverse(),'overwrite'),old);
for(const language of ['en','ja']){
 const {context}=setup(language),original=context.draft,before=JSON.stringify(original);
 context.incoming=structuredClone(original);context.incoming.tag.reverse();
 context.incoming.title_matches=[{id:'same-title',title:original.title}];
 await context.interactiveImport('work');
 assert.equal(context.draft,original);assert.equal(JSON.stringify(context.draft),before);
 assert.equal(context.html,undefined);assert.equal(context.edited,undefined);
 assert.equal(context.lastToast,language==='ja'?'変更する情報はありません':'No information to change');
}
{
 const {context,nodes}=setup();
 context.incoming.tag=[...context.draft.tag].reverse();
 const originalTags=context.draft.tag,pending=context.interactiveImport('work');await tick();
 assert.ok(!context.html.includes('data-import-mode="tag"'));assert.ok(context.html.includes('data-import-mode="author"'));
 nodes.get('#replacement-apply').onclick();await pending;assert.equal(context.draft.tag,originalTags);
}
{
 const {context,nodes}=setup();context.incoming={tag:[old[0]]};
 const before=JSON.stringify(context.draft),pending=context.interactiveImport('work');await tick();
 // Default merge adds nothing; after confirming, report no changes and keep the draft.
 nodes.get('#replacement-apply').onclick();await pending;
 assert.equal(JSON.stringify(context.draft),before);assert.equal(context.edited,undefined);
 assert.equal(context.lastToast,en.importNoChanges);
}
// Simulate touch blur before click, keyboard activation, and stale editor handlers.
{
 const {context}=setup();context.draft.author[0].id='existing-author';
 context.incoming=structuredClone(context.draft);context.incoming.author=[{name:'Shared alias'}];
 context.incoming.ambiguities=[{kind:'author',name:'Shared alias',gender:'neutral',choices:[context.draft.author[0]]}];
 context.aliasButtons=[{dataset:{aliasId:'existing-author'}}];
 const before=JSON.stringify(context.draft),pending=context.interactiveImport('work');await tick();
 context.aliasButtons[0].onclick();await pending;
 assert.equal(JSON.stringify(context.draft),before);assert.equal(context.lastToast,en.importNoChanges);assert.equal(context.edited,undefined);
}
function bookmarkSetup(){
 const {context}=setup(),handlers={},input={value:'Typed title',isConnected:true,addEventListener:(name,fn)=>handlers[name]=fn,focus:()=>{context.document.activeElement=input;handlers.focus()}},button={dataset:{bookmarkTitle:'0'}};
 const panel={hidden:true,addEventListener:(name,fn)=>handlers['panel-'+name]=fn,contains:node=>node===button};
 context.document={activeElement:input};context.$=s=>s==='[data-field="title"]'?input:panel;context.$$=()=>[button];
 context.bindBookmarkTitles();handlers.focus();return {context,input,panel,button,handlers};
}
{
 const {context,input,panel,button,handlers}=bookmarkSetup();let prevented=false;
 button.onpointerdown({button:0,preventDefault:()=>prevented=true});handlers.blur({relatedTarget:null});
 assert.ok(prevented);assert.equal(panel.hidden,false);
 button.onpointerup({button:0,preventDefault:()=>{}});
 assert.equal(input.value,'Original name');assert.equal(context.draft.title,'Original name');
 assert.equal(context.edited,undefined);assert.equal(panel.hidden,false);
}
{
 const {context,input,panel,button,handlers}=bookmarkSetup();handlers.blur({relatedTarget:button});assert.equal(panel.hidden,false);
 button.onclick();assert.equal(input.value,'Original name');assert.equal(context.draft.title,'Original name');
 handlers['panel-focusout']({relatedTarget:null});assert.equal(panel.hidden,true);
}
{
 const {context,input,button}=bookmarkSetup();context.draft=work();button.onclick();assert.equal(input.value,'Typed title');
}
console.log('Import flow checks passed: EN/JA, overwrite/merge/keep, unchanged resolved sets and scalar values, no-op imports, mobile pointer/blur selection, keyboard selection, cancellation and stale responses.');

// New/bookmarklet drafts always offer secondary attachment for a title warning,
// even with conflicting authors, the same provider, or no automatic candidates.
for(const automatic of [[],[{id:'other',title:'New title',evidence:{author:true}}]]){
 const {context}=setup();let calls=[];
 context.incoming.title_matches=[{id:'other',title:'New title',authors:['Other author']}];
 context.incoming.cross_candidates=automatic;
 context.nhentaiUI={chooseMatch:async(incoming,choices)=>{
  assert.equal(choices.length,1);assert.equal(choices[0].id,'other');
  if(automatic.length)assert.equal(choices[0].evidence.author,true);
  return {action:'attach',target:'other'};
 }};
 context.api=async(path,method,data)=>{calls.push({path,data});return path==='source-attach'?{id:'other'}:structuredClone(context.incoming)};
 context.markLibraryDirty=()=>context.dirty=true;context.nav=url=>context.destination=url;
 await context.interactiveImport(null,true);
 assert.equal(calls[1].path,'source-attach');assert.equal(calls[1].data.target,'other');
 assert.equal(context.destination,'/work/other');assert.equal(context.draft,null);assert.equal(context.edited,undefined);
}
{
 const {context}=setup(),before=JSON.stringify(context.draft);
 context.incoming.title_matches=[{id:'other',title:'New title'}];
 context.nhentaiUI={chooseMatch:async()=>null};
 await context.interactiveImport(null,true);
 assert.equal(JSON.stringify(context.draft),before);assert.equal(context.edited,undefined);
}
