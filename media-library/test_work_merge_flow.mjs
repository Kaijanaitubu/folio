import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync('static/app.js','utf8');
for(const language of ['en','ja'])for(const scenario of ['ok','dirty','cancel','stale','no-links']){
 const calls=[],notices=[];
 const draft={id:'a',title:'Source',links:scenario==='no-links'?[]:[{url:'https://example.com/a'}]};
 const c={lang:language,draft,baseline:JSON.stringify(draft),routeVersion:1,t:k=>k,toast:x=>notices.push(x),markLibraryDirty:()=>calls.push('dirty'),nav:x=>calls.push(x),confirm:async()=>scenario!=='cancel',nhentaiUI:{chooseMatch:async(d,items,batch,opts)=>{assert.equal(opts.exclude,'a');assert.equal(opts.existing,true);assert.equal(items.length,1);return {action:'attach',target:'b'}}},api:async(path,method,body)=>{calls.push(path);if(path==='works?limit=40')return {items:[{id:'a'},{id:'b'}]};if(path.endsWith('merge-preview')){if(scenario==='stale')c.routeVersion++;return {source:{title:'Source'},target:{title:'Target'},links:[{}],signature:'guard'}}assert.equal(body.signature,'guard');return {id:'b'}}};
 if(scenario==='dirty')draft.title='Edited';
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('async function mergeSavedDraft(')),c);await c.mergeSavedDraft('a');
 if(scenario==='ok'){assert(calls.includes('works/a/merge-links'));assert.equal(c.draft,null);assert(calls.includes('/work/b'))}else{assert(!calls.includes('works/a/merge-links'));assert.equal(c.draft,draft)}
 if(scenario==='dirty'||scenario==='no-links')assert.equal(calls.length,0);
}
assert(!source.includes('openWorkMerge'));
assert(source.includes("if(id){await mergeSavedDraft(id);return}"));
console.log('Saved-entry merge flow: EN/JA, confirmation, unsaved edits, cancellation, stale responses, missing links and detail button removal passed.');
