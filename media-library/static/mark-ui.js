export const markEn={marks:'Marks',mark:'Mark',editMarks:'Edit marks',markLabels:'Mark labels',markLabelHint:'Five independent marks, shared across your library. Numbers and symbols stay fixed. Leave a label blank to use its default.',markLabelSaved:'Mark labels saved',searchHelp:'Search help'};
export const markJa={marks:'マーク',mark:'マーク',editMarks:'マークを編集',markLabels:'マークのラベル',markLabelHint:'5個のマークは全作品で共通です。番号と記号は固定です。ラベルを空欄にすると既定名を使います。',markLabelSaved:'マークのラベルを保存しました',searchHelp:'検索ヘルプ'};
export function createMarkUI({t,esc,config,api,onSaved,onError}){
 const defs=()=>config().marks||[];
 const name=d=>d.label||(d.number===1?t('bought'):t('mark')+' '+d.number);
 const summary=w=>defs().filter(d=>(w.marks||[]).includes(d.number)).map(d=>`<span class="work-mark-symbol" title="${esc(d.number+'. '+name(d))}" aria-label="${esc(name(d))}">${esc(d.on)}</span>`).join('');
 const buttons=w=>`<div class="mark-buttons">${defs().map(d=>`<button type="button" class="mark-toggle" data-work-mark="${d.number}" aria-pressed="${(w.marks||[]).includes(d.number)}" aria-label="${esc(name(d))}"><span aria-hidden="true">${esc((w.marks||[]).includes(d.number)?d.on:d.off)}</span><small>${d.number}. ${esc(name(d))}</small></button>`).join('')}</div>`;
 const detail=w=>`<details class="work-mark-menu"><summary aria-label="${esc(t('editMarks'))}"><span class="mark-summary">${summary(w)||esc(t('marks'))}</span><span class="mark-chevron" aria-hidden="true">⌄</span></summary>${buttons(w)}</details>`;
 function bind(root,getWork,onChange,immediate=false){
  root.querySelectorAll('[data-work-mark]').forEach(button=>button.onclick=async()=>{
   const work=getWork(),number=Number(button.dataset.workMark),value=!(work.marks||[]).includes(number);
   if(!immediate){const marks=new Set(work.marks||[]);if(value)marks.add(number);else marks.delete(number);work.marks=[...marks].sort();work.bought=marks.has(1);onChange(work);root.innerHTML=buttons(work);bind(root,getWork,onChange);return;}
   root.querySelectorAll('button').forEach(b=>b.disabled=true);
   try{const result=await api('works/'+work.id+'/marks','POST',{number,value,expected:work.marks||[]});onSaved(result);if(!root.isConnected)return;onChange(result);root.innerHTML=detail(result);root.querySelector('details').open=true;bind(root,getWork,onChange,true);}
   catch(e){onError(e.message);if(root.isConnected){try{const latest=await api('works/'+work.id);if(!root.isConnected)return;onChange(latest);root.innerHTML=detail(latest);root.querySelector('details').open=true;bind(root,getWork,onChange,true);}catch{root.querySelectorAll('button').forEach(b=>b.disabled=false);}}}
  });
 }
 const settings=()=>`<section class="panel stack"><h3>${esc(t('markLabels'))}</h3><p class="muted small">${esc(t('markLabelHint'))}</p><form id="mark-label-form" class="stack">${defs().map(d=>`<label><span>${d.number}. ${esc(d.off)}</span><input data-mark-label="${d.number}" maxlength="80" value="${esc(d.label)}" placeholder="${esc(name({...d,label:''}))}"></label>`).join('')}<div id="mark-label-error"></div><div><button type="submit" class="btn primary">${esc(t('save'))}</button></div></form></section>`;
 function bindSettings(root){const expected=defs().map(d=>d.label);root.querySelector('#mark-label-form').onsubmit=async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{const result=await api('mark-labels','PUT',{expected,labels:[...root.querySelectorAll('[data-mark-label]')].map(e=>e.value)});config().marks=result.marks;expected.splice(0,5,...result.marks.map(d=>d.label));onError(t('markLabelSaved'));}catch(e){root.querySelector('#mark-label-error').textContent=e.message;}finally{button.disabled=false;}};}
 return {summary,buttons,detail,bind,settings,bindSettings,name};
}
