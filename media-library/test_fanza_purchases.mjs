import vm from 'node:vm';import assert from 'node:assert/strict';import {fanzaPurchasesBookmarklet} from './static/fanza-purchases.js';
for(const scenario of ['complete','cancel','mixed','partial','wrong-site']){
 let count=2,clock=0,blob=null,downloads=0;const alerts=[];
 const pane={scrollHeight:1000,clientHeight:400,isConnected:true,get innerText(){return scenario==='partial'?'合計: 4作品':'合計: 3作品'},contains:()=>true,scrollTo:()=>{count=3}};
 const anchors=()=>Array.from({length:count},(_,i)=>({parentElement:pane,href:'https://www.dmm.co.jp/dc/-/mylibrary/detail/=/product_id=d_'+(i+1)+'/',querySelector:s=>({textContent:s.includes('Genre')?(scenario==='mixed'?'ボイス':'コミック'):'Title <'+i+'>'})}));
 class TestURL extends URL{static createObjectURL(b){blob=b;return 'blob:test'}static revokeObjectURL(){}}
 const context={location:{protocol:'https:',hostname:scenario==='wrong-site'?'example.com':'www.dmm.co.jp',pathname:'/dc/-/mylibrary/',origin:'https://www.dmm.co.jp',href:'https://www.dmm.co.jp/dc/-/mylibrary/'},document:{querySelectorAll:anchors,getElementById:id=>id==='genre_book'?{checked:true}:null,createElement:()=>({style:{},append(){},remove(){},click(){downloads++}}),body:{append(){}}},getComputedStyle:n=>({overflowY:n===pane?'auto':'visible'}),URL:TestURL,Blob,TextEncoder,Date:class extends Date{static now(){clock+=1000;return clock}},setTimeout:fn=>{fn();return 1},confirm:()=>scenario!=='cancel',alert:m=>alerts.push(m)};
 vm.createContext(context);await vm.runInContext(fanzaPurchasesBookmarklet('ja').slice('javascript:'.length).replace(';void(0);',''),context);
 if(scenario==='complete'){assert.equal(downloads,1);const html=await blob.text();assert.equal((html.match(/<DT>/g)||[]).length,3);assert(html.includes('Title &lt;0&gt;'));assert(!/cookie|password|purchase_date|account_id/i.test(html))}else{assert.equal(downloads,0);if(scenario!=='cancel')assert(alerts.length>0)}
}
console.log('FANZA purchase exporter: paginated completion, escaped titles, cancellation, mixed media, partial counts and wrong host passed.');
