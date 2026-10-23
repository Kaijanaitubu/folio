// Unit tests of the actual prototype handlers with DOM stubs; no browser or live database.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {STORAGE_KEY,fixtures,blankWork,clone,associate,errors,safeURL,sourceSite,unique,allLanguages,representativePages,representativeDate} from './static/prototypes/work/model.mjs';
const code=readFileSync(new URL('static/prototypes/work/work.js',import.meta.url),'utf8');
function fn(name){const start=code.indexOf('function '+name+'('),end=code.indexOf('\nfunction ',start+1);assert.ok(start>=0&&end>start);return code.slice(start,end);}
function setup(){
 const nodes={},events=[];
 const context={state:fixtures(),draft:clone(fixtures().works[0]),currentId:'atelier',mode:'edit',lastHash:'#/edit/atelier',baseline:JSON.stringify(fixtures().works[0]),clone,associate,errors,safeURL,sourceSite,blankWork,
  t:k=>k,esc:v=>String(v??''),btn:(label,attrs)=>`<button ${attrs}>${label}</button>`,
  location:{hash:'#/edit/atelier'},window:{scrollTo(){}},
  store:()=>{events.push('store');return true;},toast:message=>events.push(message),render:()=>events.push('render'),
  modal:(title,html)=>{context.dialogHTML=html;events.push('dialog');},
  $:key=>nodes[key]??=(key==='#dialog'?{close:()=>events.push('close')}:{innerHTML:''}),
  $$:()=>[{dataset:{field:'title'},parentElement:null,setAttribute(){},focus(){events.push('focus-title');}}]
 };
 context.history={replaceState:(_a,_b,hash)=>{context.location.hash=hash;},pushState:(_a,_b,hash)=>{context.location.hash=hash;}};
 context.dirty=()=>context.draft&&JSON.stringify(context.draft)!==context.baseline;
 vm.createContext(context);
 vm.runInContext(['requestLeave','go','route','saveDraft','updateField','newWork'].map(fn).join('\n'),context);
 return {c:context,nodes,events};
}
for(const target of ['#/work/atelier','#/work/stargazer','#/edit/anthology']){
 const {c,nodes,events}=setup();c.draft.title='Edited title';c.go(target);
 assert.equal(c.location.hash,'#/edit/atelier');assert.match(c.dialogHTML,/leave-save/);
 nodes['#leave-stay'].onclick();assert.equal(c.draft.title,'Edited title');assert.ok(!events.includes('store'));
 c.go(target);nodes['#leave-save'].onclick();
 assert.equal(c.state.works[0].title,'Edited title');assert.equal(c.location.hash,target);assert.equal(c.draft,null);assert.ok(events.includes('store'));
 c.route();assert.equal(c.currentId,target.split('/').at(-1));
 if(target.startsWith('#/edit/'))assert.equal(c.draft.id,'anthology');
}
{
 const {c,nodes,events}=setup();c.draft.title='Discard me';c.go('#/work/stargazer');nodes['#leave-discard'].onclick();
 assert.equal(c.location.hash,'#/work/stargazer');assert.equal(c.state.works[0].title,'雨上がりのアトリエ');assert.ok(!events.includes('store'));
}
for(const mutation of [d=>d.title=' ',d=>d.links[0].url='bad',d=>d.links[0].pages=-1,d=>d.links[0].dates[0].value='2026-02-30',d=>d.relations[0].url='bad']){
 const {c,nodes,events}=setup();mutation(c.draft);c.go('#/work/stargazer');nodes['#leave-save'].onclick();
 assert.equal(c.location.hash,'#/edit/atelier');assert.ok(c.draft);assert.match(nodes['#form-errors'].innerHTML,/role="alert"/);assert.ok(!events.includes('store'));
}
{
 const {c,nodes,events}=setup();c.draft.title='';c.go('#/work/stargazer');nodes['#leave-save'].onclick();assert.ok(events.includes('focus-title'));
}
{
 const {c,nodes}=setup();c.draft.title='Not yet persisted';c.store=()=>false;c.go('#/work/stargazer');nodes['#leave-save'].onclick();
 assert.equal(c.location.hash,'#/edit/atelier');assert.equal(c.draft.title,'Not yet persisted');assert.equal(c.state.works[0].title,'雨上がりのアトリエ');
}
{
 const {c,nodes}=setup();c.draft.title='Saved before back';c.location.hash='#/work/stargazer';c.route();
 assert.equal(c.location.hash,'#/edit/atelier');nodes['#leave-save'].onclick();assert.equal(c.location.hash,'#/work/stargazer');assert.equal(c.state.works[0].title,'Saved before back');
}
{
 const {c,nodes}=setup();c.draft.title='Saved before new';c.requestLeave(c.newWork);nodes['#leave-save'].onclick();
 assert.equal(c.state.works[0].title,'Saved before new');assert.equal(c.draft.title,'');assert.notEqual(c.draft.id,'atelier');assert.equal(c.location.hash,'#/edit/'+c.draft.id);
}
{
 const {c,events}=setup();c.draft.title='Editing same route';c.go('#/edit/atelier');assert.equal(events.length,0);assert.equal(c.draft.title,'Editing same route');
 c.updateField('links.0.label','My edition');assert.equal(c.draft.links[0].site,'dlsite');
 c.updateField('links.0.url','https://creator.fanbox.cc/posts/1');assert.equal(c.draft.links[0].site,'fanbox');
 c.updateField('links.0.label','DLsite');assert.equal(c.draft.links[0].site,'fanbox');
}

