import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const load=async file=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('static/'+file,import.meta.url),'utf8')).toString('base64'));
const {createMarkUI,markEn,markJa}=await load('mark-ui.js');
const {searchHelpHTML}=await load('search-help.js');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const config={marks:[['○','●'],['△','▲'],['□','■'],['♡','♥'],['☆','★']].map(([off,on],i)=>({number:i+1,label:i===3?'<Favorite>':'',off,on})),dimensions:[{number:7,name:'Quality <&>',maximum:2}],categories:{manga:'漫画'}};
for(const lang of ['en','ja']){
 const text={...(lang==='ja'?markJa:markEn),bought:lang==='ja'?'購入済み':'Purchased'},calls=[],saved=[],errors=[];
 let current={id:'fixture',marks:[1]},response;
 const root={isConnected:true,buttons:[],details:{open:false},querySelectorAll(){return this.buttons},querySelector(){return this.details},set innerHTML(html){this.html=html;this.buttons=[...html.matchAll(/data-work-mark="(\d+)"/g)].map(m=>({dataset:{workMark:m[1]},disabled:false}))}};
 const ui=createMarkUI({t:k=>text[k]||k,esc,config:()=>config,api:async(...args)=>{calls.push(args);return typeof response==='function'?response(...args):response},onSaved:w=>saved.push(w),onError:e=>errors.push(e)});
 root.innerHTML=ui.buttons(current);ui.bind(root,()=>current,w=>current=w);
 await root.buttons[3].onclick();assert.deepEqual(current.marks,[1,4]);assert.equal(calls.length,0);assert.ok(root.html.includes('&lt;Favorite&gt;'));
 response={...current,marks:[1,2,4]};root.innerHTML=ui.detail(current);ui.bind(root,()=>current,w=>current=w,true);
 await root.buttons[1].onclick();assert.deepEqual(calls[0],['works/fixture/marks','POST',{number:2,value:true,expected:[1,4]}]);assert.deepEqual(current.marks,[1,2,4]);assert.equal(saved.length,1);assert.equal(root.details.open,true);
 // Rejected stale writes reload the current work without retrying a destructive overwrite.
 response=(path)=>{if(path.endsWith('/marks'))throw Error('Stale');return {...current,marks:[5]}};
 await root.buttons[2].onclick();assert.deepEqual(current.marks,[5]);assert.equal(errors.at(-1),'Stale');assert.equal(calls.length,3);
 // An old page cannot apply a late response to the next page.
 let release;response=()=>new Promise(r=>release=r);const pending=root.buttons[0].onclick();root.isConnected=false;release({...current,marks:[1,5]});await pending;
 assert.deepEqual(current.marks,[5]);assert.equal(saved.length,2);
 const help=searchHelpHTML(config,lang,esc);assert.ok(help.includes('rating7:&gt;=2'));assert.ok(help.includes('-rating7:&gt;=1'));assert.ok(!help.includes('rating1:'));assert.ok(help.includes('Quality &lt;&amp;&gt;'));assert.ok(help.includes('&lt;Favorite&gt;'));assert.ok(help.includes('mark:=124'));
 const noRating=searchHelpHTML({...config,dimensions:[]},lang,esc);assert.ok(!noRating.includes('rating1:'));assert.ok(noRating.includes('pages:&gt;=20'));
}
console.log('Marks UI and search help passed: EN/JA, draft vs immediate saves, stale/late response protection, safe dynamic labels and rating examples.');
