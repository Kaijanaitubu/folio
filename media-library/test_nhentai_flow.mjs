// Import-job status translations must not rename unrelated work-editor fields.
import assert from 'node:assert/strict';
import {en,ja} from './static/i18n.js';
import {featureEn,featureJa} from './static/feature-text.js';
import {nhentaiEn,nhentaiJa} from './static/nhentai-text.js';
const intentional=new Set(['imports','importsHint','importHint','sourceTools','sourcePaste','sourceToolsHint','sourceMatchesHint','sourceRelatedHint']);
for(const [base,features,addition] of [[en,featureEn,nhentaiEn],[ja,featureJa,nhentaiJa]]){
 const existing={...base,...features};
 for(const key of Object.keys(addition))if(key in existing)assert.ok(intentional.has(key),`Unexpected translation collision: ${key}`);
 const result={...existing,...addition};
 for(const field of ['title','cover','author','tag','review','language','pages','save','delete'])assert.equal(result[field],existing[field],`Work field renamed: ${field}`);
 assert.ok(result.awaiting_review);assert.ok(result.matchAll);
}
console.log('nhentai English/Japanese integration preserves work-field translations');
