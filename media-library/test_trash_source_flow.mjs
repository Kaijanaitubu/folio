import assert from 'node:assert/strict';
import {createTrashSourceUI} from './static/trash-source-ui.js';
const tick=()=>new Promise(r=>setImmediate(r));
const work=()=>({title:'Current',tag:[{id:'a',name:'A'}],author:[],circle:[],series:[],character:[],links:[{url:'https://example.org/item',is_primary:true}]});
function setup(secondary=false){
 const nodes=new Map(),calls=[];let html='';const draft=work();draft.links[0].is_primary=!secondary;
 const incoming={...work(),title:'Old',tag:[{id:'b',name:'B'}]};
 const ui=createTrashSourceUI({api:async(...args)=>{calls.push(args);return {works:[incoming],signature:'snapshot'}},modal:s=>html=s,closeModal:()=>{},dialog:{},$:s=>{if(!nodes.has(s))nodes.set(s,{});return nodes.get(s)},$$:s=>s.includes('mode')?[{dataset:{trashMode:'tag'},value:'overwrite'}]:[],esc:s=>String(s),t:s=>s,lang:()=> 'en'});
 return {ui,draft,nodes,calls,get html(){return html}};
}
{
 const s=setup(),before=JSON.stringify(s.draft),pending=s.ui.prepare(s.draft);await tick();
 s.nodes.get('#trash-reuse-cancel').onclick();assert.equal(await pending,false);assert.equal(JSON.stringify(s.draft),before);
}
{
 const s=setup(),pending=s.ui.prepare(s.draft);await tick();assert.ok(s.html.includes('permanently deleted'));
 s.nodes.get('#trash-reuse-confirm').onclick();assert.equal(await pending,true);
 assert.equal(s.draft.title,'Current');assert.equal(s.draft.trash_sources[0].signature,'snapshot');assert.equal(s.calls.length,1);
}
{
 const s=setup(true),pending=s.ui.prepare(s.draft);await tick();s.nodes.get('#trash-reuse-confirm').onclick();await tick();
 assert.ok(s.html.includes('data-trash-mode'));s.nodes.get('#trash-fields-apply').onclick();assert.equal(await pending,true);
 assert.equal(s.draft.title,'Current');assert.deepEqual(s.draft.tag,[{id:'b',name:'B'}]);assert.equal(s.calls.length,1);
}
{
 const s=setup(),pending=s.ui.prepare(s.draft,'',()=>false);assert.equal(await pending,false);assert.equal(s.nodes.size,0);
}
{
 const s=setup();assert.equal(await s.ui.attach('https://example.org/trashed','target',[],()=>false),null);assert.equal(s.calls.length,1);
}
console.log('Trash source UI passed: cancel, explicit permanent-delete consent, deferred save, per-field overwrite and stale navigation.');
