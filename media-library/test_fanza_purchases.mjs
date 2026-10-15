import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fanzaPurchasesBookmarklet,fanzaPurchaseTools} from './static/fanza-purchases.js';

async function run(scenario,language){
 let count=2,clock=0,blob=null,downloads=0,scrolled=false,panel;
 const alerts=[],confirmations=[];const kind=scenario.startsWith('cg')?'cg':'comics';
 let selected=scenario==='unsupported-filter'?'voice':kind;
 const pane={scrollHeight:1000,clientHeight:400,isConnected:true,get innerText(){return scenario.includes('partial')?'合計: 4作品':'合計: 3作品'},contains:()=>true,scrollTo(){count=3;scrolled=true;if(scenario==='filter-change')selected='cg';if(scenario==='cancel-during-scroll')panel.children[1].onclick()}};
 const anchors=()=>Array.from({length:count},(_,i)=>({parentElement:pane,href:scenario==='foreign-url'?'https://example.com/dc/-/mylibrary/detail/=/product_id=d_1/':'https://www.dmm.co.jp/dc/-/mylibrary/detail/=/product_id=d_'+(i+1)+'/',querySelector:s=>({textContent:s.includes('Genre')?(scenario==='mixed'?'ボイス':scenario==='cg-mixed'?'コミック':scenario==='cg-unknown'?'':kind==='cg'?'CG':'コミック'):'Title <'+i+'>'})}));
 class TestURL extends URL{static createObjectURL(b){blob=b;return 'blob:test'}static revokeObjectURL(){}}
 const doc={querySelectorAll:anchors,getElementById:id=>id==='genre_book'?{checked:selected==='comics'}:id==='genre_cg'?{checked:selected==='cg'}:null,createElement:()=>({style:{},children:[],append(...nodes){this.children.push(...nodes)},remove(){},click(){downloads++}}),body:{append(node){if(node.id==='folio-purchase-progress')panel=node}}};
 Object.defineProperty(doc,'cookie',{get(){throw Error('Credentials must not be read')}});
 const context={location:{protocol:'https:',hostname:scenario==='wrong-site'?'example.com':'www.dmm.co.jp',pathname:scenario==='wrong-path'?'/dc/doujin/':'/dc/-/mylibrary/',origin:'https://www.dmm.co.jp',href:'https://www.dmm.co.jp/dc/-/mylibrary/'},document:doc,getComputedStyle:n=>({overflowY:n===pane?'auto':'visible'}),URL:TestURL,Blob,TextEncoder,Date:class extends Date{static now(){clock+=1000;return clock}},setTimeout:fn=>{fn();return 1},confirm:message=>{confirmations.push(message);return !scenario.includes('confirm-cancel')},alert:m=>alerts.push(m)};
 vm.createContext(context);await vm.runInContext(fanzaPurchasesBookmarklet(language).slice('javascript:'.length).replace(';void(0);',''),context);
 return {downloads,alerts,confirmations,scrolled,html:blob?await blob.text():null};
}
for(const language of ['en','ja']){
 for(const scenario of ['complete','cg-complete','confirm-cancel','cg-confirm-cancel','mixed','cg-mixed','cg-unknown','partial','cg-partial','wrong-site','wrong-path','foreign-url','unsupported-filter','filter-change','cancel-during-scroll']){
  const result=await run(scenario,language);
  if(scenario.endsWith('complete')){
   assert.equal(result.downloads,1,scenario);assert.equal((result.html.match(/<DT>/g)||[]).length,3);assert(result.html.includes('Title &lt;0&gt;'));assert(!/cookie|password|purchase_date|account_id/i.test(result.html));assert(result.scrolled);
   assert.equal(result.confirmations.length,1);assert(result.html.includes(scenario.startsWith('cg')?'FANZA purchased CG':'FANZA purchased comics'));
  }else{assert.equal(result.downloads,0,scenario);if(!scenario.includes('cancel'))assert(result.alerts.length>0,scenario)}
 }
 const instructions=fanzaPurchaseTools(language);assert(instructions.includes('CG'));assert(instructions.includes(language==='ja'?'それぞれ書き出し':'two formats separately'));
}
console.log('FANZA exporter: EN/JA comics + CG, incremental completion, confirmation/cancellation, escaping, mixed/unknown media, counts, filter changes, credential isolation and URL boundaries passed (30 scenarios).');
