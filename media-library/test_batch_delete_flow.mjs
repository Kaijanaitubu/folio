import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const load=async file=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('static/'+file,import.meta.url),'utf8')).toString('base64'));
const {createBatchDelete}=await load('batch-delete.js');
const {featureEn,featureJa}=await load('feature-text.js');
for(const text of [featureEn,featureJa]){
 let ids=[],accepted=false,release;const calls=[],confirmations=[],saved=[],busy=[];
 const ui=createBatchDelete({getIds:()=>ids,getContext:()=>'/library?q=original',t:k=>text[k]||k,confirm:async(...args)=>{confirmations.push(args);return release?new Promise(r=>release=r):accepted},api:async(...args)=>{calls.push(args);if(accepted==='error')throw Error('Rejected');return {deleted:args[2].ids.length}},onDeleted:async(...args)=>saved.push(args),onBusy:value=>busy.push(value)});
 await ui.run();assert.equal(confirmations.length,0);
 ids=['a','b','a'];await ui.run();assert.equal(calls.length,0);assert.ok(confirmations[0][1].includes('2'));assert.ok(confirmations[0][1].includes(text.batchDeleteHint));assert.equal(ui.busy,false);
 accepted=true;release=true;const pending=ui.run();assert.equal(ui.busy,true);ids=['c'];await ui.run();assert.equal(confirmations.length,2);release(true);await pending;assert.deepEqual(calls[0],['batch/trash','POST',{ids:['a','b']}]);assert.deepEqual(saved[0],[{deleted:2},'/library?q=original']);assert.equal(ui.busy,false);
 release=null;accepted='error';await assert.rejects(ui.run(),/Rejected/);assert.equal(saved.length,1);assert.equal(ui.busy,false);assert.deepEqual(ids,['c']);assert.equal(busy.at(-1),false);
}
console.log('Batch deletion passed: EN/JA count, cancel, frozen selection, repeat-click guard, success and retained selection on failure.');

