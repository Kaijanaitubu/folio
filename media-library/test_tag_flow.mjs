import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const load=async file=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('static/'+file,import.meta.url),'utf8')).toString('base64'));
const {createTagUI,tagEn,tagJa}=await load('tag-ui.js');
const {en,ja}=await load('i18n.js');
function setup(language){
 const text={...(language==='ja'?ja:en),...(language==='ja'?tagJa:tagEn)},h={nodes:new Map(),calls:[],applied:[],shared:[],html:'',dialog:{},dirty:0};
 const node=(value='')=>({value,isConnected:true,addEventListener(type,fn){this['on'+type]=fn},focus(){this.focused=true}});
 h.close=()=>{for(const n of h.nodes.values())n.isConnected=false;h.nodes.clear()};
 const $=s=>h.nodes.get(s)||null;
 const modal=html=>{
  h.close();h.html=html;
  for(const match of html.matchAll(/id="([^"]+)"/g))h.nodes.set('#'+match[1],node());
  for(const match of html.matchAll(/<select id="([^"]+)">([\s\S]*?)<\/select>/g)){
   const options=[...match[2].matchAll(/<option value="([^"]*)"([^>]*)>/g)];$('#'+match[1]).value=(options.find(o=>o[2].includes('selected'))||options[0])?.[1]||'';
  }
  for(const match of html.matchAll(/<input id="([^"]+)"[^>]*value="([^"]*)"/g))$('#'+match[1]).value=match[2];
  for(const match of html.matchAll(/<textarea id="([^"]+)">([\s\S]*?)<\/textarea>/g))$('#'+match[1]).value=match[2];
  h.choices=[...html.matchAll(/data-collision-target="([^"]+)"/g)].map(m=>Object.assign(node(),{dataset:{collisionTarget:m[1]}}));
 };
 h.$=$;h.ui=createTagUI({$, $$:s=>s==='[data-collision-target]'?h.choices:[],api:async(path,method,body)=>{h.calls.push({path,method,body});return h.respond(path,method,body)},t:k=>text[k]||k,esc:String,btn:(label,id)=>`<button id="${id}">${label}</button>`,modal,closeModal:h.close,dialog:h.dialog,error:(_,e)=>{throw e},markLibraryDirty:()=>h.dirty++,displayName:e=>e.display_alias||e.name});return h;
}
const original={id:'none',kind:'tag',name:'Archive',gender:'neutral',aliases:['Blue'],display_alias:'',sort_reading:''};
const female={...original,id:'female',gender:'female'};
const event={preventDefault(){}};
const tick=()=>new Promise(r=>setImmediate(r));
for(const language of ['en','ja']){
 const h=setup(language);h.respond=()=>[female];
 h.ui.workEditor(original,e=>h.applied.push(e),id=>h.shared.push(id));
 assert.ok(h.html.includes(language==='ja'?'未指定（none）':'None'));
 assert.ok(h.$('#work-tag-shared'));h.$('#work-tag-gender').value='female';await h.$('#work-tag-form').onsubmit(event);
 assert.equal(h.applied[0].id,'female');assert.equal(h.calls.length,1);assert.equal(h.calls[0].path,'entities/attribute');
 h.respond=()=>[];h.ui.workEditor(original,e=>h.applied.push(e),()=>{});h.$('#work-tag-gender').value='male';await h.$('#work-tag-form').onsubmit(event);
 assert.equal(h.applied[1].gender,'male');assert.equal(h.applied[1].id,undefined);assert.equal(h.applied[1].literal_name,true);
 assert.ok(h.calls.every(c=>c.path==='entities/attribute')); // No shared creation before saving the work.
 const count=h.applied.length;h.ui.workEditor(original,e=>h.applied.push(e),()=>{});h.$('#work-tag-cancel').onclick();assert.equal(h.applied.length,count);
 h.respond=()=>original;h.ui.workEditor(original,()=>{},()=>{});await h.$('#work-tag-shared').onclick();
 assert.ok(h.$('#metadata-name'));assert.equal(h.$('#metadata-name').value,'Archive');assert.equal(h.$('#metadata-gender').value,'neutral');assert.ok(h.$('#metadata-merge'));
 // Selecting a primary name swaps the draft and preserves the previous name.
 h.ui.editor(original,id=>h.applied.push(id));const beforePrimary=h.calls.length;
 h.$('#metadata-display').onchange({target:{value:'Blue'}});
 assert.equal(h.$('#metadata-name').value,'Blue');assert.equal(h.$('#metadata-aliases').value,'Archive');assert.equal(h.calls.length,beforePrimary);
 h.$('#metadata-display').onchange({target:{value:'Archive'}});
 assert.equal(h.$('#metadata-name').value,'Archive');assert.equal(h.$('#metadata-aliases').value,'Blue');
 h.$('#metadata-display').onchange({target:{value:'Blue'}});
 h.respond=()=>({id:'none'});h.$('#metadata-form').onsubmit(event);await tick();
 assert.equal(h.calls.at(-1).body.name,'Blue');assert.deepEqual(h.calls.at(-1).body.aliases,['Archive']);assert.equal(h.calls.at(-1).body.display_alias,'');
 h.ui.editor(original,()=>{});h.$('#metadata-display').onchange({target:{value:'Blue'}});const beforeCancel=h.calls.length;h.$('#metadata-cancel').onclick();assert.equal(h.calls.length,beforeCancel);assert.equal(original.name,'Archive');
 for(const kind of ['author','circle','series','character']){
  h.ui.editor({...original,kind},()=>{});assert.equal(h.$('#metadata-gender'),null);
  h.$('#metadata-display').onchange({target:{value:'Blue'}});h.respond=()=>({id:kind});h.$('#metadata-form').onsubmit(event);await tick();
  assert.equal(h.calls.at(-1).body.kind,kind);assert.equal(h.calls.at(-1).body.name,'Blue');assert.deepEqual(h.calls.at(-1).body.aliases,['Archive']);
 }
 h.ui.editor(null,id=>h.applied.push(id));h.$('#metadata-name').value='Blue';
 h.respond=()=>{throw Object.assign(Error('collision'),{tag_conflicts:[{name:'Blue',choices:[original]}],signature:'snapshot'})};
 const submit=h.$('#metadata-form').onsubmit(event);await tick();assert.ok(h.choices.length);await h.choices[0].onclick();await tick();await submit;
 assert.equal(h.applied.at(-1),'none');assert.ok(!h.nodes.size);
 // Closing a pending local lookup does not reopen a modal or apply a late result.
 let release;h.respond=()=>new Promise(r=>release=r);h.ui.workEditor(original,e=>h.applied.push(e),()=>{});h.$('#work-tag-gender').value='female';
 const pending=h.$('#work-tag-form').onsubmit(event);const before=h.applied.length;h.$('#work-tag-cancel').onclick();release([female]);await pending;assert.equal(h.applied.length,before);
}
console.log('Tag UI checks passed: EN/JA, local attribute replacement, deferred creation, cancel, shared editor, alias reuse, and late-response protection.');