// Render the real templates to strings and inspect their control structure.
const ctx={state:fixtures(),draft:clone(fixtures().works[0]),language:'ja',unique,openDetails:new Set(),safeURL,
 document:{querySelector(){},querySelectorAll(){return[];}},bindEditor(){},shell:html=>ctx.html=html};
vm.createContext(ctx);
vm.runInContext(code.slice(code.indexOf('const messages='),code.indexOf("let language='ja'"))+code.slice(code.indexOf('const t='),code.indexOf('let draft='))+code.slice(code.indexOf('const markDefs='),code.indexOf('\nfunction markButtons'))+['sourceCard','linkEditor','editorPage','chipField','identityFields','markButtons','cover'].map(fn).join('\n'),ctx);
let html=ctx.sourceCard(ctx.draft.links[0],0);
assert.match(html,/<a class="source-main"[^>]*href="https:\/\/example.com\/store-a"/);
assert.match(html,/発売日 2026-10-10/);assert.ok(html.indexOf('発売日 2026-10-10')<html.indexOf('class="source-toggle"'));
assert.match(html,/<\/a><button type="button" class="source-toggle"/);assert.match(html,/aria-expanded="false"/);assert.match(html,/id="source-supplement-0" hidden/);
assert.ok(!html.includes('<summary>'));
ctx.openDetails.add('source-store-a');assert.match(ctx.sourceCard(ctx.draft.links[0],0),/aria-expanded="true"/);
ctx.editorPage();html=ctx.html;
assert.ok(!html.includes('<details'));assert.match(html,/section-no">04<\/span><h2>詳細情報/);
assert.match(html,/type="submit" form="work-form"/);assert.match(html,/data-field="links.0.label"/);
assert.ok(!html.includes('data-field="links.0.site"'));assert.equal((html.match(/data-cancel-edit/g)||[]).length,2);
assert.match(html,/data-field="age"/);assert.match(html,/data-field="links.0.pages"/);
assert.match(html,/data-field="relations.0.url"/);assert.match(html,/data-field="links.0.dates.0.value"/);
ctx.language='en';ctx.editorPage();assert.match(ctx.html,/Save/);assert.match(ctx.html,/Source label \/ edition \(free text\)/);

const attributes={'aria-expanded':'false','aria-controls':'source-supplement-0'},supplement={hidden:true},stored=new Map(),detailNodes={};
const toggle={dataset:{sourceToggle:'source-store-a'},getAttribute:k=>attributes[k],setAttribute:(k,v)=>attributes[k]=v};
ctx.document.querySelector=s=>detailNodes[s]??={};
ctx.document.querySelectorAll=s=>s==='[data-source-toggle]'?[toggle]:[];
ctx.document.getElementById=()=>supplement;
Object.assign(ctx,{STORAGE_KEY,allLanguages,representativePages,representativeDate,stars:()=>'',bindMetadataSearch(){},localStorage:{setItem:(k,v)=>stored.set(k,v)}});
vm.runInContext(['summary','metadata','detailPage'].map(fn).join('\n'),ctx);
ctx.detailPage(ctx.draft);toggle.onclick();
assert.equal(supplement.hidden,false);assert.equal(attributes['aria-expanded'],'true');assert.ok(JSON.parse(stored.get(STORAGE_KEY+'.open')).includes('source-store-a'));
toggle.onclick();assert.equal(supplement.hidden,true);assert.equal(attributes['aria-expanded'],'false');
console.log('Work prototype flow: save/discard/stay, navigation targets, validation/storage failures, new entries, free labels and visible form controls passed.');
