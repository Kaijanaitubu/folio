import assert from 'node:assert/strict';
import {createWorkMergeUI,metadataPatch} from './static/work-merge-ui.js';
import {createNhentaiUI} from './static/nhentai-ui.js';
const base={title:'Target',cover:'',category:'',pages:null,language:'',author:[],circle:[],series:[],character:[],tag:[{id:'old',name:'Old'}],review:'Private',marks:[1],ratings:{a:5},links:[{url:'https://example.com/target',is_primary:true}]};
const incoming={...base,title:'Source',pages:10,cover:'https://example.com/cover',author:[{name:'Author'}],tag:[{id:'new',name:'New'}],review:'Never transfer'};
for(const lang of ['en','ja'])for(const mode of ['links','merge','overwrite','keep','cancel','stale']){
 const nodes=new Map(),get=s=>{if(!nodes.has(s))nodes.set(s,{checked:false,hidden:true});return nodes.get(s)};
 let html='',closed=0,current=true;
 const ui=createWorkMergeUI({modal:h=>html=h,closeModal:()=>closed++,dialog:{},$:get,$$:s=>s==='[data-merge-mode]'?[{dataset:{mergeMode:'tag'},value:mode}]:[{dataset:{mergeScalar:'title'}}],esc:x=>String(x).replaceAll('<','&lt;'),t:x=>x,lang:()=>lang});
 const p=ui.review({source:incoming,target:base,links:[{url:'https://example.com/source'}]},()=>current,true);
 assert.equal(get('#merge-metadata').checked,false);assert(!html.includes('review">'));assert(html.includes('Source'));assert(html.includes('Target'));
 if(mode==='stale')current=false;
 if(mode==='cancel')get('#merge-cancel').onclick();
 else {get('#merge-metadata').checked=mode!=='links';get('#merge-metadata').onchange();assert.equal(get('#merge-fields').hidden,mode==='links');get('#merge-apply').onclick();get('#merge-apply').onclick()}
 const patch=await p;assert.equal(closed,1);
 if(['stale','cancel'].includes(mode)){assert.equal(patch,null);continue}
 if(mode==='links'){assert.deepEqual(patch,{});continue}
 assert.equal(patch.title,'Source');assert.equal(patch.pages,10);assert.equal(patch.cover,incoming.cover);assert.deepEqual(patch.author,incoming.author);
 assert(!('review' in patch));assert(!('marks' in patch));assert(!('ratings' in patch));
 if(mode==='keep')assert(!('tag' in patch));
 if(mode==='overwrite')assert.deepEqual(patch.tag,incoming.tag);
 if(mode==='merge')assert.deepEqual(patch.tag,[...base.tag,...incoming.tag]);
}
assert.deepEqual(metadataPatch(base,{...base,tag:[...base.tag].reverse()}),{});
// Draft attachment passes every link and applies only after the review succeeds.
for(const cancel of [false,true]){
 const calls=[],nodes=new Map(),get=s=>{if(!nodes.has(s))nodes.set(s,{checked:false});return nodes.get(s)};
 const draft={...incoming,links:[{url:'https://example.com/a'},{url:'https://example.com/b'}]};
 const ui=createWorkMergeUI({api:async(path,method,body)=>{calls.push({path,body});return path.endsWith('preview')?{source:body.draft,target:base,links:body.draft.links,signature:'guard',trash_conflicts:[]}:{id:'target'}},modal:()=>{},closeModal:()=>{},dialog:{},$:get,$$:()=>[],esc:String,t:x=>x,lang:()=> 'en'});
 const pending=ui.attach(draft,'target');await new Promise(r=>setImmediate(r));get(cancel?'#merge-cancel':'#merge-apply').onclick();const result=await pending;
 assert.equal(calls.length,cancel?1:2);assert.equal(draft.links.length,2);
 if(!cancel){assert.equal(result.id,'target');assert.deepEqual(calls[1].body.draft.links,draft.links);assert.deepEqual(calls[1].body.metadata_patch,{})}
}
console.log('Merge UI: EN/JA, links-only default, scalar overwrite, multi merge/overwrite/keep, empty fills, equality, personal records, cancellation, stale/double activation and all draft links passed.');

for(const mode of ['ok','all','cancel','stale']){
 const nodes=new Map(),get=s=>{if(!nodes.has(s))nodes.set(s,{isConnected:true,style:{},value:'all',checked:false,addEventListener:()=>{}});return nodes.get(s)},calls=[];
 const job={status:'awaiting_review',enumeration_done:true,counts:{match_review:1},match_policy:'ask',items:[{id:'i',title:'Source',status:'match_review',warnings:{candidates:[{id:'target',title:'Target'}]}}]};
 const ui=createNhentaiUI({$:get,$$:()=>[],api:async(path,method,body)=>{calls.push({path,body});if(path.endsWith('merge-preview'))return {source:incoming,target:base,links:[],signature:'guard'};if(path.endsWith('decide')){job.items[0].status='linked';return {resolved:1}}return job},t:x=>x,esc:String,btn:()=>'',modal:()=>{},closeModal:()=>{},dialog:{},toast:()=>{},shell:()=>{},heading:()=>'',summaryCards:()=>'',markLibraryDirty:()=>{},workMergeUI:{review:async(p,current)=>{assert.equal(p.signature,'guard');if(mode==='all')assert.equal(p.notice,'matchAllMetadataHint');if(mode==='stale')get('#job-summary').isConnected=false;return mode==='cancel'?null:{pages:10}}}});
 await ui.jobPage('j');const pending=get('#review-i').onclick();get('#match-all').checked=mode==='all';get('#match-attach').onclick();await pending;
 const apply=calls.find(c=>c.path.endsWith('/decide'));
 if(['cancel','stale'].includes(mode))assert.equal(apply,undefined);
 else{assert.equal(apply.body.merge_signature,'guard');assert.deepEqual(apply.body.metadata_patch,{pages:10});assert.equal(apply.body.apply_all,mode==='all')}
}
console.log('Batch merge UI: shared review, metadata/signature forwarding, apply-all scope hint, cancellation and stale-page guards passed.');
