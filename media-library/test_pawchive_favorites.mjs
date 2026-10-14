import assert from 'node:assert/strict';
import vm from 'node:vm';
import {favoritesBookmarklet} from './static/pawchive-favorites.js';
import {mergeOriginals,originalKey} from './static/pawchive-sources.js';
import {createPawchiveUI} from './static/pawchive-ui.js';

async function run(rows,options={}){
 const calls=[],alerts=[],blobs=[],anchors=[],confirmations=[];
 const encoded=new TextEncoder().encode(JSON.stringify(rows));let supplied=false;
 const response={status:options.status||200,ok:!(options.status>=400),headers:{get:()=>options.mime||'application/json'},body:{getReader:()=>({read:async()=>supplied?{done:true}:(supplied=true,{done:false,value:encoded}),releaseLock(){}})}};
 const context={location:{protocol:'https:',hostname:options.host||'pawchive.pw'},fetch:async(...args)=>{calls.push(args);return response},AbortController,TextEncoder,TextDecoder,Blob,Date,alert:message=>alerts.push(message),confirm:message=>{confirmations.push(message);return options.confirm!==false},setTimeout:()=>0,clearTimeout(){},URL:{createObjectURL:blob=>{blobs.push(blob);return 'blob:synthetic'},revokeObjectURL(){}},document:{body:{append(){}},createElement:()=>{const anchor={click(){anchors.push(this)},remove(){}};return anchor}}};
 await vm.runInNewContext(favoritesBookmarklet(options.lang).slice(11).replace(/;void\(0\);$/,''),context);
 return {calls,alerts,confirmations,anchors,html:blobs.length?await blobs[0].text():null};
}
const rows=[{service:'fanbox',user:'12',id:'34',cookie:'credential-fixture',email:'private-fixture',title:'<script>fixture</script>'},{service:'fanbox',user:'12',id:'34'},{service:'patreon',user:56,id:78},{service:'discord',user:'1',id:'2'}];
for(const lang of ['en','ja']){
 const result=await run(rows,{lang});
 assert.equal(result.calls.length,1);assert.equal(result.calls[0][0],'/api/v1/account/favorites?type=post');
 assert.equal(result.calls[0][1].method,'GET');assert.equal(result.calls[0][1].credentials,'same-origin');assert.equal(result.calls[0][1].redirect,'error');
 assert.equal(result.anchors.length,1);assert.ok(result.anchors[0].download.endsWith('.html'));
 assert.equal((result.html.match(/<DT><A /g)||[]).length,2);
 assert.ok(result.html.includes('https://pawchive.pw/fanbox/user/12/post/34'));
 assert.ok(!result.html.includes('credential-fixture'));assert.ok(!result.html.includes('private-fixture'));assert.ok(!result.html.includes('<script>'));
 assert.ok(result.confirmations[0].includes(lang==='ja'?'未対応：1':'Unsupported: 1'));
}
for(const [data,options] of [[rows,{confirm:false}],[rows,{status:401}],[rows,{status:503}],[rows,{mime:'text/html'}],[rows,{host:'evil.test'}],[{},{}],[[{service:'fanbox',user:'bad',id:'34'}],{}],[[],{}],[[{service:'discord',user:'1',id:'2'}],{}]]){
 const result=await run(data,options);assert.equal(result.html,null);assert.equal(result.anchors.length,0);
 if(options.confirm!==false)assert.ok(result.alerts.length);
}
const large=await run(Array.from({length:2505},(_,i)=>({service:'fanbox',user:'12',id:String(i+1)})));
assert.equal((large.html.match(/<DT><A /g)||[]).length,2505);
assert.equal(originalKey('https://artist.fanbox.cc/posts/34?x=1'),originalKey('https://www.fanbox.cc/@artist/posts/34'));
const existing=[{url:'https://www.patreon.com/posts/name-78',label:'Custom',is_primary:true}];
const merged=mergeOriginals(existing,[{url:'https://www.patreon.com/posts/78',label:'Patreon'},{url:'https://artist.fanbox.cc/posts/34',label:'FANBOX'}]);
assert.equal(merged.length,2);assert.equal(merged[0],existing[0]);assert.equal(merged[1].is_primary,false);assert.equal(existing.length,1);

for(const lang of ['en','ja']){
 const nodes={},modals=[],ui=createPawchiveUI({$:selector=>nodes[selector]??={isConnected:true},$$:()=>[{dataset:{pawOriginal:'0'}}],modal:html=>modals.push(html),closeModal(){},dialog:{},esc:String,toast(){},lang:()=>lang});
 const incoming={original_links:[{url:'https://artist.fanbox.cc/posts/34',label:'FANBOX',matches:[]}]};
 const selected=ui.chooseOriginals(incoming,{links:[]},()=>true);nodes['#paw-original-continue'].onclick();
 assert.equal((await selected).length,1);assert.ok(modals[0].includes(lang==='ja'?'閲覧可否':'availability'));
 const cancelled=ui.chooseOriginals(incoming,{links:[]},()=>true);nodes['#paw-original-cancel'].onclick();assert.equal(await cancelled,null);
 const stale=ui.chooseOriginals(incoming,{links:[]},()=>false);nodes['#paw-original-continue'].onclick();assert.equal(await stale,null);
 assert.deepEqual(await ui.chooseOriginals(incoming,{links:[{url:'https://www.fanbox.cc/@artist/posts/34'}]},()=>true),[]);
 assert.ok(ui.tools().includes('Pawchive Favorites'));
}
console.log('Pawchive Favorites passed: EN/JA export, 2505 IDs, no credentials, auth/shape/cancel failures, and original-link selection.');
