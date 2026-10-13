export const tagEn={neutral:'None',gender:'Attribute',workTag:'Tag on this work',workTagHint:'Changing the attribute replaces this work’s tag only. New tags are created when you save the work.',editSharedTag:'Edit shared tag',sharedTagTitle:'Edit shared tag',tagCollision:'Tag name or alias already exists',tagCollisionHint:'These names belong to existing tags with the same attribute. Choose an existing tag, keep separate tags, or merge shared tags.',useExistingTag:'Use existing tag',keepSeparateTags:'Keep separate tags',tagReview:'Choose tags',tagReviewHint:'More than one tag matches this name. Select the existing tag to use.',tag_review:'Tag choices needed',metadata_mergeOperation:'Metadata merge',mergePreviewHint:'All works using the source tag, including Trash, will use the target. The target name, attribute and display settings are kept. This merge can be undone in History.',mergeCount:'Affected works',mergeResult:'Merged',sharedSaved:'Shared tag saved',reviewMerge:'Review merge',historyHint:'Saved edits, batch edits, rating conversions and metadata merges can be undone for 30 days. Later conflicting changes prevent undo. Other directory edits and import jobs are not included.'};
export const tagJa={neutral:'未指定（none）',gender:'属性',workTag:'この作品のタグ',workTagHint:'属性変更はこの作品のタグだけを差し替えます。新しいタグは作品を保存した時に作成されます。',editSharedTag:'タグ自体を編集',sharedTagTitle:'共有タグを編集',tagCollision:'タグ名・別名が既に存在します',tagCollisionHint:'同じ属性の既存タグに、この名前が登録されています。既存タグを使う・別々に残す・共有タグを統合する方法を選べます。',useExistingTag:'既存タグを使う',keepSeparateTags:'別々のタグとして保存',tagReview:'タグを選択',tagReviewHint:'この名前に一致するタグが複数あります。作品に付ける既存タグを選択してください。',tag_review:'タグの確認待ち',metadata_mergeOperation:'メタデータの統合',mergePreviewHint:'ゴミ箱を含む、統合元を使う全作品のタグが差し替わります。統合先の名前・属性・表示設定を維持します。統合は操作履歴から取り消せます。',mergeCount:'影響する作品数',mergeResult:'統合しました',sharedSaved:'共有タグを保存しました',reviewMerge:'統合内容を確認',historyHint:'作品編集・一括編集・評価換算・メタデータ統合は30日間取り消せます。後から対象情報が変更された場合は取り消せません。その他の辞書編集・取込ジョブは対象外です。'};

