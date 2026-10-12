export const metadataKinds=['author','circle','tag','series','character'];
export function mergeMetadata(existing,incoming,mode='merge'){
 if(!incoming?.length||mode==='keep'&&existing.length)return [...existing];
 const result=mode==='overwrite'||!existing.length?[]:[...existing];
 for(const item of incoming)if(!result.some(old=>item.id&&old.id===item.id||old.name===item.name&&(old.gender||'neutral')===(item.gender||'neutral')))result.push(item);
 return result;
}
export function applyImported(draft,incoming,replacements=[],modes={}){
 const result={...draft};
 for(const key of ['title','cover','category','language','pages']){
  if((draft[key]===''||draft[key]==null||replacements.includes(key))&&incoming[key]!==''&&incoming[key]!=null)result[key]=incoming[key];
 }
 for(const key of metadataKinds)result[key]=mergeMetadata(draft[key]||[],incoming[key]||[],modes[key]);
 return result;
}
