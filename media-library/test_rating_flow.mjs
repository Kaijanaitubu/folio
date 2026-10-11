// Exercise the actual editor event handlers with DOM stubs; not a browser test.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const app=readFileSync(new URL('static/app.js',import.meta.url),'utf8');
const code=app.slice(app.indexOf('function dimensionEditor('),app.indexOf('\nlet bookmarkItems='));
assert.ok(code.includes('function dimensionEditor'));
const {en,ja}=await import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('static/i18n.js',import.meta.url),'utf8')).toString('base64'));
const preview={old_maximum:5,maximum:3,rows:[1,2,3,4,5].map((old,i)=>({old,new:[1,1,2,2,3][i],count:1})),rated:5,changed:4,signature:'reviewed'};
function setup(language='en',existing=true){
 const nodes={},calls=[];let html='',saved=0,closed=0;
 const context={routeVersion:1,config:{symbols:['Star']},symbols:{Star:['★','☆']},dialog:{open:true},
  t:key=>(language==='ja'?ja:en)[key],esc:x=>String(x??''),btn:()=>'',
  modal:value=>{html=value},closeModal:()=>{closed++;context.dialog.open=false;Object.values(nodes).forEach(n=>n.isConnected=false)},
  $:key=>nodes[key]??=( {value:'',checked:false,isConnected:true,innerHTML:'',textContent:'',disabled:false,scrollIntoView(){}} ),
  api:async(path,method,data)=>{calls.push({path,method,data});if(path.endsWith('/preview'))return structuredClone(preview);saved++;return {id:'d'}},
  markLibraryDirty:()=>{},ratingPage:()=>{},error:(node,e)=>node.innerHTML=e.message};
 vm.createContext(context);vm.runInContext(code,context);
 context.dimensionEditor(existing?{id:'d',number:1,name:'Quality',maximum:5,symbol:'Star'}:undefined);
 nodes['#dim-name']??={};nodes['#dim-name'].value='Quality';
 nodes['#dim-symbol']??={};nodes['#dim-symbol'].value='Star';
 nodes['#dim-gallery']??={};nodes['#dim-gallery'].checked=true;
 nodes['#dim-max'].value=existing?'5':'3';
 const submit=()=>nodes['#dimension-form'].onsubmit({preventDefault(){}});
 const scale=value=>{nodes['#dim-max'].value=String(value);nodes['#dim-max'].oninput()};
 return {context,nodes,calls,submit,scale,get html(){return html},get saved(){return saved},get closed(){return closed}};
}
for(const language of ['en','ja']){
 const s=setup(language);s.scale(3);await s.submit();
 assert.equal(s.saved,0);assert.equal(s.calls[0].path,'dimensions/d/preview');
 assert.ok(s.nodes['#dimension-preview'].innerHTML.includes('5/5'));
 assert.ok(s.nodes['#dimension-preview'].innerHTML.includes('3/3'));
 assert.equal(s.nodes['#dim-save'].textContent,(language==='ja'?ja:en).confirmConversion);
 await s.submit();assert.equal(s.saved,1);assert.equal(s.closed,1);
 assert.equal(s.calls[1].data.conversion_signature,'reviewed');
}
const cancel=setup();cancel.scale(3);await cancel.submit();cancel.nodes['#dim-cancel'].onclick();assert.equal(cancel.saved,0);
const changed=setup();changed.scale(3);await changed.submit();changed.scale(4);assert.equal(changed.nodes['#dimension-preview'].innerHTML,'');await changed.submit();assert.equal(changed.calls.length,2);assert.ok(changed.calls.every(c=>c.path.endsWith('/preview')));
const unchanged=setup();await unchanged.submit();assert.equal(unchanged.saved,1);assert.equal(unchanged.calls.length,1);assert.equal(unchanged.calls[0].data.conversion_signature,undefined);
const fresh=setup('en',false);await fresh.submit();assert.equal(fresh.saved,1);assert.equal(fresh.calls[0].method,'POST');
const stale=setup();stale.scale(3);await stale.submit();stale.context.api=async(path,method,data)=>{stale.calls.push({path,method,data});if(path.endsWith('/preview'))return structuredClone(preview);throw Error('Rating scores or scale changed; preview the conversion again')};await stale.submit();assert.equal(stale.closed,0);assert.equal(stale.nodes['#dimension-preview'].innerHTML,'');await stale.submit();assert.equal(stale.calls.at(-1).path,'dimensions/d/preview');
const late=setup();late.scale(3);let resolve;late.context.api=()=>new Promise(r=>resolve=r);const pending=late.submit();late.nodes['#dim-cancel'].onclick();resolve(preview);await pending;assert.equal(late.nodes['#dimension-preview'].innerHTML,'');assert.equal(late.saved,0);
console.log('Rating editor checks passed: EN/JA preview, confirm, cancel, re-preview, unchanged/new scales, stale and late responses.');