// Work drafts may carry imported names without the directory's kind field.
for(const language of ['en','ja']){
 for(const kind of ['author','circle','series','character']){
  const h=setup(language),item={...original,id:'source'};delete item.kind;
  const target={...original,id:'target',kind,name:'Target'};
  h.respond=path=>path.startsWith('entities?kind='+kind+'&')?[target]:[];
  h.ui.editor(item,()=>{}, {kind});h.$('#metadata-merge').onclick();await tick();
  assert.equal(h.calls.at(-1).path,'entities?kind='+kind+'&q=');
  assert.ok(h.$('#merge-target').innerHTML.includes('value="target"'));
 }
}

for(const language of ['en','ja']){
 // An unsaved imported author is replaced by an existing author in the work draft.
 const h=setup(language),target={...original,id:'author-target',kind:'author',name:'Existing author'};
 h.respond=path=>path.startsWith('entities?')?[target]:assert.fail('Unexpected mutation: '+path);
 h.ui.editor({name:'Imported author'},id=>h.applied.push(id),{kind:'author'});
 assert.ok(h.html.includes(language==='ja'?'既存のメタデータを使う':'Use existing metadata'));
 h.$('#metadata-merge').onclick();await tick();
 assert.equal(h.$('#merge-next').disabled,false);h.$('#merge-target').value=target.id;
 await h.$('#merge-next').onclick();assert.deepEqual(h.applied,[target.id]);assert.ok(h.calls.every(c=>!c.method));
 // Saving an unsaved name creates metadata rather than PUT /undefined.
 h.ui.editor({name:'Imported author'},()=>{}, {kind:'author'});h.respond=()=>({id:'created'});
 h.$('#metadata-form').onsubmit(event);await tick();
 assert.equal(h.calls.at(-1).path,'entities');assert.equal(h.calls.at(-1).method,'POST');assert.equal(h.calls.at(-1).body.kind,'author');
 // Existing authors still use the preview + signature-protected shared merge.
 const source={...original,id:'source-author',kind:'author'};
 h.respond=path=>path.startsWith('entities?')?[source,target,{...target,id:'wrong-kind',kind:'tag'}]:path.endsWith('/merge-preview')?{source,target,count:2,signature:'reviewed'}:{id:target.id};
 h.ui.editor(source,id=>h.applied.push(id));h.$('#metadata-merge').onclick();await tick();
 assert.ok(!h.$('#merge-target').innerHTML.includes('wrong-kind'));
 assert.ok(!h.$('#merge-target').innerHTML.includes('value="source-author"'));
 h.$('#merge-target').value=target.id;const review=h.$('#merge-next').onclick();await tick();
 assert.ok(h.$('#merge-confirm'));await h.$('#merge-confirm').onclick();await review;
 assert.equal(h.calls.at(-1).path,'entities/source-author/merge');assert.equal(h.calls.at(-1).body.signature,'reviewed');
 // Empty searches disable selection and show a reason; cancellation ignores late results.
 h.respond=()=>[];h.ui.mergeEditor(source,()=>{});await tick();
 assert.equal(h.$('#merge-next').disabled,true);assert.equal(h.$('#merge-target').disabled,true);assert.equal(h.$('#merge-empty').hidden,false);
 let release;h.respond=()=>new Promise(resolve=>release=resolve);h.ui.mergeEditor(source,()=>assert.fail('Late selection'));
 h.$('#merge-cancel').onclick();h.ui.editor(target,()=>{});const nextHTML=h.html;release([target]);await tick();
 assert.equal(h.html,nextHTML);assert.equal(h.$('#merge-target'),null);
}
// The actual work editor deduplicates the source/target after a metadata merge.
{
 const app=readFileSync(new URL('static/app.js',import.meta.url),'utf8');
 const body=app.slice(app.indexOf(" $$('[data-edit-chip]').forEach"),app.indexOf(" $$('[data-score]').forEach"));
 const vm=await import('node:vm');
 for(const stale of [false,true]){
  let onSave,release;const source={id:'source',name:'Source'},target={id:'target',name:'Target'};
  const initial={author:[source,target],title:'Unsaved work',review:'Keep'},button={dataset:{editChip:'author:0'}};
  const context={draft:initial,id:'work',$$:()=>[button],metadataEditor:(item,kind,callback)=>{assert.equal(kind,'author');onSave=callback},api:()=>stale?new Promise(resolve=>release=resolve):Promise.resolve(target),markLibraryDirty:()=>{},edit:()=>{context.edited=true}};
  vm.runInNewContext(body,context);button.onclick();const pending=onSave(target.id);
  if(stale){context.draft={author:[],title:'Another work'};release(target)}await pending;
  if(stale){assert.equal(context.draft.title,'Another work');assert.equal(context.edited,undefined)}
  else{assert.deepEqual(initial.author,[target]);assert.equal(initial.review,'Keep');assert.equal(context.edited,true)}
 }
}
console.log('Metadata merge regressions passed: inferred kind, unsaved author reuse/create, existing merge, empty/cancelled lookup, work deduplication and stale drafts.');
