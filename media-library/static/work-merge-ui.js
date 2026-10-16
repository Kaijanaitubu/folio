import {applyImported,metadataKinds,sameMetadataSet} from './import-policy.js';
const scalars=['title','cover','category','language','pages'];
export function metadataPatch(before,after){
 return Object.fromEntries([...scalars,...metadataKinds].filter(k=>metadataKinds.includes(k)?!sameMetadataSet(before[k],after[k]):before[k]!==after[k]).map(k=>[k,after[k]]));
}
export function createWorkMergeUI({api,modal,closeModal,dialog,$,$$,esc,t,lang,trashSourceUI}){
 const s=(en,ja)=>lang()==='ja'?ja:en;
 async function review(p,current=()=>true,saved=false){
  const source=p.source,target=p.target;
  const present=v=>v!==''&&v!=null;
  const conflicts=scalars.filter(k=>present(source[k])&&present(target[k])&&source[k]!==target[k]);
  const multi=metadataKinds.filter(k=>source[k]?.length&&target[k]?.length&&!sameMetadataSet(source[k],target[k]));
  const fills=[...scalars.filter(k=>present(source[k])&&!present(target[k])),...metadataKinds.filter(k=>source[k]?.length&&!target[k]?.length)];
  const names=items=>items.map(e=>(e.display_name||e.name||e)+(e.gender==='female'?' ♀':e.gender==='male'?' ♂':'')).join(', ');
  return new Promise(resolve=>{
   modal(`<h2>${esc(s('Review merge','統合内容の確認'))}</h2><p>${esc(source.title)} → ${esc(target.title)}</p><p>${esc(s('All new links are added as secondary links. The destination primary link, ratings, review and marks are preserved.','新しいリンクをすべて副リンクに追加します。統合先の主リンク・評価・レビュー・マークは維持します。'))}</p><details><summary>${esc(s('Links to add','追加するリンク'))}: ${p.links.length}</summary>${p.links.map(l=>`<small class="shared-link">${esc(l.label||'')} ${esc(l.url)}</small>`).join('')}</details>${p.notice?`<p class="notice">${esc(p.notice)}</p>`:''}${saved?`<p class="notice">${esc(s('The source entry will move to Trash after a successful merge.','統合成功時に、統合元の作品をゴミ箱へ移動します。'))}</p>`:''}<label class="check-label"><input type="checkbox" id="merge-metadata"><span>${esc(s('Include metadata (default: links only)','メタデータも反映する（初期状態：リンクのみ）'))}</span></label><div id="merge-fields" class="stack" hidden>${fills.length?`<p>${esc(s('Empty fields filled automatically','空欄は自動で補完'))}: ${fills.map(k=>`<small class="shared-link">${esc(t(k))}: ${esc(metadataKinds.includes(k)?names(source[k]):source[k])}</small>`).join('')}</p>`:''}${conflicts.map(k=>`<label class="check-label"><input type="checkbox" data-merge-scalar="${k}"><span>${esc(t(k))} — ${esc(s('Overwrite','上書き'))}<br><small>${esc(target[k])} → ${esc(source[k])}</small></span></label>`).join('')}${multi.map(k=>`<div class="import-field"><label><span>${esc(t(k))}</span><select data-merge-mode="${k}">${['merge','overwrite','keep'].map(m=>`<option value="${m}">${esc(t('import_'+m))}</option>`).join('')}</select></label><small>${esc(t('existingValues'))}: ${esc(names(target[k]))}</small><small>${esc(t('incomingValues'))}: ${esc(names(source[k]))}</small></div>`).join('')}<small>${esc(s('Identical values and empty incoming fields are left unchanged.','一致する項目と取得データが空の項目は変更しません。'))}</small></div><div class="actions"><button class="btn" id="merge-cancel">${esc(t('cancel'))}</button><button class="btn primary" id="merge-apply">${esc(s('Merge','統合'))}</button></div>`);
   let done=false;
   const finish=value=>{if(done)return;done=true;closeModal();resolve(current()?value:null)};
   $('#merge-metadata').onchange=()=>{$('#merge-fields').hidden=!$('#merge-metadata').checked};
   $('#merge-cancel').onclick=()=>finish(null);
   $('#merge-apply').onclick=()=>finish($('#merge-metadata').checked?metadataPatch(target,applyImported(target,source,$$('[data-merge-scalar]:checked').map(e=>e.dataset.mergeScalar),Object.fromEntries($$('[data-merge-mode]').map(e=>[e.dataset.mergeMode,e.value])))):{});
   dialog.oncancel=()=>finish(null);
  });
 }
 async function attach(source,target,current=()=>true){
  const draft=structuredClone(source);
  const p=await api('draft-merge/preview','POST',{draft,target});if(!current())return null;
  let patch=await review(p,current);if(patch===null||!current())return null;
  let consents=[];
  if(p.trash_conflicts?.length){
   const combined={...structuredClone(p.target),...patch,links:[...p.target.links,...p.links.map(l=>({...l,is_primary:false}))]};
   if(!await trashSourceUI.prepare(combined,target,current))return null;
   patch=metadataPatch(p.target,combined);consents=combined.trash_sources||[];
  }
  if(!current())return null;
  return api('draft-merge/apply','POST',{draft,target,signature:p.signature,metadata_patch:patch,trash_sources:consents});
 }
 return {review,attach};
}
