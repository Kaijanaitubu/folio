// UI shares the existing shell, request guards and escaped text helpers.
export function createNhentaiUI({workMergeUI,reviewTags, $, $$, api, t, esc, btn, modal, closeModal, dialog, error, toast, nav, shell, heading, summaryCards, markLibraryDirty}){
 const modes=(id,label)=>`<label><span>${esc(t(label))}</span><select id="${id}"><option value="neutral">${esc(t('nhentaiNeutral'))}</option><option value="frequency">${esc(t('nhentaiFrequency'))}</option></select></label>`;
 const safe=fn=>async()=>{try{await fn()}catch(e){toast(e.message)}};
 async function mount(container){
  const state=await api('nhentai/status');if(!container.isConnected)return;
  container.innerHTML=`<section class="panel stack"><h3>${esc(t('nhentaiTitle'))}</h3><p id="nhentai-state"></p><form id="nhentai-connect-form" class="stack"><label><span>${esc(t('nhentaiKey'))}</span><input id="nhentai-key" type="password" autocomplete="off" spellcheck="false" placeholder="${state.connected?'••••••••':''}"><small>${esc(t('nhentaiKeyHint'))}</small></label><label class="check-label"><input id="nhentai-remember" type="checkbox" ${state.can_remember?'':'disabled'}><span>${esc(t('nhentaiRemember'))}</span></label><label><span>${esc(t('nhentaiQuery'))}</span><input id="nhentai-query" autocomplete="off"></label><div class="row wrap"><button class="btn primary" type="submit" id="nhentai-connect">${esc(t('nhentaiConnect'))}</button>${btn(t('nhentaiDisconnect'),'nhentai-disconnect')}</div></form><div id="nhentai-error"></div>${modes('nhentai-default','nhentaiDefault')}<small class="muted">${esc(t('nhentaiTagHint'))}</small><div id="nhentai-preview"></div></section>`;
  const paintState=s=>{$('#nhentai-state').textContent=t(s.connected?'nhentaiConnected':'nhentaiDisconnected')+(s.connected?' · '+t(s.remembered?'nhentaiRemembered':'nhentaiSession'):'');$('#nhentai-disconnect').disabled=!s.connected&&!s.remembered};
  paintState(state);$('#nhentai-default').value=state.tag_mode;
  for(const id of ['nhentai-query','nhentai-key'])$('#'+id).oninput=()=>$('#nhentai-preview').replaceChildren();
  $('#nhentai-default').onchange=safe(async()=>{await api('nhentai/settings','POST',{tag_mode:$('#nhentai-default').value});toast(t('nhentaiDefaultSaved'))});
  $('#nhentai-disconnect').onclick=safe(async()=>{const s=await api('nhentai/disconnect','POST',{});paintState(s);$('#nhentai-preview').replaceChildren();$('#nhentai-key').value=''});
  $('#nhentai-connect-form').onsubmit=async e=>{
   e.preventDefault();const button=$('#nhentai-connect'),out=$('#nhentai-preview'),query=$('#nhentai-query').value.trim();button.disabled=true;$('#nhentai-error').replaceChildren();
   try{
    const result=await api('nhentai/connect','POST',{key:$('#nhentai-key').value.trim(),remember:$('#nhentai-remember').checked,query});if(!container.isConnected)return;
    $('#nhentai-key').value='';paintState(result);const preview=result.preview;
    out.innerHTML=`<div class="stack"><p>${esc(preview.total==null?t('nhentaiCountUnknown'):t('nhentaiTotal')+': '+preview.total.toLocaleString())}</p><p class="muted small">${esc(t('nhentaiPreviewHint'))}</p><label><span>${esc(t('nhentaiScope'))}</span><select id="nhentai-scope"><option value="all">${esc(t('nhentaiAll'))}</option><option value="selected">${esc(t('nhentaiSelected'))}</option></select></label>${modes('nhentai-tag-mode','nhentaiTagMode')}<div class="bookmark-list">${preview.items.map((i,n)=>`<label class="bookmark-row"><input type="checkbox" data-favorite="${n}" checked disabled><div class="info">${esc(i.title||i.url)}<small>${esc(i.url)}</small></div></label>`).join('')}</div>${btn(t('nhentaiStart'),'nhentai-start','primary','upload')}</div>`;
    $('#nhentai-scope').onchange=()=>$$('[data-favorite]').forEach(b=>b.disabled=$('#nhentai-scope').value==='all');
    $('#nhentai-tag-mode').value=$('#nhentai-default').value;
    $('#nhentai-start').disabled=!preview.items.length;
    $('#nhentai-start').onclick=async()=>{
     const start=$('#nhentai-start');start.disabled=true;
     try{const selected=$('[id="nhentai-scope"]').value==='selected';const items=selected?$$('[data-favorite]:checked').map(b=>preview.items[Number(b.dataset.favorite)]):undefined;if(selected&&!items.length)throw Error(t('selectNone'));
      const job=await api('jobs','POST',{kind:'favorites',query,items,tag_mode:$('#nhentai-tag-mode').value});nav('/job/'+job.id)
     }catch(e){error($('#nhentai-error'),e);start.disabled=false}
    };
   }catch(e){if(container.isConnected)error($('#nhentai-error'),e)}finally{if(button.isConnected)button.disabled=false}
  };
 }
 function chooseMatch(incoming,candidates=[],batch=false,options={}){
  return new Promise(resolve=>{
   modal(`<h2 tabindex="-1" autofocus>${esc(options.title||t('matchTitle'))}</h2><p>${esc(options.hint||t('matchHint'))}</p><div class="import-match"><b>${esc(incoming.title||'')}</b><small>${esc(t('author'))}: ${esc((incoming.author||[]).map(a=>a.display_name||a.name).join(', '))}</small><small>${esc(incoming.language||'')} · ${esc(t('pages'))}: ${esc(incoming.pages??'—')}</small></div><div id="match-candidates" class="stack"></div><label><span>${esc(t('matchSearch'))}</span><input id="match-query" type="search" autocomplete="off"></label><div id="match-error"></div>${batch?`<label class="check-label match-candidate"><input id="match-all" type="checkbox"><span>${esc(t('matchAll'))}</span></label><p class="muted small">${esc(t('matchAllHint'))}</p>`:''}<div class="actions wrap">${btn(t('cancel'),'match-cancel')}${options.existing?'':btn(t('matchNew'),'match-new')}${btn(t('matchAttach'),'match-attach','primary')}</div>`);
   let selected=candidates.length===1?candidates[0].id:null, sequence=0,timer;
   const paint=items=>{
    items=items.filter(w=>w.id!==options.exclude);
    $('#match-candidates').innerHTML=items.map(w=>`<label class="check-label import-match match-candidate"><input type="radio" name="match-target" value="${esc(w.id)}" ${selected===w.id?'checked':''}><span><b>${esc(w.title)}</b><small>${esc((w.authors||w.author?.map(a=>a.display_name||a.name)||[]).join(', '))}</small><small>${esc(w.primary_url||w.links?.find(l=>l.is_primary)?.url||'')}</small><small>${esc(w.language||'')} · ${esc(t('pages'))}: ${esc(w.pages??'—')}</small>${w.evidence?.original_source?`<small>${esc(t('originalSourceMatch'))}</small>`:''}${w.evidence&&(w.evidence.language===false||w.evidence.pages===false)?`<small class="notice">${esc(t('matchMismatch'))}</small>`:''}${w.evidence?.author_conflict?`<small class="notice">${esc(t('matchAuthorMismatch'))}</small>`:w.evidence?.author===false?`<small>${esc(t('matchAuthorUnknown'))}</small>`:''}</span></label>`).join('');
    $('#match-attach').disabled=!selected;$$('[name="match-target"]').forEach(r=>r.onchange=()=>{selected=r.value;$('#match-attach').disabled=false});
   };
   paint(candidates);
   const finish=action=>{clearTimeout(timer);sequence++;const result=action?{action,target:selected,apply_all:$('#match-all')?.checked||false}:null;closeModal();resolve(result)};
   $('#match-cancel').onclick=()=>finish(null);if($('#match-new'))$('#match-new').onclick=()=>finish('new');$('#match-attach').onclick=()=>finish('attach');dialog.oncancel=()=>{clearTimeout(timer);sequence++;resolve(null)};
   $('#match-query').oninput=()=>{clearTimeout(timer);const query=$('#match-query').value.trim(),seq=++sequence;selected=null;$('#match-attach').disabled=true;timer=setTimeout(async()=>{try{const r=await api('works?limit=40&q='+encodeURIComponent(query?JSON.stringify(query):''));if(seq===sequence&&$('#match-candidates'))paint(r.items)}catch(e){if(seq===sequence&&$('#match-error'))error($('#match-error'),e)}},250)};
  });
 }
 async function jobPage(id){
  shell('imports',heading(t('jobResults'),t('jobHint'),`<a class="btn" href="#/imports">${esc(t('imports'))}</a>`)+`<div id="job-summary"></div><div class="row wrap"><label><span>${esc(t('jobFilter'))}</span><select id="job-filter"><option value="all">${esc(t('jobAllItems'))}</option><option value="warnings">${esc(t('importWarnings'))}</option>${['match_review','tag_review','failed','needs_review','added','linked','duplicate_url','pending','cancelled'].map(s=>`<option value="${s}">${esc(t(s))}</option>`).join('')}</select></label></div><div id="job-items" class="bookmark-list"></div><div id="job-more"></div>`);
  const root=$('#job-summary');let latest,limit=100,timer,loading=false;
  const paintItems=()=>{
   const filter=$('#job-filter').value,items=latest.items.filter(i=>filter==='all'||filter==='warnings'&&(i.warnings?.original_links?.length||i.warnings?.titles?.length||i.warnings?.related?.length||i.status==='tag_review')||i.status===filter),shown=items.slice(0,limit);
   $('#job-items').innerHTML=shown.map(i=>`<div class="bookmark-row"><div class="info">${i.work_id?`<a href="#/work/${esc(i.work_id)}">${esc(i.title)}</a>`:esc(i.title||i.label||i.url)}<small>${esc(i.url)}${i.message?'<br>'+esc(i.message):''}</small>${i.status==='match_review'?btn(t('matchReview'),'review-'+i.id):i.status==='tag_review'?btn(t('tagReview'),'review-tags-'+i.id):''}${i.warnings?.original_links?.length||i.warnings?.titles?.length||i.warnings?.related?.length?`<details><summary>${esc(t('importWarnings'))}</summary>${summaryCards([...(i.warnings.titles||[]),...(i.warnings.related||[])])}${(i.warnings.original_links||[]).map(link=>`<small>${esc(t('originalSkipped'))}: ${esc(link.url)}</small>${summaryCards(link.matches||[])}`).join('')}</details>`:''}</div><span class="status ${i.status}">${esc(t(i.status))}</span></div>`).join('');
   shown.filter(i=>i.status==='match_review').forEach(i=>$('#review-'+i.id).onclick=safe(async()=>{
    const incoming=i.review_data||{title:i.title};const decision=await chooseMatch(incoming,i.warnings.candidates||[],true);if(!decision||!root.isConnected)return;
    if(decision.action==='attach'){
     const p=await api('jobs/'+id+'/merge-preview','POST',{item_id:i.id,target:decision.target});if(!root.isConnected)return;
     if(decision.apply_all)p.notice=t('matchAllMetadataHint');
     const patch=await workMergeUI.review(p,()=>root.isConnected);if(patch===null||!root.isConnected)return;
     decision.merge_signature=p.signature;decision.metadata_patch=patch;
    }
    const result=await api('jobs/'+id+'/decide','POST',{item_id:i.id,...decision});markLibraryDirty();toast(t('matchResolved')+': '+result.resolved);await poll();
   }));
   shown.filter(i=>i.status==='tag_review').forEach(i=>$('#review-tags-'+i.id).onclick=safe(async()=>{
    const choices=await reviewTags(i.warnings.tags||[]);if(!choices||!root.isConnected)return;
    await api('jobs/'+id+'/tags','POST',{item_id:i.id,choices});markLibraryDirty();await poll();
   }));
   $('#job-more').innerHTML=items.length>limit?btn(t('jobMore')+` (${Math.min(limit,items.length)}/${items.length})`,'job-more-button'):'';
   $('#job-more-button')?.addEventListener('click',()=>{limit+=100;paintItems()});
  };
  const poll=async()=>{
   clearTimeout(timer);if(loading||!root.isConnected)return;loading=true;
   try{
    latest=await api('jobs/'+id);if(!root.isConnected)return;const j=latest,total=j.items.length,warned=j.items.filter(i=>i.warnings?.original_links?.length||i.warnings?.titles?.length||i.warnings?.related?.length||i.status==='tag_review').length,done=j.items.filter(i=>!['pending','running','match_review','tag_review'].includes(i.status)).length;
    root.innerHTML=`<section class="panel stack"><div class="row between wrap"><h3>${esc(t(j.status))} · ${done}/${total}</h3><div class="row wrap">${j.status==='running'?btn(t('pauseJob'),'pause-job')+btn(t('cancelJob'),'cancel-job'):['paused','awaiting_key','cancelled'].includes(j.status)?btn(t('resumeJob'),'resume-job'):''}${btn(t('retryFailed'),'retry-job')}</div></div>${!j.enumeration_done?`<p>${esc(t('nhentaiEnumeration'))}: ${Math.max(0,j.enumeration_page-1)} / ${j.enumeration_pages??'—'}</p><small>${esc(t('nhentaiEnumerationHint'))}</small>`:''}${j.message?`<p class="notice">${esc(j.message)} ${j.status==='awaiting_key'?`<a href="#/imports?view=favorites&amp;service=nhentai">${esc(t('nhentaiConnect'))}</a>`:''}</p>`:''}<div class="progress"><div></div></div>${warned?`<p class="notice">${esc(t('importWarnings'))}: ${warned}</p>`:''}<div class="row wrap">${Object.entries(j.counts).map(([s,n])=>`<span class="status ${s}">${esc(t(s))}: ${n}</span>`).join('')}</div><label><span>${esc(t('matchPolicy'))}</span><select id="job-match-policy"><option value="ask">${esc(t('matchAsk'))}</option><option value="attach_unique">${esc(t('matchUnique'))}</option><option value="new">${esc(t('matchSeparate'))}</option></select><small>${esc(t('matchAllHint'))}</small></label></section>`;
    $('.progress>div',root).style.width=(total?done/total*100:0)+'%';$('#job-match-policy').value=j.match_policy;
    $('#job-match-policy').onchange=safe(async()=>{await api('jobs/'+id+'/policy','POST',{policy:$('#job-match-policy').value})});
    for(const command of ['pause','cancel','resume','retry'])$('#'+command+'-job')?.addEventListener('click',safe(async()=>{await api('jobs/'+id+'/'+(command==='resume'&&j.status==='cancelled'?'retry':command),'POST',{});await poll()}));
    paintItems();if(j.status==='running')timer=setTimeout(poll,3000);
   }catch(e){toast(e.message);if(root.isConnected)timer=setTimeout(poll,5000)}finally{loading=false}
  };
  $('#job-filter').onchange=()=>{limit=100;if(latest)paintItems()};await poll();
 }
 return {mount,chooseMatch,jobPage,modes};
}
