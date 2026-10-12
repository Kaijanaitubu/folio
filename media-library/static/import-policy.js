export const metadataKinds=['author','circle','tag','series','character'];
const scalarKinds=['title','cover','category','language','pages'];
export function sameMetadataItem(a,b){
 return a.id&&b.id?a.id===b.id:a.name===b.name&&(a.gender||'neutral')===(b.gender||'neutral');
}
export function sameMetadataSet(a=[],b=[]){
 const unique=items=>items.filter((item,i)=>!items.slice(0,i).some(old=>sameMetadataItem(old,item)));
 const left=unique(a),right=unique(b);
 return left.length===right.length&&left.every(item=>right.some(other=>sameMetadataItem(item,other)));
}
export function hasImportedChanges(draft,incoming){
 return scalarKinds.some(key=>incoming[key]!==''&&incoming[key]!=null&&draft[key]!==incoming[key])||
  metadataKinds.some(key=>incoming[key]?.length&&!sameMetadataSet(draft[key],incoming[key]));
}
export function mergeMetadata(existing,incoming,mode='merge'){
 if(!incoming?.length||mode==='keep'&&existing.length||sameMetadataSet(existing,incoming))return existing;
 const result=mode==='overwrite'||!existing.length?[]:[...existing];
 for(const item of incoming)if(!result.some(old=>sameMetadataItem(old,item)))result.push(item);
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
