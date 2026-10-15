import assert from 'node:assert/strict';
import {importScreen,importLocation} from './static/import-screen.js';
const render=(view,service,lang)=>importScreen({view,service,lang,esc:s=>String(s).replaceAll('<','&lt;'),icon:n=>'<svg>'+n+'</svg>',t:k=>k,sourceTools:()=>'<div id="setup-only"></div>',pawTools:()=>'<div id="paw-favorites-code"></div>',fanzaTools:()=>'<div id="fanza-purchases-code"></div>',modes:()=>'<select id="bookmark-tag-mode"></select>',pawOption:()=>'<input id="bookmark-original-links">'});
for(const lang of ['en','ja']){
 const home=render('home','nhentai',lang);assert.equal((home.match(/class="import-card"/g)||[]).length,4);assert.ok(!home.includes('bookmark-file'));assert.ok(!home.includes('nhentai-import'));assert.ok(!home.includes('setup-only'));
 const history=render('history','nhentai',lang);assert.ok(history.includes('id="jobs"'));assert.ok(!history.includes('bookmark-file'));
 const settings=render('settings','nhentai',lang);assert.ok(settings.includes('setup-only'));assert.ok(!settings.includes('bookmark-file'));
 const links=render('link','nhentai',lang);assert.ok(links.includes('source-open-form'));assert.ok(!links.includes('setup-only'));
 const kemono=render('favorites','kemono',lang);assert.ok(kemono.includes('.json,application/json'));assert.ok(!kemono.includes('paw-favorites-code'));assert.ok(kemono.includes('bookmark-original-links'));assert.ok(!kemono.includes('id="nhentai-import"'));
 const paw=render('favorites','pawchive',lang);assert.ok(paw.includes('paw-favorites-code'));assert.ok(paw.includes('.html,.htm'));assert.ok(!paw.includes('fanza-purchases-code'));
 const nh=render('favorites','nhentai',lang);assert.ok(nh.includes('id="nhentai-import"'));assert.ok(!nh.includes('bookmark-file'));
 const fanza=render('purchases','nhentai',lang);assert.ok(fanza.includes('fanza-purchases-code'));assert.ok(!fanza.includes('bookmark-original-links'));assert.ok(fanza.includes(lang==='ja'?'準備中':'not supported yet'));
}
assert.deepEqual(importLocation(new URLSearchParams('view=evil&service=evil')),{view:'home',service:'nhentai',kind:'nhentai'});
assert.equal(importLocation(new URLSearchParams('view=favorites&service=kemono')).kind,'kemono');
assert.equal(importLocation(new URLSearchParams('view=purchases')).kind,'fanza');
console.log('Import screen checks passed: EN/JA, four purposes, scoped inputs, services, setup/history and invalid routes.');
