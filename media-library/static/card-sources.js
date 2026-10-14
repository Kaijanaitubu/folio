// A compact source summary uses saved labels, then known providers or the host.
export function createCardSources({esc,t,modal,closeModal,$}){
 const valid=work=>(work.links||[]).filter(link=>{try{return ['http:','https:'].includes(new URL(link.url).protocol)}catch{return false}});
 const host=link=>new URL(link.url).hostname.replace(/^www\./i,'');
 const name=link=>link.label?.trim()||({'pawchive.pw':'Pawchive','hitomi.la':'Hitomi','nhentai.net':'nhentai','momon-ga.com':'momon-ga','dlsite.com':'DLsite','play.dlsite.com':'DLsite Play','dlsharing.com':'DLsite','dmm.co.jp':'FANZA同人','book.dmm.co.jp':'FANZAブックス','book.dmm.com':'DMMブックス'}[host(link)]||host(link));
 function button(work){
  const links=valid(work);if(!links.length)return '';
  const primary=links.find(link=>link.is_primary)||links[0],extra=links.length-1;
  return `<button type="button" class="card-source" data-card-sources="${esc(work.id)}" aria-label="${esc(t('sources')+': '+work.title)}" title="${esc(t('sources')+': '+name(primary)+(extra?' +'+extra:''))}"><span>${esc(name(primary))}</span>${extra?`<small>+${extra}</small>`:''}</button>`;
 }
 function open(work){
  const links=valid(work);
  modal(`<div class="card-sources-header"><h2>${esc(t('sources'))}</h2><button type="button" class="iconbtn" id="card-sources-close" aria-label="${esc(t('close'))}">×</button></div><p class="card-sources-title">${esc(work.title)}</p><div class="card-sources-list">${links.map(link=>`<a class="card-source-link" href="${esc(link.url)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"><span class="card-source-heading"><b>${esc(name(link))}</b>${link.is_primary?`<span class="tag">${esc(t('primary'))}</span>`:''}<span aria-hidden="true">↗</span></span><small>${esc(host(link))}</small><span class="card-source-url">${esc(link.url)}</span></a>`).join('')}</div>`);
  $('#card-sources-close').onclick=closeModal;
 }
 function bind(root,works){
  const byId=new Map(works.map(work=>[String(work.id),work]));
  root.querySelectorAll('[data-card-sources]').forEach(button=>button.onclick=()=>{const work=byId.get(button.dataset.cardSources);if(work)open(work)});
 }
 return {button,bind};
}