export function createTagUI({$, $$, api, t, esc, btn, modal, closeModal, dialog, error, markLibraryDirty, displayName}){
 const label=e=>displayName(e)+(e.gender&&e.gender!=='neutral'?' · '+t(e.gender):'');
 const info=e=>`${label(e)}${e.aliases?.length?' · '+e.aliases.join(', '):''}${e.uses!=null?' · '+e.uses+' '+t('uses'):''}`;
 async function collisionChoice(conflicts,editing,value){
  return new Promise(resolve=>{
   const choices=[...new Map(conflicts.flatMap(c=>c.choices).map(e=>[e.id,e])).values()];
   modal(`<h2>${esc(t('tagCollision'))}</h2><p>${esc(t('tagCollisionHint'))}</p><p>${conflicts.map(c=>esc(c.name)).join(', ')}</p><div class="stack">${choices.map(e=>`<button class="btn" data-collision-target="${e.id}">${esc(t(editing?'mergeInto':'useExistingTag'))}: ${esc(info(e))}</button>`).join('')}</div><div class="actions tag-actions">${btn(t('cancel'),'collision-cancel')}${conflicts.some(c=>c.choices.some(e=>e.name===value.name&&e.gender===value.gender))?'':btn(t('keepSeparateTags'),'collision-separate')}</div>`);
   $$('[data-collision-target]').forEach(b=>b.onclick=()=>{closeModal();resolve({target:b.dataset.collisionTarget})});
   $('#collision-cancel').onclick=()=>{closeModal();resolve(null)};
   $('#collision-separate')?.addEventListener('click',()=>{closeModal();resolve({separate:true})});
   dialog.oncancel=()=>resolve(null);
  });
 }
 async function mergeConfirm(item,target,onSave,data){
  const preview=await api('entities/'+item.id+'/merge-preview','POST',{target});
  return new Promise(resolve=>{
   modal(`<h2>${esc(t('merge'))}</h2><p>${esc(info(preview.source))} → <b>${esc(info(preview.target))}</b></p><p>${esc(t('mergeCount'))}: ${preview.count}</p><p>${esc(t('mergePreviewHint'))}</p><div id="merge-error"></div><div class="actions tag-actions">${btn(t('cancel'),'merge-cancel')}${btn(t('merge'),'merge-confirm','primary')}</div>`);
   $('#merge-cancel').onclick=()=>{closeModal();resolve(false)};dialog.oncancel=()=>resolve(false);
   $('#merge-confirm').onclick=async()=>{const button=$('#merge-confirm');button.disabled=true;try{
    const result=await api('entities/'+item.id+'/merge','POST',{target,signature:preview.signature,metadata:data});
    closeModal();markLibraryDirty();await onSave(result.id);resolve(true);
   }catch(e){error($('#merge-error'),e);button.disabled=false}};
  });
 }
 function mergeEditor(item,onSave){
  modal(`<h2>${esc(t('merge'))}: ${esc(label(item))}</h2><p>${esc(t('mergeText'))}</p><div id="merge-error"></div><div class="stack"><input id="merge-query" placeholder="${esc(t('searchMetadata'))}"><label><span>${esc(t('mergeInto'))}</span><select id="merge-target"></select></label></div><div class="actions tag-actions">${btn(t('cancel'),'merge-cancel')}${btn(t('reviewMerge'),'merge-next','primary')}</div>`);
  let sequence=0,timer;const root=$('#merge-query');
  const load=async()=>{try{const seq=++sequence, candidates=await api('entities?kind='+item.kind+'&q='+encodeURIComponent(root.value));if(seq!==sequence||!root.isConnected)return;
   const targets=candidates.filter(e=>e.id!==item.id);
   $('#merge-target').innerHTML=targets.map(e=>`<option value="${e.id}">${esc(info(e))}</option>`).join('');$('#merge-next').disabled=!targets.length;
  }catch(e){if(root.isConnected)error($('#merge-error'),e)}};
  root.oninput=()=>{clearTimeout(timer);timer=setTimeout(load,180)};load();$('#merge-cancel').onclick=closeModal;
  $('#merge-next').onclick=async()=>{try{await mergeConfirm(item,$('#merge-target').value,onSave)}catch(e){error($('#merge-error'),e)}};
 }
 function editor(item,onSave,initial){
  const data={kind:'tag',name:item?.name||'',gender:item?.gender||'neutral',aliases:item?.aliases||[],display_alias:item?.display_alias||'',sort_reading:item?.sort_reading||'',...initial};
  modal(`<h2>${esc(t(item?'sharedTagTitle':'newMetadata'))}</h2><p>${esc(t('sharedWarning'))}</p><div id="metadata-error"></div><form id="metadata-form" class="stack"><label><span>${esc(t('canonicalName'))}</span><input id="metadata-name" required value="${esc(data.name)}"></label><label><span>${esc(t('gender'))}</span><select id="metadata-gender">${['neutral','female','male'].map(g=>`<option value="${g}" ${data.gender===g?'selected':''}>${esc(t(g))}</option>`).join('')}</select></label><label><span>${esc(t('aliases'))}</span><textarea id="metadata-aliases">${esc(data.aliases.join('\n'))}</textarea></label><label><span>${esc(t('displayAlias'))}</span><select id="metadata-display"></select><small>${esc(t('displayAliasHint'))}</small></label><label><span>${esc(t('sortReading'))}</span><input id="metadata-reading" value="${esc(data.sort_reading)}"></label><div class="actions tag-actions">${item?btn(t('merge'),'metadata-merge'):''}${btn(t('cancel'),'metadata-cancel')}<button class="btn primary" type="submit">${esc(t('save'))}</button></div></form>`);
  let selected=data.display_alias;
  const aliases=()=>[...new Set($('#metadata-aliases').value.split('\n').map(s=>s.trim()).filter(Boolean))];
  function options(){const names=aliases();if(!names.includes(selected))selected='';$('#metadata-display').innerHTML=`<option value="">${esc($('#metadata-name').value||t('canonicalName'))}</option>`+names.map(n=>`<option value="${esc(n)}" ${n===selected?'selected':''}>${esc(n)}</option>`).join('')}
  options();$('#metadata-display').onchange=e=>selected=e.target.value;$('#metadata-name').oninput=options;$('#metadata-aliases').oninput=options;
  $('#metadata-cancel').onclick=closeModal;$('#metadata-merge')?.addEventListener('click',()=>mergeEditor(item,onSave));
  const submit=async(value,form=$('#metadata-form'))=>{
   try{const result=await api('entities'+(item?'/'+item.id:''),item?'PUT':'POST',value);markLibraryDirty();if(!form.isConnected)return;closeModal();await onSave(result.id)}
   catch(e){
    if(!form.isConnected)return;
    if(!e.tag_conflicts){error($('#metadata-error'),e);return}
    const decision=await collisionChoice(e.tag_conflicts,!!item,value);
    if(!decision){editor(item,onSave,value);return}
    if(decision.target){
     if(!item){markLibraryDirty();await onSave(decision.target);return}
     try{if(!await mergeConfirm(item,decision.target,onSave,value))editor(item,onSave,value)}catch(err){editor(item,onSave,value);error($('#metadata-error'),err)}
    }else{editor(item,onSave,value);await submit({...value,allow_collision:true,collision_signature:e.signature})}
   }
  };
  $('#metadata-form').onsubmit=e=>{e.preventDefault();submit({kind:'tag',name:$('#metadata-name').value,gender:$('#metadata-gender').value,aliases:aliases(),display_alias:$('#metadata-display').value,sort_reading:$('#metadata-reading').value})};
 }
 function workEditor(item,onApply,onShared){
  modal(`<h2>${esc(t('workTag'))}: ${esc(displayName(item))}</h2><p>${esc(t('workTagHint'))}</p><div id="work-tag-error"></div><form id="work-tag-form" class="stack"><label><span>${esc(t('gender'))}</span><select id="work-tag-gender">${['neutral','female','male'].map(g=>`<option value="${g}" ${(item.gender||'neutral')===g?'selected':''}>${esc(t(g))}</option>`).join('')}</select></label><div class="actions tag-actions">${item.id?btn(t('editSharedTag'),'work-tag-shared'):''}${btn(t('cancel'),'work-tag-cancel')}<button class="btn primary" type="submit">${esc(t('apply'))}</button></div></form>`);
  const workForm=$('#work-tag-form');
  $('#work-tag-cancel').onclick=closeModal;
  $('#work-tag-shared')?.addEventListener('click',async()=>{try{const shared=await api('entities/'+item.id);if(!workForm.isConnected)return;editor(shared,async id=>{await onShared(id);workEditor(await api('entities/'+id),onApply,onShared)})}catch(e){error($('#work-tag-error'),e)}});
  $('#work-tag-form').onsubmit=async e=>{e.preventDefault();try{
   const gender=$('#work-tag-gender').value;
   if(gender===(item.gender||'neutral')){closeModal();onApply(item);return}
   const result=await api('entities/attribute','POST',{name:item.name,gender});if(!workForm.isConnected)return;
   let changed=result.find(e=>e.name===item.name);
   if(!changed&&result.length>1){const choices=await reviewTags([{index:0,name:item.name,gender,choices:result}]);if(!choices)return;changed=result.find(e=>e.id===choices[0])}
   changed=changed||result[0];
   if(!changed){changed={...item,gender,literal_name:true};delete changed.id;delete changed.uses;delete changed.created}
   closeModal();onApply(changed);
  }catch(err){error($('#work-tag-error'),err)}};
 }
 async function reviewTags(conflicts){
  return new Promise(resolve=>{
   modal(`<h2>${esc(t('tagReview'))}</h2><p>${esc(t('tagReviewHint'))}</p><div class="stack">${conflicts.map(c=>`<label><span>${esc(c.name)}${c.gender!=='neutral'?' · '+esc(t(c.gender)):''}</span><select data-review-tag="${c.index}"><option value="">${esc(t('select'))}</option>${c.choices.map(e=>`<option value="${e.id}">${esc(info(e))}</option>`).join('')}</select></label>`).join('')}</div><div class="actions tag-actions">${btn(t('cancel'),'tags-cancel')}${btn(t('apply'),'tags-apply','primary')}</div>`);
   $('#tags-cancel').onclick=()=>{closeModal();resolve(null)};dialog.oncancel=()=>resolve(null);
   $('#tags-apply').onclick=()=>{const inputs=$$('[data-review-tag]');if(inputs.some(i=>!i.value)){inputs.find(i=>!i.value).focus();return}const choices=Object.fromEntries(inputs.map(i=>[i.dataset.reviewTag,i.value]));closeModal();resolve(choices)};
  });
 }
 return {editor,workEditor,mergeEditor,reviewTags};
}
