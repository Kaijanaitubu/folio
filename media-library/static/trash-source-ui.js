import {applyImported,metadataKinds,sameMetadataSet} from './import-policy.js';
export function createTrashSourceUI({api,modal,closeModal,dialog,$,$$,esc,t,lang}){
 const s=(en,ja)=>lang()==='ja'?ja:en;
 async function fields(work,incoming){
  const scalar=['title','cover','category','language','pages'].filter(k=>work[k]!==''&&work[k]!=null&&incoming[k]!==''&&incoming[k]!=null&&work[k]!==incoming[k]);
  const multi=metadataKinds.filter(k=>work[k]?.length&&incoming[k]?.length&&!sameMetadataSet(work[k],incoming[k]));
  if(!scalar.length&&!multi.length)return applyImported(work,incoming);
  const names=items=>items.map(e=>e.display_name||e.name).join(', ');
  return new Promise(resolve=>{
   modal(`<h2>${esc(t('replaceTitle'))}</h2><p>${esc(t('replaceText'))}</p><div class="stack">${scalar.map(k=>`<label class="check-label"><input type="checkbox" data-trash-scalar="${k}"><span>${esc(t(k))}<br><small>${esc(work[k])} → ${esc(incoming[k])}</small></span></label>`).join('')}${multi.map(k=>`<div class="import-field"><label><span>${esc(t(k))}</span><select data-trash-mode="${k}">${['merge','overwrite','keep'].map(m=>`<option value="${m}">${esc(t('import_'+m))}</option>`).join('')}</select></label><small>${esc(t('existingValues'))}: ${esc(names(work[k]))}</small><small>${esc(t('incomingValues'))}: ${esc(names(incoming[k]))}</small></div>`).join('')}</div><div class="actions"><button id="trash-fields-cancel" class="btn">${esc(t('cancel'))}</button><button id="trash-fields-apply" class="btn primary">${esc(t('apply'))}</button></div>`);
   const finish=v=>{closeModal();resolve(v)};
   $('#trash-fields-cancel').onclick=()=>finish(null);
   $('#trash-fields-apply').onclick=()=>finish(applyImported(work,incoming,$$('[data-trash-scalar]:checked').map(e=>e.dataset.trashScalar),Object.fromEntries($$('[data-trash-mode]').map(e=>[e.dataset.trashMode,e.value]))));
   dialog.oncancel=()=>resolve(null);
  });
 }
 async function prepare(work,id='',current=()=>true,only=null){
  if(work.trash_sources)work.trash_sources=work.trash_sources.filter(c=>work.links.some(l=>l.url===c.url));
  for(const link of [...work.links].filter(l=>l.url&&(!only||l===only))){
   if(work.trash_sources?.some(c=>c.url===link.url&&c.primary===!!link.is_primary))continue;
   const p=await api('trash-source/preview','POST',{url:link.url,exclude:id||''});if(!current())return false;
   if(!p.works.length)continue;
   const secondary=!link.is_primary;
   const accepted=await new Promise(resolve=>{
    modal(`<h2>${esc(s('This link is in Trash','同じリンクの作品がゴミ箱にあります'))}</h2><p>${esc(secondary?s('Merge selected metadata and this link into the current entry?','このリンクと選択したメタデータを現在の作品へ統合しますか？'):s('Delete the trashed entries and register this link again?','ゴミ箱の作品を削除して、このリンクを新たに登録しますか？'))}</p><div class="stack">${p.works.map(w=>`<div><b>${esc(w.title)}</b>${w.links.map(l=>`<small class="shared-link">${esc(l.url)}</small>`).join('')}</div>`).join('')}</div><p>${esc(s('The listed Trash entries and their other links will be permanently deleted only when you save successfully. Ratings, marks and reviews are not transferred. Cancel editing to keep them.','保存成功時に、表示したゴミ箱の作品とそのほかのリンクを完全削除します。評価・マーク・レビューは引き継ぎません。編集をキャンセルすれば削除しません。'))}</p><div class="actions"><button id="trash-reuse-cancel" class="btn">${esc(t('cancel'))}</button><button id="trash-reuse-confirm" class="btn primary">${esc(s('Yes — continue','はい・続行'))}</button></div>`);
    const finish=v=>{closeModal();resolve(v)};$('#trash-reuse-cancel').onclick=()=>finish(false);$('#trash-reuse-confirm').onclick=()=>finish(true);dialog.oncancel=()=>resolve(false);
   });
   if(!accepted||!current())return false;
   let updated={...work};
   if(secondary)for(const incoming of p.works){updated=await fields(updated,incoming);if(!updated||!current())return false;}
   Object.assign(work,updated);work.trash_sources=(work.trash_sources||[]).filter(c=>c.url!==link.url);work.trash_sources.push({url:link.url,signature:p.signature,primary:!!link.is_primary});
  }
  return current();
 }
 async function attach(url,target,titles,current=()=>true,originals=[]){
  const p=await api('trash-source/preview','POST',{url});
  if(!current())return null;
  if(!p.works.length)return api('source-attach','POST',{url,target,source_titles:titles,original_links:originals});
  const work=await api('works/'+target);if(!current())return null;work.links.push({url,label:'',is_primary:false});for(const original of originals)work.links.push({url:original.url,label:original.label,is_primary:false});
  if(!await prepare(work,target,current))return null;
  return api('works/'+target,'PUT',work);
 }
 return {prepare,attach};
}
