import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync('static/app.js','utf8');
for(const language of ['en','ja'])for(const accepted of [true,false]){
 const nodes=new Map(),calls=[];let html='';
 const work={id:'one',title:'Example',category:'',language:'',pages:null,author:[],circle:[],series:[],character:[],tag:[{name:'Female',gender:'female'},{name:'Male',gender:'male'},{name:'None',gender:'neutral'}],ratings:{},review:'',links:[{url:'https://example.com',is_primary:true,label:'Source'}]};
 const c={lang:language,routeVersion:1,config:{dimensions:[]},librarySnapshot:null,currentWork:null,api:async(p,m)=>{calls.push([p,m]);return work},shell:(name,h)=>html=h,icon:n=>n,esc:x=>String(x??''),t:k=>k,btn:()=>'',image:()=>'',displayName:e=>e.name,metadataHref:()=>'',images:()=>{},markUI:{detail:()=>'',bind:()=>{}},$:s=>{if(!nodes.has(s))nodes.set(s,{isConnected:true});return nodes.get(s)},nav:p=>calls.push(['nav',p]),markLibraryDirty:()=>{},toast:()=>{},confirm:async()=>accepted,safely:fn=>fn,shareWork:()=>{}};
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('async function detail('),source.indexOf('\nconst dialog=')),c);await c.detail('one');
 assert(html.includes('Female ♀'));assert(html.includes('Male ♂'));assert(html.includes('>None</a>'));
 assert(html.indexOf('id="share-work"')<html.indexOf('id="detail-delete-work"'));assert(html.indexOf('id="detail-delete-work"')<html.indexOf('id="edit-work"'));
 await nodes.get('#detail-delete-work').onclick();assert.equal(calls.some(([p,m])=>p==='works/one'&&m==='DELETE'),accepted);
}
console.log('Detail actions EN/JA: gender symbols, compact action order, confirmed deletion and cancellation passed.');
