import {createMarkUI,markEn,markJa} from './mark-ui.js';
import {searchHelpHTML} from './search-help.js';
import {createBatchDelete} from './batch-delete.js';
import {createTagUI,tagEn,tagJa} from './tag-ui.js';
import {createNhentaiUI} from './nhentai-ui.js';
import {nhentaiEn,nhentaiJa} from './nhentai-text.js';
import {featureEn,featureJa} from './feature-text.js';
import {applyImported,metadataKinds,sameMetadataSet,hasImportedChanges} from './import-policy.js';
import {en,ja} from './i18n.js';
import {localizeError} from './errors.js';
import {bookmarklet} from './source-link.js';
import {pageTitle} from './page-title.js';
import {createTrashSourceUI} from './trash-source-ui.js';
import {createCardSources} from './card-sources.js';
import {isStoreSource,isStoreCover,isDLsitePlaySeries} from './store-sources.js';
import {isPawchiveSource,isPawchiveCover,mergeOriginals} from './pawchive-sources.js';
import {createPawchiveUI} from './pawchive-ui.js';
Object.assign(en,featureEn,nhentaiEn,tagEn,markEn);Object.assign(ja,featureJa,nhentaiJa,tagJa,markJa);
const $=(s,root=document)=>root.querySelector(s), $$=(s,root=document)=>[...root.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let lang=localStorage.getItem('folio-language')||'en', config, draft=null, baseline='', librarySnapshot=null, currentWork=null, routeVersion=0, jobTimer=null, suggestionTimer;
let selecting=false, selectedWorks=new Set(), selectionHash='', previewController=null, previewObjectUrl='', previewTimer=null, previewSequence=0, installPrompt=null;
let selectionVersion=0, matchingSavedSearch=null;
let theme=localStorage.getItem('folio-theme')||'dark', searchDraft='';
document.documentElement.dataset.theme=theme;
document.querySelector('meta[name="theme-color"]').content=theme==='light'?'#f6f5f1':'#101010';
const displayName=e=>e.display_name||e.display_alias||e.name;
const metadataQuery=(e,kind=e.kind)=>(kind==='tag'?(e.gender&&e.gender!=='neutral'?e.gender:'none'):kind)+':'+JSON.stringify(e.name);
const metadataHref=(e,kind)=>'#/library?'+new URLSearchParams({q:metadataQuery(e,kind)});
const t=k=>(lang==='ja'?ja:en)[k]??en[k]??k;
const symbols={Star:['★','☆'],Heart:['♥','♡'],Circle:['●','○'],Diamond:['◆','◇'],Square:['■','□'],Triangle:['▲','△'],Flower:['✿','❀'],Sun:['☀','☀'],Moon:['☾','☾'],Sparkle:['✦','✧']};
const paths={book:'<path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4z"/><path d="M20 4h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-3h3z"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',plus:'<path d="M12 5v14M5 12h14"/>',tag:'<path d="m3 3 9 0 9 9-9 9-9-9z"/><circle cx="7.5" cy="7.5" r="1"/>',star:'<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',settings:'<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 3 2 2-1 4 3 2 3-1 3 4 3-2 1-3 4-1-1-4-3-1-1-4z"/>',arrow:'<path d="M20 12H4m6-6-6 6 6 6"/>',external:'<path d="M14 3h7v7m0-7-11 11M10 3H3v18h18v-7"/>',dice:'<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="7.5" cy="7.5" r=".5"/><circle cx="16.5" cy="7.5" r=".5"/><circle cx="12" cy="12" r=".5"/><circle cx="7.5" cy="16.5" r=".5"/><circle cx="16.5" cy="16.5" r=".5"/>',menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',edit:'<path d="m4 16-1 5 5-1L21 7l-4-4zM14 6l4 4"/>',x:'<path d="m6 6 12 12M6 18 18 6"/>',refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-2l2 3M4 16l2 3a7 7 0 0 0 12-2"/>'};
const icon=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.book}</svg>`;
paths.bookmark='<path d="M6 3h12v18l-6-4-6 4z"/>';
paths.trash='<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>';
const btn=(text,id,style='',ico='')=>`<button type="button" class="btn ${style}" ${id?`id="${id}"`:''}>${ico?icon(ico):''}${esc(text)}</button>`;
function toast(message){const el=$('#toast');el.textContent=message;el.style.display='block';clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.style.display='none',4500)}
async function api(path,method='GET',body){const res=await fetch('/api/'+path,{method,headers:{'Content-Type':'application/json',...(config?{'X-Library-Token':config.token}:{})},body:body===undefined?undefined:JSON.stringify(body)});const data=await res.json();if(!res.ok)throw Object.assign(Error(localizeError(data.error||t('error'),lang)),{matches:data.matches,tag_conflicts:data.tag_conflicts,signature:data.signature});return data}
function error(el,e){el.innerHTML=`<div class="error" role="alert">${esc(localizeError(e.message||e,lang))}</div>`}
function nav(path){location.hash=path}
function updatePageTitle(){const {path,params}=route();const title=path.startsWith('/work/')&&currentWork?.id===path.split('/')[2]?currentWork.title:path.startsWith('/edit/')?draft?.title||'':'';document.title=pageTitle(path,params,title)}
async function refreshConfig(){config=await api('config')}
const markUI=createMarkUI({t,esc,config:()=>config,api,onError:toast,onSaved:result=>{markLibraryDirty();libraryItems=libraryItems.map(w=>w.id===result.id?result:w);if(librarySnapshot)librarySnapshot.items=librarySnapshot.items.map(w=>w.id===result.id?result:w);if(route().path==='/library'&&$('#gallery'))paintLibrary();}});
const cardSources=createCardSources({esc,t,modal,closeModal,$});
function showSearchHelp(){modal(searchHelpHTML(config,lang,esc));dialog.classList.add('search-help-dialog');dialog.addEventListener('close',()=>dialog.classList.remove('search-help-dialog'),{once:true});$('#search-help-close').onclick=closeModal;}
function route(){const [path,qs='']=(location.hash.slice(1)||'/library').split('?');return {path,params:new URLSearchParams(qs)}}
function shell(active,content,bottom=true){
 updatePageTitle();
 document.documentElement.lang=lang;document.documentElement.dataset.theme=theme;
 const navs=[['library','grid','/library'],['metadata','tag','/metadata'],['ratings','star','/ratings'],['imports','upload','/imports'],['savedSearches','bookmark','/saved-searches'],['trash','trash','/trash'],['history','refresh','/history'],['settings','settings','/settings']];
 $('#app').innerHTML=`<div class="shell"><div class="mobile-head"><a class="brand" href="#/library"><span class="brandmark">f</span>Folio<span class="muted small"> / ${esc(t('library'))}</span></a><button class="iconbtn" id="menu" aria-label="${esc(t('settings'))}">${icon('menu')}</button></div><aside class="sidebar"><a class="brand" href="#/library"><span class="brandmark">f</span>Folio</a><div class="nav-caption">${esc(t('localLabel'))}</div>${navs.map(([key,ico,path])=>`<a class="navitem ${active===key?'active':''}" href="#${path}">${icon(ico)}${esc(t(key))}</a>`).join('')}<div class="sidebar-bottom"><div class="locale"><button data-lang="en" class="${lang==='en'?'chosen':''}">EN</button><button data-lang="ja" class="${lang==='ja'?'chosen':''}">日本語</button></div><div class="local"><span class="dot"></span>${esc(t('localLabel'))}<br>${esc(t('localHint'))}</div></div></aside><main class="main">${content}</main>${bottom?`<nav class="bottom-bar utility-bar" aria-label="${esc(t('library'))}"><form id="bottom-search-form" class="utility-search search-wrap" role="search"><input id="query" aria-label="${esc(t('search'))}" placeholder="${esc(t('searchPlaceholder'))}" value="${esc(searchDraft)}" autocomplete="off"><button id="bottom-search" type="submit" aria-label="${esc(t('search'))}" title="${esc(t('search'))}">${icon('search')}</button><div id="suggestions"></div></form><button id="bottom-random" type="button" aria-label="${esc(t('random'))}" title="${esc(t('random'))}">${icon('dice')}</button><button id="bottom-add" type="button" aria-label="${esc(t('add'))}" title="${esc(t('add'))}">${icon('plus')}</button></nav>`:''}</div>`;
 updateUtilityFocus();
 $('#menu')?.addEventListener('click',()=>$('.sidebar').classList.toggle('open'));
 $$('.navitem').forEach(a=>a.addEventListener('click',()=>$('.sidebar').classList.remove('open')));
 $$('[data-lang]').forEach(b=>b.onclick=()=>switchLanguage(b.dataset.lang));
 $('#bottom-add')?.addEventListener('click',()=>{captureLibrary();nav('/new')});
 $('#bottom-search-form')?.addEventListener('submit',e=>{e.preventDefault();submitSearch()});
 if($('#query')){$('#query').oninput=()=>{searchDraft=$('#query').value;suggest($('#query'))};$('#query').onkeydown=e=>{if(e.key==='Escape')$('#suggestions').innerHTML=''}}
 $('#bottom-random')?.addEventListener('click',async()=>{try{const q=route().path==='/library'?(route().params.get('q')||''):'';const result=await api('works?random=1&q='+encodeURIComponent(q));if(!result.items.length)return toast(t('noResults'));captureLibrary();nav('/work/'+result.items[0].id)}catch(e){toast(e.message)}});
}
function switchLanguage(next){lang=next;localStorage.setItem('folio-language',lang);render(true)}
function heading(title,sub,action='',eyebrow=''){return `<div class="pagehead"><div>${eyebrow?`<div class="eyebrow">${esc(eyebrow)}</div>`:''}<h1>${esc(title)}</h1><p>${esc(sub)}</p></div>${action}</div>`}
function placeholder(unavailable=false,hitomi=false){return `<div class="placeholder" ${unavailable?`title="${esc(t(hitomi?'hitomiCoverHint':'externalCoverHint'))}"`:''}>${icon('book')}<span>${esc(t(unavailable?'coverUnavailable':'noCover'))}</span>${hitomi?`<small>${esc(t('viewCoverOnSource'))}</small>`:''}</div>`}
// Change the browser image identity when the saved cover changes. The relay still
// reads the URL from the database; this query is not an upstream fetch target.
function image(w,extra=''){const relay=w.id&&relayCover(w.cover);const src=relay?'/api/works/'+encodeURIComponent(w.id)+'/cover?v='+encodeURIComponent(w.cover):w.cover;return `<div class="cover ${extra}">${w.cover?`<img src="${esc(src)}" alt="${esc(w.title)}" loading="lazy" referrerpolicy="no-referrer" ${relay?'data-relay="hitomi"':''}>`:placeholder()}${w.category?`<span class="cover-badge">${esc(t(w.category))}</span>`:''}</div>`}
function images(){$$('.cover img').forEach(img=>{const failed=()=>{if(img.isConnected)img.outerHTML=placeholder(true,img.dataset.relay==='hitomi')};img.onerror=failed;if(img.complete&&!img.naturalWidth)failed()})}
function ratingDisplay(w,d){const n=w.ratings?.[d.id];const [on,off]=symbols[d.symbol]||symbols.Star;return `<div class="ratingline"><span>${d.number}. ${esc(d.name)}</span>${n?`<span class="symbols">${esc(on.repeat(n))}<span class="off">${esc(off.repeat(d.maximum-n))}</span></span><small>${n}/${d.maximum}</small>`:`<small>${esc(t('unrated'))}</small>`}</div>`}
function card(w){return `<div class="work-card" data-work-id="${esc(w.id)}"><label class="work-check"><input type="checkbox" data-work-check="${esc(w.id)}" aria-label="${esc(t('selectMode')+': '+w.title)}"></label><a class="card" href="#/work/${w.id}">${image(w)}<div class="card-title">${esc(w.title)}</div><div class="card-author">${esc(w.author.map(a=>displayName(a)).join(', ')||t('notSpecified'))}</div><div class="card-tags">${w.tag.slice(0,3).map(a=>`<span class="tag ${a.gender}">${esc(displayName(a))}</span>`).join('')}${w.tag.length>3?`<span class="tag">+${w.tag.length-3}</span>`:''}</div>${config.dimensions.filter(d=>d.gallery).map(d=>ratingDisplay(w,d)).join('')}</a><div class="card-footer">${cardSources.button(w)}<a class="card-marks" href="#/work/${w.id}" aria-label="${esc(w.title)}">${markUI.summary(w)}</a></div></div>`}
let libraryItems=[],total=0,seed=String(Date.now()),activeLibraryHash='',querySequence=0;
function markLibraryDirty(){if(librarySnapshot)librarySnapshot.dirty=true}
function captureLibrary(){if(route().path==='/library')librarySnapshot={hash:location.hash.slice(1)||'/library',items:libraryItems,total,seed,scroll:scrollY}}
async function library(){
 const {params}=route();const q=params.get('q')||'',sort=validLibrarySort(params.get('sort')||localStorage.getItem('folio-library-sort')||'newest');
 localStorage.setItem('folio-library-sort',sort);params.set('sort',sort);
 const canonical='/library?'+params;history.replaceState(null,'','#'+canonical);previousHash=location.hash;
 searchDraft=q;activeLibraryHash=canonical;
 shell('library',heading(t('libraryTitle'),t('librarySubtitle'),`<div class="desktop-add">${btn(t('add'),'add-top','primary','plus')}</div>`,t('collection'))+`<div class="toolbar library-toolbar"><span class="tag active-query">${esc(q||t('library'))}</span><select id="sort" aria-label="${esc(t('newest'))}">${['newest','oldest','recent','least','random'].map(k=>`<option value="${k}" ${sort===k?'selected':''}>${esc(t(k==='random'?'randomSort':k))}</option>`).join('')}${config.dimensions.map(d=>`<option value="rating${d.number}" ${sort==='rating'+d.number?'selected':''}>${esc(t('highest'))}: ${d.number}. ${esc(d.name)}</option>`).join('')}</select></div><div class="search-help"><a id="search-help-link" href="#search-help">${esc(t('searchHelp'))}</a> · ${esc(t('help'))} &nbsp; <code>${esc(t('searchExample'))}</code></div><div id="library-errors"></div><div class="results-line"><span id="count">${esc(t('loading'))}</span>${sort==='random'?`<button id="reshuffle" class="iconbtn" aria-label="${esc(t('reshuffle'))}">${icon('refresh')}</button>`:''}</div><div id="gallery" class="gallery"></div><div id="library-empty"></div><div id="more"></div>`);
 $('#search-help-link').onclick=event=>{event.preventDefault();showSearchHelp()};
 $('#add-top').onclick=()=>{captureLibrary();nav('/new')};
 $('#sort').onchange=updateLibraryQuery;
 $('#reshuffle')?.addEventListener('click',()=>{seed=String(Date.now());fetchLibrary(false)});
 mountLibraryFeatures();
 if(librarySnapshot?.hash===activeLibraryHash){libraryItems=librarySnapshot.items;total=librarySnapshot.total;seed=librarySnapshot.seed;if(librarySnapshot.dirty){const target=Math.max(40,libraryItems.length),savedScroll=librarySnapshot.scroll;libraryItems=[];const p=route().params;while(libraryItems.length<target){const r=await api(`works?q=${encodeURIComponent(p.get('q')||'')}&sort=${p.get('sort')||'newest'}&seed=${seed}&offset=${libraryItems.length}`);total=r.total;libraryItems.push(...r.items);if(!r.items.length||libraryItems.length>=total)break}librarySnapshot.dirty=false;paintLibrary();requestAnimationFrame(()=>scrollTo(0,savedScroll))}else{paintLibrary();requestAnimationFrame(()=>scrollTo(0,librarySnapshot.scroll))}}
 else {libraryItems=[];await fetchLibrary(false)}
}
function submitSearch(){$('#query')?.blur();searchDraft=$('#query')?.value||'';const sort=validLibrarySort($('#sort')?.value||localStorage.getItem('folio-library-sort')||'newest');const p=new URLSearchParams();if(searchDraft.trim())p.set('q',searchDraft.trim());p.set('sort',sort);const target='/library'+(p.size?'?'+p:'');$('#suggestions')&&( $('#suggestions').innerHTML='');if(route().path==='/library'){librarySnapshot=null;seed=String(Date.now());if((location.hash.slice(1)||'/library')===target){fetchLibrary(false);return}}nav(target)}
function validLibrarySort(value){return ['newest','oldest','recent','least','random',...config.dimensions.map(d=>'rating'+d.number)].includes(value)?value:'newest'}
function updateLibraryQuery(){resetSelection();const q=route().params.get('q')||'',sort=validLibrarySort($('#sort')?.value||'newest');localStorage.setItem('folio-library-sort',sort);const p=new URLSearchParams();if(q)p.set('q',q);p.set('sort',sort);const hash='/library?'+p;history.replaceState(null,'','#'+hash);previousHash=location.hash;activeLibraryHash=hash;selectionHash=hash;seed=String(Date.now());librarySnapshot=null;bindSelectionCards();refreshSearchSaveButton().catch(e=>toast(e.message));fetchLibrary(false)}
async function fetchLibrary(append){const seq=++querySequence;const q=route().params.get('q')||'',sort=$('#sort')?.value||'newest';try{const result=await api(`works?q=${encodeURIComponent(q)}&sort=${sort}&seed=${seed}&offset=${append?libraryItems.length:0}`);if(seq!==querySequence||route().path!='/library')return;$('#library-errors').innerHTML='';libraryItems=append?[...libraryItems,...result.items]:result.items;total=result.total;paintLibrary()}catch(e){if($('#library-errors'))error($('#library-errors'),e)}}
function paintLibrary(){if(!$('#gallery'))return;$('#count').textContent=`${total.toLocaleString()} ${t('works')} · ${libraryItems.length} ${t('showing')}`;$('#gallery').innerHTML=libraryItems.map(card).join('');images();cardSources.bind($('#gallery'),libraryItems);$$('.card,.card-marks').forEach(a=>a.onclick=captureLibrary);$('#library-empty').innerHTML=total?'':`<div class="empty"><div class="empty-icon">${icon(route().params.get('q')?'search':'book')}</div><h2>${esc(t(route().params.get('q')?'noResults':'emptyTitle'))}</h2><p>${esc(t(route().params.get('q')?'noResultsText':'emptyText'))}</p><div class="row">${route().params.get('q')?btn(t('clear'),'empty-clear'):btn(t('add'),'empty-add','primary','plus')+`<a class="btn" href="#/imports">${icon('upload')}${esc(t('imports'))}</a>`}</div></div>`;$('#empty-add')?.addEventListener('click',()=>nav('/new'));$('#empty-clear')?.addEventListener('click',()=>{$('#query').value='';searchDraft='';submitSearch()});$('#more').innerHTML=libraryItems.length<total?btn(t('loadMore'),'load-more','loadmore'):'';$('#load-more')?.addEventListener('click',()=>fetchLibrary(true));bindSelectionCards()}
function fragment(text){let quoted=false,escaped=false,start=0;for(let i=0;i<text.length;i++){const ch=text[i];if(escaped){escaped=false;continue}if(quoted&&ch==='\\'){escaped=true;continue}if(ch==='"')quoted=!quoted;else if(!quoted&&(ch==='/'||/\s/.test(ch)))start=i+1}const raw=text.slice(start),neg=raw.startsWith('-');const term=neg?raw.slice(1):raw;const sep=term.indexOf(':');return {start,neg,field:sep>=0?term.slice(0,sep):'',value:(sep>=0?term.slice(sep+1):term).replace(/^"/,'').replace(/"$/,'')}}
let suggestionVersion=0;
async function suggest(input){clearTimeout(suggestionTimer);const seq=++suggestionVersion;const container=$('#suggestions');if(!container)return;container.innerHTML='';const f=fragment(input.value);if(!f.value&&!/^mark[1-5]?$/.test(f.field))return;suggestionTimer=setTimeout(async()=>{try{const items=await api(`suggestions?q=${encodeURIComponent(f.value)}&field=${f.field}`);if(seq!==suggestionVersion||!container.isConnected||!items.length)return;container.innerHTML=`<div class="suggestions">${items.map((i,n)=>`<button type="button" data-index="${n}"><span>${esc(i.field)}:${esc(i.label)}</span><small>${esc(i.detail)}</small></button>`).join('')}</div>`;const select=n=>{const i=items[n];const val=/\s|[\/"\\]/.test(i.value)?JSON.stringify(i.value):i.value;input.value=input.value.slice(0,f.start)+(f.neg?'-':'')+i.field+':'+val+' ';container.innerHTML='';searchDraft=input.value;input.focus()};$$('button',container).forEach(b=>b.onclick=()=>select(Number(b.dataset.index)));input.onkeydown=e=>{if(e.isComposing){if(e.key==='Enter')e.preventDefault();return}const buttons=$$('button',container);let idx=buttons.findIndex(b=>b.classList.contains('selected'));if((e.key==='ArrowDown'||e.key==='ArrowUp')&&buttons.length){e.preventDefault();idx=(idx+(e.key==='ArrowDown'?1:buttons.length-1)+buttons.length)%buttons.length;buttons.forEach((b,n)=>b.classList.toggle('selected',n===idx))}else if(e.key==='Enter'){e.preventDefault();if(idx>=0)select(idx);else{container.innerHTML='';submitSearch()}}else if(e.key==='Escape')container.innerHTML=''}}catch{container.innerHTML=''}},180)}
async function detail(id){const version=routeVersion;const w=await api('works/'+id+'/open','POST',{});if(version!==routeVersion)return;currentWork=w;const source=w.links.find(l=>l.is_primary);shell('library',`<div class="row between"><a class="btn ghost" href="#${esc(librarySnapshot?.hash||'/library')}">${icon('arrow')}${esc(t('back'))}</a><div class="row wrap">${btn(lang==='ja'?'共有':'Share','share-work')}${btn(t('edit'),'edit-work','','edit')}</div></div><div class="detail"><div class="detail-cover">${source?`<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${image(w)}</a>`:image(w)}</div><div><div class="eyebrow">${esc(w.category?t(w.category):t('library'))}</div><div class="work-heading"><h1>${esc(w.title)}</h1><div id="detail-marks">${markUI.detail(w)}</div></div><div class="ratings">${config.dimensions.map(d=>ratingDisplay(w,d)).join('')}</div><div class="row wrap"><span class="tag">${esc(w.language||t('notSpecified'))}</span>${w.pages!=null?`<span class="tag">${esc(t('pages'))}: ${w.pages}</span>`:''}${source?`<a class="btn primary" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${icon('external')}${esc(t('openSource'))}</a>`:''}</div><div class="meta">${['author','circle','tag','series','character'].filter(k=>k==='author'||k==='circle'||w[k].length).map(k=>`<div><label>${esc(t(k))}</label>${w[k].length?`<div class="row wrap">${w[k].map(e=>`<a class="tag ${e.gender}" href="${esc(metadataHref(e,k))}">${esc(displayName(e))}</a>`).join('')}</div>`:`<span class="muted small">${esc(t('notSpecified'))}</span>`}</div>`).join('')}${w.review?`<div><label>${esc(t('review'))}</label><p class="review">${esc(w.review)}</p></div>`:''}${w.links.length?`<div><label>${esc(t('sources'))}</label><div class="source-list">${w.links.map(l=>`<a class="source-link" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${icon('external')}<span>${esc(l.label||l.url)}</span>${l.is_primary?`<span class="tag">${esc(t('primary'))}</span>`:''}</a>`).join('')}</div></div>`:''}</div></div></div>`);images();let markedWork=w;markUI.bind($('#detail-marks'),()=>markedWork,result=>{markedWork=result;currentWork=result},true);$('#edit-work').onclick=()=>nav('/edit/'+id);$('#share-work').onclick=safely(()=>shareWork(w,version))}

const dialog=$('#dialog');
const trashSourceUI=createTrashSourceUI({api,modal,closeModal,dialog,$,$$,esc,t,lang:()=>lang});
function modal(html){dialog.innerHTML=html;dialog.showModal()}
function closeModal(){dialog.close();dialog.innerHTML=''}
async function confirm(title,text,action=t('delete')){return new Promise(resolve=>{modal(`<h2>${esc(title)}</h2><p>${esc(text)}</p><div class="actions">${btn(t('cancel'),'confirm-no')}${btn(action,'confirm-yes','primary')}</div>`);$('#confirm-no').onclick=()=>{closeModal();resolve(false)};$('#confirm-yes').onclick=()=>{closeModal();resolve(true)};dialog.oncancel=()=>resolve(false)})}
const tagUI=createTagUI({$, $$, api, t, esc, btn, modal, closeModal, dialog, error, markLibraryDirty, displayName});
const pawchiveUI=createPawchiveUI({$, $$,modal,closeModal,dialog,esc,toast,lang:()=>lang});
const nhentaiUI=createNhentaiUI({reviewTags:tagUI.reviewTags, $, $$, api, t, esc, btn, modal, closeModal, dialog, error, toast, nav, shell, heading, summaryCards, markLibraryDirty});
const relayCover=url=>isPawchiveCover(url)||isStoreCover(url)||/^https?:\/\/(?:[ab]?tn)\.(?:hitomi\.la|gold-usergeneratedcontent\.net)\//.test(url)||/^https:\/\/t[1234]?\.nhentai\.net\//.test(url)||/^https:\/\/z[23]\.momon-ga\.me\/galleries\//.test(url);
const field=(key,value='',type='text',extra='')=>`<label><span>${esc(t(key))}</span><input data-field="${key}" type="${type}" value="${esc(value)}" ${extra}></label>`;
function blank(){return {title:'',cover:'',category:'',language:'',pages:null,review:'',bought:false,marks:[],author:[],circle:[],tag:[],series:[],character:[],links:[],ratings:{}}}
function scoreEditor(d){const n=draft.ratings[d.id]||0;return `<div><span class="field-title">${d.number}. ${esc(d.name)} <small>(${d.maximum})</small></span><div class="score-editor">${Array.from({length:d.maximum},(_,i)=>`<button type="button" data-score="${d.id}:${i+1}" class="${i<n?'on':''}" aria-label="${esc(d.name)} ${i+1}/${d.maximum}">${symbols[d.symbol][i<n?0:1]}</button>`).join('')}<button type="button" class="clear-score" data-score="${d.id}:0">${esc(t('clearRating'))}</button><small>${n?`${n}/${d.maximum}`:esc(t('unrated'))}</small></div></div>`}
async function edit(id,reuse=false){if(!reuse||!draft){draft=id?await api('works/'+id):blank();baseline=JSON.stringify(draft)}shell('library',`<div class="row between"><button id="cancel-edit" class="btn ghost">${icon('arrow')}${esc(t('cancel'))}</button><span class="muted small">${esc(t('entryHint'))}</span></div><div class="entry-form"><div class="pagehead"><div><h1>${esc(t(id?'editWork':'newWork'))}</h1></div></div><div id="form-error"></div><form id="entry-form" class="stack"><section class="panel form-grid"><div class="title-field">${field('title',draft.title,'text','required class="title-input"')}<div id="bookmark-title-candidates" hidden></div></div><label><span>${esc(t('category'))}</span><select data-field="category"><option value="">${esc(t('notSpecified'))}</option>${Object.keys(config.categories).map(k=>`<option value="${k}" ${draft.category===k?'selected':''}>${esc(t(k))}</option>`).join('')}</select></label><div class="full">${field('cover',draft.cover,'url')}<div id="cover-preview"></div></div>${['author','circle','tag','series','character'].map(k=>`<div class="${k==='tag'?'full':''}"><div class="metadata-field-heading"><span class="field-title">${esc(t(k))}</span><button type="button" class="btn ghost clear-metadata" data-clear-kind="${k}" aria-label="${esc(t('clearMetadata')+' · '+t(k))}" ${draft[k].length?'':'disabled'}>${esc(t('clearMetadata'))}</button></div><div class="chips">${draft[k].map((e,i)=>`<span class="chip"><button type="button" data-edit-chip="${k}:${i}">${esc(displayName(e))}${k==='tag'&&e.gender&&e.gender!=='neutral'?` · ${esc(t(e.gender))}`:''}</button><button type="button" data-remove-chip="${k}:${i}" aria-label="${esc(t('remove'))}">×</button></span>`).join('')}<button type="button" class="add-chip" data-add-kind="${k}">+ ${esc(t('select'))} / +</button></div></div>`).join('')}${field('language',draft.language)}${field('pages',draft.pages??'','number','min="0" step="1"')}</section><section class="panel"><h3>${esc(t('sources'))}</h3><p class="muted small">${esc(t('importHint'))}</p><div id="link-fields">${draft.links.map((l,i)=>`<div class="link-edit"><input type="radio" name="primary" aria-label="${esc(t('primary'))}" data-primary="${i}" ${l.is_primary?'checked':''}><div class="link-fields"><input type="url" data-link="${i}:url" value="${esc(l.url)}" placeholder="https://…" aria-label="${esc(t('workLink'))}"><input data-link="${i}:label" value="${esc(l.label)}" placeholder="${esc(t('sourceLabel'))}" aria-label="${esc(t('sourceLabel'))}"></div><button type="button" class="iconbtn" data-remove-link="${i}" aria-label="${esc(t('remove'))}">${icon('x')}</button></div>`).join('')}</div><div class="row wrap">${btn(t('addLink'),'add-link','','plus')}${btn(t('importMetadata'),'import-metadata','','upload')}</div></section><section class="panel stack"><h3>${esc(t('personal'))}</h3>${config.dimensions.length?config.dimensions.map(scoreEditor).join(''):`<p class="muted small">${esc(t('noRatings'))}</p>`}<div><span class="field-title">${esc(t('marks'))}</span><div id="edit-marks">${markUI.buttons(draft)}</div></div><label><span>${esc(t('review'))}</span><textarea data-field="review">${esc(draft.review)}</textarea></label></section></form></div><div class="bottom-bar edit-actions">${btn(t('save'),'save-work','primary')}${id?btn(t('delete'),'delete-work','danger'):''}</div>`);
 markUI.bind($('#edit-marks'),()=>draft,work=>{draft=work});
 $$('[data-field]').forEach(el=>el.oninput=()=>{const k=el.dataset.field;draft[k]=k==='bought'?el.checked:k==='pages'?(el.value===''?null:Number(el.value)):el.value});
 bindCoverPreview(id);
 bindBookmarkTitles();
 $$('[data-link]').forEach(el=>el.oninput=()=>{const [i,k]=el.dataset.link.split(':');draft.links[i][k]=el.value});
 $$('[data-primary]').forEach(el=>el.onchange=()=>draft.links.forEach((l,i)=>l.is_primary=i===Number(el.dataset.primary)));
 $$('[data-remove-link]').forEach(b=>b.onclick=()=>{draft.links.splice(Number(b.dataset.removeLink),1);if(draft.links.length&&!draft.links.some(l=>l.is_primary))draft.links[0].is_primary=true;edit(id,true)});
 $('#add-link').onclick=()=>{draft.links.push({url:'',label:'',is_primary:!draft.links.length});edit(id,true)};
 $$('[data-remove-chip]').forEach(b=>b.onclick=()=>{const [k,i]=b.dataset.removeChip.split(':');draft[k].splice(Number(i),1);edit(id,true)});
 $$('[data-clear-kind]').forEach(b=>b.onclick=async()=>{const k=b.dataset.clearKind,editing=draft,scroll=window.scrollY;if(!editing[k].length||!await confirm(t('clearMetadataTitle').replace('{kind}',t(k)),t('clearMetadataText'),t('clearMetadata'))||draft!==editing)return;draft[k]=[];await edit(id,true);window.scrollTo(0,scroll)});
 $$('[data-add-kind]').forEach(b=>b.onclick=()=>chooseMetadata(b.dataset.addKind,item=>{if(!draft[b.dataset.addKind].some(e=>e.id===item.id))draft[b.dataset.addKind].push(item);edit(id,true)}));
 $$('[data-edit-chip]').forEach(b=>b.onclick=()=>{
  const [k,index]=b.dataset.editChip.split(':'),i=Number(index),editing=draft;
  if(k!=='tag'){metadataEditor(draft[k][i],k,async eid=>{if(draft!==editing)return;draft[k][i]=await api('entities/'+eid);markLibraryDirty();edit(id,true)});return}
  const apply=item=>{if(draft!==editing)return;draft.tag[i]=item;const seen=new Set();draft.tag=draft.tag.filter(e=>{const key=e.id||e.name+'\0'+(e.gender||'neutral');if(seen.has(key))return false;seen.add(key);return true});edit(id,true)};
  const shared=async()=>{if(draft!==editing)return;draft.tag=await Promise.all(draft.tag.map(e=>e.id?api('entities/'+e.id):e));markLibraryDirty();await edit(id,true)};
  tagUI.workEditor(draft.tag[i],apply,shared);
 });
 $$('[data-score]').forEach(b=>b.onclick=()=>{const [did,v]=b.dataset.score.split(':');if(Number(v))draft.ratings[did]=Number(v);else delete draft.ratings[did];edit(id,true)});
 $('#cancel-edit').onclick=async()=>{if(JSON.stringify(draft)!==baseline&&!await confirm(t('discardTitle'),t('discardText'),t('discard')))return;draft=null;nav(id?'/work/'+id:librarySnapshot?.hash||'/library')};
 $('#entry-form').onsubmit=e=>{e.preventDefault();saveDraft(id)};
 $('#save-work').onclick=()=>saveDraft(id);
 $('#delete-work')?.addEventListener('click',async()=>{if(!await confirm(t('deleteTitle'),t('deleteText')))return;await api('works/'+id,'DELETE');draft=null;markLibraryDirty();toast(t('deleted'));nav(librarySnapshot?.hash||'/library')});
 $('#import-metadata').onclick=()=>interactiveImport(id);
 {
  $('#import-metadata').insertAdjacentHTML('afterend',btn(id?(lang==='ja'?'リンクを既存作品へ統合':'Merge links into an existing entry'):t('linkExisting'),'attach-existing'));
  $('#attach-existing').onclick=async()=>{try{
   if(id){await mergeSavedDraft(id);return}
   const link=draft.links.find(l=>l.is_primary&&l.url)||draft.links.find(l=>l.url);if(!link)return toast(t('addLink'));
   const active=draft,version=routeVersion,current=()=>draft===active&&routeVersion===version;
   const decision=await nhentaiUI.chooseMatch(draft,[]);if(decision?.action!=='attach'||!current())return;
   const result=await trashSourceUI.attach(link.url,decision.target,draft.source_titles||[],current);if(!result||!current())return;draft=null;markLibraryDirty();nav('/work/'+result.id)
  }catch(e){error($('#form-error'),e)}};
 }
}
async function saveDraft(id){const b=$('#save-work');b.disabled=true;try{if(!$('#entry-form').reportValidity())return;const active=draft,version=routeVersion;if(!await trashSourceUI.prepare(active,id,()=>draft===active&&routeVersion===version))return;const result=await api('works'+(id?'/'+id:''),id?'PUT':'POST',draft);draft=null;markLibraryDirty();if(result.warnings.length)toast(t('duplicateSource')+' '+result.warnings.join(', '));else toast(t('saved'));nav('/work/'+result.id)}catch(e){error($('#form-error'),e);$('#form-error').scrollIntoView({block:'center'})}finally{if(b.isConnected)b.disabled=false}}
async function chooseMetadata(kind,onSelect){
 modal(`<div class="metadata-picker-header"><h2>${esc(t('choose'))}: ${esc(t(kind))}</h2><button type="button" id="choose-close" class="iconbtn" aria-label="${esc(t('close'))}" title="${esc(t('close'))}">${icon('x')}</button></div><div class="stack"><input id="choose-query" autofocus placeholder="${esc(t('searchMetadata'))}"><div id="choose-list" class="directory-list"></div></div><div class="actions">${btn(t('createNew'),'choose-new','primary','plus')}</div>`);
 const input=$('#choose-query');let sequence=0,timer;
 const stop=()=>{sequence++;clearTimeout(timer)};
 const dismiss=()=>{stop();closeModal()};
 const paint=async q=>{const seq=++sequence;try{
  const items=await api('entities?kind='+kind+'&q='+encodeURIComponent(q));if(seq!==sequence||!input.isConnected)return;
  $('#choose-list').innerHTML=items.map(e=>`<div class="directory-row"><div><b>${esc(displayName(e))}</b><div class="subtitle">${kind==='tag'&&e.gender!=='neutral'?esc(t(e.gender)):esc(e.aliases.join(', '))}</div></div><button type="button" class="btn" data-choose="${e.id}">${esc(t('select'))}</button></div>`).join('')||`<p class="muted">${esc(t('noneMetadata'))}</p>`;
  $$('[data-choose]').forEach(b=>b.onclick=()=>{const item=items.find(e=>e.id===b.dataset.choose);dismiss();onSelect(item)});
 }catch(e){if(seq===sequence&&input.isConnected)error($('#choose-list'),e)}};
 input.oninput=e=>{clearTimeout(timer);timer=setTimeout(()=>paint(e.target.value),180)};
 $('#choose-close').onclick=dismiss;dialog.oncancel=stop;
 $('#choose-new').onclick=()=>{const name=input.value.trim();dismiss();metadataEditor(null,kind,async eid=>{const entity=await api('entities/'+eid);onSelect(entity)},name)};
 await paint('');
}
async function metadataEditor(item,kind,onSave,initialName=''){
 if(kind==='tag')return tagUI.editor(item,onSave,item?undefined:{name:initialName});
 if(dialog.open)closeModal();
 modal(`<h2>${esc(t(item?'edit':'newMetadata'))}: ${esc(t(kind))}</h2><p>${esc(t('sharedWarning'))}</p><div id="metadata-error"></div><form id="metadata-form" class="stack"><label><span>${esc(t('canonicalName'))}</span><input id="metadata-name" required value="${esc(item?.name??initialName)}"></label>${kind==='tag'?`<label><span>${esc(t('gender'))}</span><select id="metadata-gender">${['neutral','female','male'].map(g=>`<option value="${g}" ${(item?.gender||'neutral')===g?'selected':''}>${esc(t(g))}</option>`).join('')}</select></label>`:''}<label><span>${esc(t('aliases'))}</span><textarea id="metadata-aliases">${esc(item?.aliases?.join('\n')||'')}</textarea></label><label><span>${esc(t('displayAlias'))}</span><select id="metadata-display"></select><small class="muted">${esc(t('displayAliasHint'))}</small></label><label><span>${esc(t('sortReading'))}</span><input id="metadata-reading" value="${esc(item?.sort_reading||'')}"><small class="muted">${esc(t('sortReadingHint'))}</small></label><div class="actions">${btn(t('cancel'),'metadata-cancel')}<button class="btn primary" type="submit">${esc(t('save'))}</button></div></form>`);
 let selected=item?.display_alias||'';
 const aliases=()=>[...new Set($('#metadata-aliases').value.split('\n').map(a=>a.trim()).filter(Boolean))];
 function options(){const names=aliases();if(!names.includes(selected))selected='';$('#metadata-display').innerHTML=`<option value="">${esc($('#metadata-name').value.trim()||t('canonicalName'))} (${esc(t('canonicalName'))})</option>`+names.map(a=>`<option value="${esc(a)}" ${a===selected?'selected':''}>${esc(a)}</option>`).join('')}
 options();$('#metadata-display').onchange=e=>selected=e.target.value;
 $('#metadata-name').oninput=options;$('#metadata-aliases').oninput=options;
 $('#metadata-cancel').onclick=closeModal;
 $('#metadata-form').onsubmit=async e=>{e.preventDefault();try{const result=await api('entities'+(item?.id?'/'+item.id:''),item?.id?'PUT':'POST',{kind,name:$('#metadata-name').value,gender:$('#metadata-gender')?.value||'neutral',aliases:aliases(),display_alias:$('#metadata-display').value,sort_reading:$('#metadata-reading').value});markLibraryDirty();closeModal();onSave(result.id)}catch(e){error($('#metadata-error'),e)}};
}
function summaryCards(matches){return matches.map(w=>`<div class="import-match"><a href="#${w.deleted_at?'/trash':'/work/'+esc(w.id)}" target="_blank" rel="noopener"><b>${esc(w.title)}${w.deleted_at?' · '+esc(t('trash')):''}</b></a><small>${esc(t('author'))}: ${esc((w.authors||[]).join(', ')||t('notSpecified'))}</small><small>${esc(w.primary_url||w.source_url||t('notSpecified'))}</small></div>`).join('')}
function bindBookmarkTitles(){
 const input=$('[data-field="title"]'),panel=$('#bookmark-title-candidates');
 const editing=draft;let selecting=false;
 const names=[...new Set([...(draft.bookmark_names||[]),...(draft.source_titles||[])].map(s=>s.trim()).filter(Boolean))];
 if(!names.length)return;
 panel.innerHTML=`<small class="muted">${esc(t(draft.bookmark_names?.length?'bookmarkTitleCandidates':'sourceTitleCandidates'))}</small>`+names.map((name,i)=>`<button type="button" class="btn ghost" data-bookmark-title="${i}">${esc(name)}</button>`).join('');
 input.addEventListener('focus',()=>panel.hidden=false);
 input.addEventListener('blur',e=>{if(!selecting&&!panel.contains(e.relatedTarget))panel.hidden=true});
 panel.addEventListener('focusout',e=>{if(!selecting&&e.relatedTarget!==input&&!panel.contains(e.relatedTarget))panel.hidden=true});
 $$('[data-bookmark-title]',panel).forEach(b=>{
  const apply=()=>{selecting=false;if(draft!==editing||!input.isConnected)return;input.value=names[Number(b.dataset.bookmarkTitle)];editing.title=input.value;input.focus({preventScroll:true})};
  b.onpointerdown=e=>{if(e.button!==0)return;selecting=true;e.preventDefault()};
  b.onpointerup=e=>{if(e.button!==0)return;e.preventDefault();apply()};
  b.onpointercancel=()=>{selecting=false;if(document.activeElement!==input&&!panel.contains(document.activeElement))panel.hidden=true};
  b.onclick=apply;
 });
}
async function interactiveImport(id,sourceDraft=false){
 const activeDraft=draft,importVersion=routeVersion;
 const valid=draft.links.filter(l=>l.url);if(!valid.length){toast(t('addLink'));return}
 let link=valid.find(l=>l.is_primary)||valid[0];
 if(valid.length>1){const choice=await new Promise(resolve=>{modal(`<h2>${esc(t('importMetadata'))}</h2><div class="stack">${valid.map((l,i)=>`<button class="btn" data-import-link="${i}">${esc(l.label||l.url)}</button>`).join('')}</div><div class="actions">${btn(t('cancel'),'import-link-cancel')}</div>`);$$('[data-import-link]').forEach(b=>b.onclick=()=>{closeModal();resolve(valid[Number(b.dataset.importLink)])});$('#import-link-cancel').onclick=()=>{closeModal();resolve(null)};dialog.oncancel=()=>resolve(null)});if(!choice)return;link=choice}
 if(draft!==activeDraft||routeVersion!==importVersion)return;
 const b=$('#import-metadata');b.disabled=true;b.textContent=t('loading');
 try{
  if(!await trashSourceUI.prepare(activeDraft,id,()=>draft===activeDraft&&routeVersion===importVersion,link))return;
  if(!link.is_primary&&activeDraft.trash_sources?.some(c=>c.url===link.url)){await edit(id,true);toast(t('importDone'));return;}
  const incoming=await api('import','POST',{url:link.url,exclude:id||'',trash_sources:(draft.trash_sources||[]).filter(c=>c.url===link.url)});
  const current=()=>draft===activeDraft&&routeVersion===importVersion;
  if(!current())return;
  if(['mixed','uncertain'].includes(incoming.media_kind)){
   if(!await confirm(lang==='ja'?'動画を含む投稿': 'Post contains video',lang==='ja'?'画像と動画が混在しているか、内容を判定できない投稿です。取り込みますか？':'This post contains video and images, or its contents are uncertain. Import it?',lang==='ja'?'取り込む':'Import')||!current())return;
  }
  for(const ambiguity of incoming.ambiguities||[]){
   const selected=await new Promise(resolve=>{modal(`<h2>${esc(t('selectAlias'))}</h2><p>${esc(ambiguity.name)}</p><div class="stack">${ambiguity.choices.map(c=>`<button class="btn" data-alias-id="${c.id}">${esc(displayName(c))}${c.gender&&c.gender!=='neutral'?' · '+esc(t(c.gender)):''}</button>`).join('')}</div>${btn(t('cancel'),'alias-cancel')}`);$$('[data-alias-id]').forEach(b=>b.onclick=()=>{closeModal();resolve(ambiguity.choices.find(c=>c.id===b.dataset.aliasId))});$('#alias-cancel').onclick=()=>{closeModal();resolve(null)};dialog.oncancel=()=>resolve(null)});
   if(!selected||!current())return;
   for(let i=0;i<incoming[ambiguity.kind].length;i++){const e=incoming[ambiguity.kind][i];if(e.name===ambiguity.name&&(e.gender||'neutral')===ambiguity.gender)incoming[ambiguity.kind][i]=selected}
  }
  const originals=incoming.original_links?.length?await pawchiveUI.chooseOriginals(incoming,draft,current):[];
  if(!originals||!current())return;
  let titleReviewed=false;
  const matchChoices=[...new Map([...(incoming.title_matches||[]),...(incoming.cross_candidates||[])].map(w=>[w.id,w])).values()];
  if(!id&&matchChoices.length){
   const decision=await nhentaiUI.chooseMatch(incoming,matchChoices);
   if(!decision||!current())return;
   if(decision.action==='attach'){
    const result=await trashSourceUI.attach(link.url,decision.target,incoming.source_titles||[incoming.title],current,originals);if(!result||!current())return;
    if(result.original_warnings?.length)toast(t('originalSkipped')+': '+result.original_warnings.length);
    draft=null;markLibraryDirty();nav('/work/'+result.id);return;
   }
   titleReviewed=true;
  }
  if(!hasImportedChanges(draft,incoming)&&!originals.length){toast(t('importNoChanges')+(incoming.warnings?.length?' · '+incoming.warnings.map(w=>localizeError(w,lang)).join('; '):''));return}
  if((!titleReviewed&&incoming.title_matches?.length)||(!sourceDraft&&incoming.related_matches?.length)){
   const accepted=await new Promise(resolve=>{modal(`<h2>${esc(t('importWarnings'))}</h2>${!titleReviewed&&incoming.title_matches?.length?`<p>${esc(t('sameTitleHint'))}</p>${summaryCards(incoming.title_matches)}`:''}${!sourceDraft&&incoming.related_matches?.length?`<p>${esc(t('sourceRelatedHint'))}</p>${summaryCards(incoming.related_matches)}`:''}<div class="actions">${btn(t('cancel'),'import-warning-cancel')}${btn(t('continueImport'),'import-warning-continue','primary')}</div>`);$('#import-warning-cancel').onclick=()=>{closeModal();resolve(false)};$('#import-warning-continue').onclick=()=>{closeModal();resolve(true)};dialog.oncancel=()=>resolve(false)});
   if(!accepted||!current())return;
  }
  const singles=['title','cover','category','language','pages'];
  const conflicts=singles.filter(k=>draft[k]!==''&&draft[k]!=null&&incoming[k]!==''&&incoming[k]!=null&&draft[k]!==incoming[k]);
  const multi=metadataKinds.filter(k=>draft[k]?.length&&incoming[k]?.length&&!sameMetadataSet(draft[k],incoming[k]));
  let choices={replacements:[],modes:{}};
  if(conflicts.length||multi.length){
   choices=await new Promise(resolve=>{
    const names=items=>items.map(e=>displayName(e)+(e.gender&&e.gender!=='neutral'?' ('+t(e.gender)+')':'')).join(', ');
    modal(`<h2>${esc(t('replaceTitle'))}</h2><p>${esc(t('replaceText'))}</p><div class="stack">${conflicts.map(k=>`<label class="check-label"><input type="checkbox" data-replace="${k}"><span><b>${esc(t(k))}</b><br><small>${esc(draft[k])} → ${esc(incoming[k])}</small></span></label>`).join('')}${multi.map(k=>`<div class="import-field"><label><span>${esc(t(k))}</span><select data-import-mode="${k}">${['merge','overwrite','keep'].map(m=>`<option value="${m}">${esc(t('import_'+m))}</option>`).join('')}</select></label><small>${esc(t('existingValues'))}: ${esc(names(draft[k]))}</small><small>${esc(t('incomingValues'))}: ${esc(names(incoming[k]))}</small></div>`).join('')}</div><div class="actions">${btn(t('cancel'),'replacement-cancel')}${btn(t('apply'),'replacement-apply','primary')}</div>`);
    $('#replacement-cancel').onclick=()=>{closeModal();resolve(null)};
    $('#replacement-apply').onclick=()=>{const result={replacements:$$('[data-replace]:checked').map(b=>b.dataset.replace),modes:Object.fromEntries($$('[data-import-mode]').map(el=>[el.dataset.importMode,el.value]))};closeModal();resolve(result)};
    dialog.oncancel=()=>resolve(null);
   });
   if(!choices||!current())return;
  }
  const updated=applyImported(draft,incoming,choices.replacements,choices.modes);
  if(!hasImportedChanges(draft,updated)&&!originals.length){toast(t('importNoChanges'));return}
  Object.assign(draft,updated);
  if(originals.length)draft.links=mergeOriginals(draft.links,originals);
  if(incoming.source_label&&!link.label?.trim())link.label=incoming.source_label;
  draft.source_titles=[...new Set([...(draft.source_titles||[]),...(incoming.source_titles||[])])];
  toast(t('importDone')+(incoming.warnings?.length?' · '+incoming.warnings.map(w=>localizeError(w,lang)).join('; '):''));edit(id,true);
 }catch(e){
  if(draft===activeDraft&&routeVersion===importVersion){
   if(e.matches?.length){modal(`<h2>${esc(t('duplicate_url'))}</h2><p>${esc(t('registeredSourceHint'))}</p>${summaryCards(e.matches)}<div class="actions">${btn(t('close'),'registered-close')}</div>`);$('#registered-close').onclick=closeModal}
   else error($('#form-error'),e);
  }
 }finally{if(b.isConnected){b.disabled=false;b.textContent=t('importMetadata')}}
}

let metadataKind='tag',metadataSort='name_asc',metadataFilter='';
async function metadata(){
 clearTimeout(metadata.timer);
 shell('metadata',heading(t('metadataTitle'),t('metadataHint'),btn(t('newMetadata'),'metadata-add','primary','plus'))+`<div class="directory-tabs">${['tag','author','circle','series','character'].map(k=>`<button data-kind="${k}" class="${k===metadataKind?'active':''}">${esc(t(k))}</button>`).join('')}</div><div class="toolbar metadata-toolbar"><div class="searchbox search-wrap">${icon('search')}<input id="metadata-search" aria-label="${esc(t('searchMetadata'))}" placeholder="${esc(t('searchMetadata'))}" value="${esc(metadataFilter)}"></div><select id="metadata-sort" aria-label="${esc(t('sortMetadata'))}">${['name_asc','name_desc','uses_desc','uses_asc','newest','oldest'].map(k=>`<option value="${k}" ${k===metadataSort?'selected':''}>${esc(t('meta_'+k))}</option>`).join('')}</select></div><div id="metadata-error-page"></div><div class="results-line" id="metadata-count"></div><div id="directory" class="directory-list"></div><div id="metadata-more"></div>`);
 $$('[data-kind]').forEach(b=>b.onclick=()=>{metadataKind=b.dataset.kind;metadata()});
 $('#metadata-add').onclick=()=>metadataEditor(null,metadataKind,()=>metadata());
 const directory=$('#directory'),kind=metadataKind;let sequence=0,items=[],count=0;
 async function load(append=false){
  const seq=++sequence;
  try{
   const result=await api('entities?'+new URLSearchParams({kind,q:metadataFilter,sort:metadataSort,paged:1,limit:100,offset:append?items.length:0}));
   if(seq!==sequence||!directory.isConnected)return;
   items=append?[...items,...result.items]:result.items;count=result.total;
   $('#metadata-error-page').innerHTML='';$('#metadata-count').textContent=`${count.toLocaleString()} · ${items.length} ${t('showing')}`;
   directory.innerHTML=items.map(e=>`<div class="directory-row"><div class="directory-info"><div class="name"><a class="metadata-name-link" href="${esc(metadataHref(e,kind))}">${esc(displayName(e))}</a> ${kind==='tag'&&e.gender!=='neutral'?`<span class="tag ${e.gender}">${esc(t(e.gender))}</span>`:''}</div><div class="subtitle">${e.uses} ${esc(t('uses'))}${e.display_alias?' · '+esc(e.name):''}${e.aliases.some(a=>a!==e.display_alias)?' · '+esc(e.aliases.filter(a=>a!==e.display_alias).join(', ')):''}</div></div><div class="row"><button type="button" class="btn" data-edit-meta="${e.id}">${esc(t('edit'))}</button><button class="iconbtn" data-delete-meta="${e.id}" aria-label="${esc(t('delete'))}">${icon('x')}</button></div></div>`).join('')||`<div class="empty"><h2>${esc(t('noneMetadata'))}</h2><p>${esc(t('emptyDirectory'))}</p></div>`;
   $$('[data-edit-meta]',directory).forEach(b=>b.onclick=()=>{const item=items.find(e=>e.id===b.dataset.editMeta);metadataEditor(item,kind,()=>metadata());if(kind==='tag')return;const actions=$('.actions',dialog),mergeBtn=document.createElement('button');mergeBtn.type='button';mergeBtn.className='btn';mergeBtn.textContent=t('merge');actions.prepend(mergeBtn);mergeBtn.onclick=()=>mergeEditor(item,items)});
   $$('[data-delete-meta]',directory).forEach(b=>b.onclick=async()=>{const e=items.find(e=>e.id===b.dataset.deleteMeta);if(await confirm(t('deleteMetadata'),`${e.uses} ${t('uses')}. ${t('deleteMetadataText')}`)){try{await api('entities/'+e.id,'DELETE');markLibraryDirty();load()}catch(err){if(directory.isConnected)error($('#metadata-error-page'),err)}}});
   $('#metadata-more').innerHTML=items.length<count?btn(t('loadMore'),'metadata-load-more','loadmore'):'';
   $('#metadata-load-more')?.addEventListener('click',()=>load(true));
  }catch(e){if(seq===sequence&&directory.isConnected)error($('#metadata-error-page'),e)}
 }
 $('#metadata-search').oninput=e=>{metadataFilter=e.target.value;++sequence;clearTimeout(metadata.timer);metadata.timer=setTimeout(()=>load(),180)};
 $('#metadata-sort').onchange=e=>{metadataSort=e.target.value;load()};await load();
}
function mergeEditor(item,items){tagUI.mergeEditor(item,()=>metadata())}

async function ratingPage(){await refreshConfig();shell('ratings',heading(t('ratingsTitle'),t('ratingsHint'),btn(t('newDimension'),'dimension-add','primary','plus'))+`<div class="notice">${esc(t('dimensionWarning'))}</div><div class="directory-list" id="dimensions"></div>`);$('#dimensions').innerHTML=config.dimensions.map(d=>`<div class="directory-row"><div class="row"><div class="dimension-number">${d.number}</div><div><div class="name">${esc(d.name)}</div><div class="subtitle">rating${d.number} · 1–${d.maximum} · ${esc(t(d.symbol))}${d.gallery?' · '+esc(t('galleryVisible')):''}</div></div></div><div class="row"><button class="btn" data-edit-dimension="${d.id}">${esc(t('edit'))}</button><button class="iconbtn" data-delete-dimension="${d.id}" aria-label="${esc(t('delete'))}">${icon('x')}</button></div></div>`).join('')||`<div class="empty"><div class="empty-icon">${icon('star')}</div><h2>${esc(t('noRatings'))}</h2></div>`;$('#dimension-add').onclick=()=>dimensionEditor();$$('[data-edit-dimension]').forEach(b=>b.onclick=()=>dimensionEditor(config.dimensions.find(d=>d.id===b.dataset.editDimension)));$$('[data-delete-dimension]').forEach(b=>b.onclick=async()=>{if(await confirm(t('deleteDimension'),t('deleteDimensionText'))){await api('dimensions/'+b.dataset.deleteDimension,'DELETE');ratingPage()}})}
function dimensionEditor(d){
 modal(`<h2>${esc(t(d?'edit':'newDimension'))}${d?' · rating'+d.number:''}</h2><div id="dimension-error"></div><form id="dimension-form" class="stack"><label><span>${esc(t('name'))}</span><input id="dim-name" required value="${esc(d?.name||'')}"></label><label><span>${esc(t('maxScore'))}</span><input type="number" min="2" max="10" step="1" id="dim-max" required value="${d?.maximum||5}"></label><label><span>${esc(t('symbol'))}</span><select id="dim-symbol">${config.symbols.map(s=>`<option value="${s}" ${d?.symbol===s?'selected':''}>${symbols[s][0]} ${esc(t(s))}</option>`).join('')}</select></label><label class="check-label"><input type="checkbox" id="dim-gallery" ${d?.gallery?'checked':''}>${esc(t('galleryVisible'))}</label><div id="dimension-preview" aria-live="polite"></div><div class="actions">${btn(t('cancel'),'dim-cancel')}<button id="dim-save" class="btn primary" type="submit">${esc(t('save'))}</button></div></form>`);
 const form=$('#dimension-form'),maximumInput=$('#dim-max'),previewBox=$('#dimension-preview'),save=$('#dim-save'),errorBox=$('#dimension-error');
 const editorVersion=routeVersion;let preview=null,busy=false,needsPreview=false;
 const active=()=>form.isConnected&&dialog.open&&editorVersion===routeVersion;
 function resetPreview(){preview=null;previewBox.innerHTML='';save.textContent=t(d&&(needsPreview||Number(maximumInput.value)!==d.maximum)?'previewConversion':'save')}
 maximumInput.oninput=resetPreview;resetPreview();$('#dim-cancel').onclick=closeModal;
 form.onsubmit=async e=>{
  e.preventDefault();if(busy)return;
  const data={name:$('#dim-name').value,maximum:Number(maximumInput.value),symbol:$('#dim-symbol').value,gallery:$('#dim-gallery').checked};
  busy=true;save.disabled=true;errorBox.innerHTML='';
  try{
   if(d&&(needsPreview||data.maximum!==d.maximum)&&!preview){
    const result=await api('dimensions/'+d.id+'/preview','POST',{maximum:data.maximum});
    if(!active()||Number(maximumInput.value)!==data.maximum)return;
    preview=result;
    previewBox.innerHTML=`<h3>${esc(t('conversionTitle'))} · ${result.old_maximum} → ${result.maximum}</h3><p>${esc(t('conversionRule'))}</p><div class="conversion-table-wrap"><table class="conversion-table"><thead><tr><th>${esc(t('conversionBefore'))}</th><th>${esc(t('conversionAfter'))}</th><th>${esc(t('works'))}</th></tr></thead><tbody>${result.rows.map(r=>`<tr><td>${r.old}/${result.old_maximum}</td><td>${r.new}/${result.maximum}</td><td>${r.count}</td></tr>`).join('')}</tbody></table></div><p>${esc(t('conversionSummary').replace('{rated}',result.rated).replace('{changed}',result.changed))}</p><div class="notice">${esc(t('conversionLoss'))}</div>`;
    save.textContent=t('confirmConversion');previewBox.scrollIntoView({block:'nearest'});return;
   }
   if(preview)data.conversion_signature=preview.signature;
   await api('dimensions'+(d?'/'+d.id:''),d?'PUT':'POST',data);
   markLibraryDirty();if(active()){closeModal();ratingPage()}
  }catch(e){if(active()){needsPreview=!!d;resetPreview();error(errorBox,e)}}
  finally{busy=false;if(active())save.disabled=false}
 }
}

let bookmarkItems=[],selectedBookmarks=new Set();
async function imports(){shell('imports',heading(t('importsTitle'),t('importsHint'))+`${sourceTools()}${pawchiveUI.tools()}<div id="nhentai-import"></div><section class="panel"><label><span>${esc(t('bookmarkTitlePreference'))}</span><select id="bookmark-title-mode"><option value="source">${esc(t('sourceTitleFirst'))}</option><option value="bookmark">${esc(t('bookmarkTitleFirst'))}</option></select><small class="muted">${esc(t('bookmarkTitlePreferenceHint'))}</small></label>${nhentaiUI.modes('bookmark-tag-mode','nhentaiBatch')}${pawchiveUI.batchOption()}</section><label class="file-drop">${icon('upload')}<h3>${esc(t('upload'))}</h3><span>${esc(t('uploadHint'))}</span><input id="bookmark-file" type="file" accept=".html,.htm,text/html"></label><div id="import-error"></div><div id="bookmark-preview"></div><h2 class="results-line">${esc(t('jobs'))}</h2><div id="jobs" class="directory-list"></div>`);bindSourceTools();pawchiveUI.bind();$('#bookmark-original-links').checked=localStorage.getItem('folio-bookmark-original-links')!=='false';$('#bookmark-original-links').onchange=e=>localStorage.setItem('folio-bookmark-original-links',String(e.target.checked));$('#bookmark-title-mode').value=localStorage.getItem('folio-bookmark-title-mode')==='bookmark'?'bookmark':'source';$('#bookmark-title-mode').onchange=e=>localStorage.setItem('folio-bookmark-title-mode',e.target.value);$('#bookmark-file').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>12*1024*1024)throw Error(t('uploadHint'));bookmarkItems=await api('bookmarks','POST',{html:await f.text()});selectedBookmarks=new Set(bookmarkItems.map((b,i)=>b.supported&&!b.duplicate?i:-1).filter(i=>i>=0));paintBookmarkPreview()}catch(e){error($('#import-error'),e)}};await loadJobs();await nhentaiUI.mount($('#nhentai-import'))}
function paintBookmarkPreview(){const folders=[...new Set(bookmarkItems.map(b=>b.folder))];$('#bookmark-preview').innerHTML=`<section class="panel stack"><div class="row between"><h3>${esc(t('preview'))} · ${bookmarkItems.length}</h3><span id="selected-count" class="muted small"></span></div><div class="row wrap">${btn(t('selectAll'),'select-all')}${btn(t('selectNone'),'select-none')}<select id="folder-filter" aria-label="${esc(t('folder'))}"><option value="*">${esc(t('allFolders'))}</option>${folders.map(f=>`<option value="${esc(f)}">${esc(f||'/')}</option>`).join('')}</select></div><div class="bookmark-list" id="bookmark-list"></div>${btn(t('startImport'),'start-job','primary','upload')}</section>`;const paint=()=>{const f=$('#folder-filter').value;$('#bookmark-list').innerHTML=bookmarkItems.map((b,i)=>({b,i})).filter(({b})=>f==='*'||b.folder===f).map(({b,i})=>`<label class="bookmark-row"><input type="checkbox" data-bookmark="${i}" ${selectedBookmarks.has(i)?'checked':''} ${!b.supported||b.duplicate?'disabled':''}><div class="info">${esc(b.label||b.url)}<small>${esc(b.folder)}<br>${esc(b.url)}</small></div><span class="status">${esc(t(b.duplicate?'duplicate':b.related?.length?'relatedPages':b.supported?'supported':'unsupported'))}</span></label>`).join('');$('#selected-count').textContent=`${selectedBookmarks.size} / ${bookmarkItems.length}`;$$('[data-bookmark]').forEach(el=>el.onchange=()=>{const i=Number(el.dataset.bookmark);el.checked?selectedBookmarks.add(i):selectedBookmarks.delete(i);$('#selected-count').textContent=`${selectedBookmarks.size} / ${bookmarkItems.length}`})};$('#folder-filter').onchange=paint;$('#select-all').onclick=()=>{const f=$('#folder-filter').value;bookmarkItems.forEach((b,i)=>{if(b.supported&&!b.duplicate&&(f==='*'||f===b.folder))selectedBookmarks.add(i)});paint()};$('#select-none').onclick=()=>{const f=$('#folder-filter').value;bookmarkItems.forEach((b,i)=>{if(f==='*'||f===b.folder)selectedBookmarks.delete(i)});paint()};$('#start-job').onclick=async()=>{if(!selectedBookmarks.size)return;try{const job=await api('jobs','POST',{items:[...selectedBookmarks].map(i=>bookmarkItems[i]),title_mode:$('#bookmark-title-mode').value,tag_mode:$('#bookmark-tag-mode').value,include_original_links:$('#bookmark-original-links').checked});nav('/job/'+job.id)}catch(e){error($('#import-error'),e)}};paint()}
async function loadJobs(){const list=await api('jobs');if(!$('#jobs'))return;$('#jobs').innerHTML=list.map(j=>`<a class="directory-row" href="#/job/${j.id}"><div><div class="name">${new Date(j.created).toLocaleString(lang)}</div><div class="subtitle">${Object.values(j.counts).reduce((a,b)=>a+b,0)} ${esc(t('works'))} · ${j.counts.added||0} ${esc(t('added'))}</div></div><span class="status">${esc(t(j.status))}</span></a>`).join('')||`<p class="muted small">${esc(t('noJobs'))}</p>`;jobTimer=setTimeout(loadJobs,3000)}
async function jobPage(id){await nhentaiUI.jobPage(id)}

function sourceTools(){return `<section class="panel stack"><h3>${esc(t('sourceTools'))}</h3><p>${esc(t('sourceToolsHint'))}</p><p class="muted small">${esc(t('sourceLookupHint'))}</p><label><span>${esc(t('folioAddress'))}</span><input id="folio-address" type="url" value="${esc(localStorage.getItem('folio-source-address')||location.origin)}"></label><p id="bookmark-warning" class="notice small" hidden>${esc(t('bookmarkLocalWarning'))}</p><div id="bookmark-error"></div><label><span>${esc(t('bookmarkCode'))}</span><textarea id="bookmark-code" readonly rows="4" spellcheck="false"></textarea></label><div>${btn(t('copyBookmark'),'copy-bookmark')}</div><p class="muted small">${esc(t('bookmarkHelp'))}</p><p class="muted small">${esc(t('desktopBookmarkHelp'))} <a id="folio-bookmark" draggable="true">Folio</a></p><form id="source-open-form" class="stack"><label><span>${esc(t('sourcePaste'))}</span><input id="source-url" type="url" required placeholder="https://hitomi.la/reader/123.html#7"></label><div><button type="submit" class="btn primary">${esc(t('openInFolio'))}</button></div></form></section>`}
function bindSourceTools(){
 const paint=()=>{try{const base=new URL($('#folio-address').value),code=bookmarklet(base.href);$('#bookmark-code').value=code;$('#folio-bookmark').href=code;$('#copy-bookmark').disabled=false;$('#bookmark-error').innerHTML='';$('#bookmark-warning').hidden=!['localhost','127.0.0.1','[::1]'].includes(base.hostname);localStorage.setItem('folio-source-address',base.origin)}catch(e){$('#bookmark-code').value='';$('#folio-bookmark').removeAttribute('href');$('#copy-bookmark').disabled=true;error($('#bookmark-error'),e)}};
 paint();$('#folio-address').oninput=paint;
 $('#folio-bookmark').onclick=e=>{e.preventDefault();toast(t('bookmarkHelp'))};
 $('#copy-bookmark').onclick=async()=>{const field=$('#bookmark-code');try{if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(field.value)}else{field.focus();field.select();if(!document.execCommand('copy'))throw Error('copy')}toast(t('bookmarkCopied'))}catch{field.focus();field.select();toast(t('copyManually'))}};
 $('#source-open-form').onsubmit=e=>{e.preventDefault();nav('/source?'+new URLSearchParams({url:$('#source-url').value.trim()}))};
}
async function openSource(version){
 const value=route().params.get('url')||'';
 shell('library',heading(t('sourceChecking'),t('sourceToolsHint')));
 const result=await api('source-check','POST',{url:value});if(version!==routeVersion)return;
 if(result.match==='exact'&&result.matches.length&&result.matches.every(w=>w.deleted_at)){await showTrashedSource(result.matches,value);return}
 if(result.match==='gallery'){
 const choice=await new Promise(resolve=>{modal(`<h2>${esc(t('sourceRelatedTitle'))}</h2><p>${esc(t('sourceRelatedHint'))}</p><div class="stack source-related-list">${result.matches.map(w=>`<button type="button" class="btn source-related-item" data-source-work="${w.id}"><b>${esc(w.title)}</b><small>${esc(w.source_url)}${w.deleted_at?' · '+esc(t('trash')):''}</small></button>`).join('')}</div><div class="actions wrap">${btn(t('cancel'),'source-cancel')}${btn(t('sourceImportNew'),'source-import-new','primary')}</div>`);$$('[data-source-work]').forEach(b=>b.onclick=()=>{closeModal();resolve(b.dataset.sourceWork)});$('#source-cancel').onclick=()=>{closeModal();resolve(null)};$('#source-import-new').onclick=()=>{closeModal();resolve('new')};dialog.oncancel=()=>resolve(null)});
 if(version!==routeVersion)return;if(choice===null){nav('/library');return}if(choice!=='new'){const chosen=result.matches.find(w=>w.id===choice);if(chosen?.deleted_at)await showTrashedSource([chosen]);else nav('/work/'+choice);return}
 }else if(result.matches.length===1){if(result.matches[0].deleted_at)await showTrashedSource(result.matches);else nav('/work/'+result.matches[0].id);return}
 else if(result.matches.length){shell('library',heading(t('sourceMatches'),t('sourceMatchesHint'))+`<div class="directory-list">${result.matches.map(w=>`<a class="directory-row" href="#${w.deleted_at?'/trash':'/work/'+w.id}">${esc(w.title)}${w.deleted_at?' · '+esc(t('trash')):''}</a>`).join('')}</div>`);return}
 draft=blank();baseline=JSON.stringify(draft);draft.links=[{url:result.url,label:'',is_primary:true}];
 history.replaceState(null,'','#/new');previousHash=location.hash;
 await edit(null,true);if(version!==routeVersion)return;await interactiveImport(null,true);
}
function settings(){shell('settings',heading(t('settingsTitle'),t('settingsHint'))+`<div class="stack"><section class="panel stack"><h3>${esc(t('appearance'))}</h3><div class="row wrap">${btn(t('darkTheme'),'theme-dark',theme==='dark'?'primary':'')}${btn(t('lightTheme'),'theme-light',theme==='light'?'primary':'')}</div></section><section class="panel stack"><h3>${esc(t('localServer'))}</h3><p class="muted small">${esc(t('serverHint'))}</p><code>${esc(location.origin)}</code></section><section class="panel stack"><h3>${esc(t('backup'))}</h3><p class="muted small">${esc(t('backupHint'))}</p><div class="row wrap">${btn(t('downloadBackup'),'backup-download','primary')}${btn(t('backup'),'backup-now','','upload')}</div><div id="backup-result"></div></section><section class="panel stack"><h3>${esc(t('uiLanguage'))}</h3><div class="row">${btn(t('english'),'lang-en',lang==='en'?'primary':'')}${btn(t('japanese'),'lang-ja',lang==='ja'?'primary':'')}</div></section>${markUI.settings()}</div>`);markUI.bindSettings(document);$('#theme-dark').onclick=()=>setTheme('dark');$('#theme-light').onclick=()=>setTheme('light');$('#lang-en').onclick=()=>switchLanguage('en');$('#lang-ja').onclick=()=>switchLanguage('ja');$('#backup-download').onclick=async()=>{const button=$('#backup-download');button.disabled=true;$('#backup-result').textContent=t('backupDownloading');try{const r=await fetch('/api/backup/download',{method:'POST',headers:{'Content-Type':'application/json','X-Library-Token':config.token},body:'{}'});if(!r.ok){const body=await r.json();throw new Error(body.error||t('error'))}const blob=await r.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=r.headers.get('Content-Disposition')?.match(/filename="(library-[0-9-]+\.(?:sqlite3|zip))"/)?.[1]||'folio-backup.zip';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);$('#backup-result').textContent=t('backupDownloaded')}catch(e){error($('#backup-result'),e)}finally{button.disabled=false}};$('#backup-now').onclick=async()=>{try{const r=await api('backup','POST',{});$('#backup-result').textContent=t('backupDone')+': '+r.file}catch(e){error($('#backup-result'),e)}}}
let previousHash=location.hash||'#/library', restoring=false;
async function render(reuse=false){updatePageTitle();releasePreview();const version=++routeVersion;clearTimeout(jobTimer);try{await refreshConfig();if(version!==routeVersion)return;const {path}=route();if(path==='/library'){draft=null;await library()}else if(path.startsWith('/work/')){draft=null;await detail(path.split('/')[2])}else if(path==='/source'){draft=null;await openSource(version)}else if(path==='/new'||path.startsWith('/edit/'))await edit(path==='/new'?null:path.split('/')[2],reuse);else{draft=null;if(path==='/metadata')await metadata();else if(path==='/ratings')await ratingPage();else if(path==='/trash')await trashPage();else if(path==='/history')await historyPage();else if(path==='/saved-searches')await savedSearchPage();else if(path==='/share')await sharedPage(version);else if(path==='/imports')await imports();else if(path.startsWith('/job/'))await jobPage(path.split('/')[2]);else if(path==='/settings'){settings();mountInstallTools()}else nav('/library')}if(path!=='/library')scrollTo(0,0)}catch(e){shell('library',`<div class="error">${esc(e.message)}</div>${btn(t('retry'),'retry-render')}`);$('#retry-render').onclick=()=>render(reuse)}}
window.addEventListener('hashchange',async()=>{if(restoring){restoring=false;return}if(draft&&JSON.stringify(draft)!==baseline){const target=location.hash;history.replaceState(null,'',previousHash);if(!await confirm(t('discardTitle'),t('discardText'),t('discard')))return;draft=null;history.replaceState(null,'',target)}previousHash=location.hash;render()});
window.addEventListener('beforeunload',e=>{if(draft&&JSON.stringify(draft)!==baseline){e.preventDefault();e.returnValue=''}});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&$('#query')){e.preventDefault();$('#query').focus()}});
document.addEventListener('click',e=>{if(!e.target.closest('.search-wrap')){const el=$('#suggestions');if(el)el.innerHTML=''}if(e.target.closest('.card'))captureLibrary()});
prepareSharedRoute();
render();
if(window.isSecureContext&&'serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});

function setTheme(value){theme=value;localStorage.setItem('folio-theme',value);document.documentElement.dataset.theme=value;document.querySelector('meta[name="theme-color"]').content=value==='dark'?'#101010':'#f6f5f1';if(route().path==='/settings')settings()}
// A focused search lives at the top on phones. Other inputs hide the utility
// bar, avoiding overlap even on browsers that resize the layout viewport.
let utilityMotion=null;
function updateUtilityFocus(){
 const active=document.activeElement,root=document.documentElement;
 const searching=active?.closest?.('#bottom-search-form')||(root.dataset.utilityFocus==='search'&&active?.closest?.('.utility-bar'));
 const previous=root.dataset.utilityFocus||'idle';
 const next=searching?'search':active?.matches?.('input:not([type="checkbox"]):not([type="radio"]),textarea,select,[contenteditable="true"]')?'editing':'idle';
 const bar=$('.utility-bar'),mobile=window.matchMedia('(max-width:700px)').matches;
 const reduceMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 const moving=bar&&mobile&&!reduceMotion&&previous!==next&&previous!=='editing'&&next!=='editing';
 // Capture the currently drawn position before canceling an interrupted slide.
 const from=moving?bar.getBoundingClientRect().top:0;
 if(previous!==next||!mobile||reduceMotion){utilityMotion?.cancel();utilityMotion=null}
 root.dataset.utilityFocus=next;
 const viewport=window.visualViewport;
 root.style.setProperty('--visual-top',(viewport?.offsetTop||0)+'px');
 root.style.setProperty('--visual-height',(viewport?.height||window.innerHeight)+'px');
 if(moving&&bar.animate){
  const distance=from-bar.getBoundingClientRect().top;
  if(Math.abs(distance)>1)utilityMotion=bar.animate(
   [{transform:`translateY(${distance}px)`},{transform:'translateY(0)'}],
   {duration:320,easing:'cubic-bezier(0.22,1,0.36,1)'}
  );
 }
}
document.addEventListener('focusin',updateUtilityFocus);
document.addEventListener('focusout',()=>requestAnimationFrame(updateUtilityFocus));
window.visualViewport?.addEventListener('resize',updateUtilityFocus);
window.visualViewport?.addEventListener('scroll',updateUtilityFocus);
window.addEventListener('resize',updateUtilityFocus);
updateUtilityFocus();


// Recovery, named searches, bulk selection, transient previews and PWA entry.
const safely=fn=>async(...args)=>{try{await fn(...args)}catch(e){toast(e.message)}};
const sortOptions=value=>['newest','oldest','recent','least','random',...config.dimensions.map(d=>'rating'+d.number)].map(k=>`<option value="${k}" ${value===k?'selected':''}>${esc(k.startsWith('rating')?config.dimensions.find(d=>'rating'+d.number===k)?.name:t(k==='random'?'randomSort':k))}</option>`).join('');
function mountLibraryFeatures(){
 if(selectionHash!==activeLibraryHash){resetSelection();selectionHash=activeLibraryHash}
 const query=$('.active-query');query.outerHTML=`<div class="query-actions">${query.outerHTML}<button type="button" id="save-search" class="iconbtn search-save" aria-label="${esc(t('saveSearch'))}" title="${esc(t('saveSearch'))}" data-tooltip="${esc(t('saveSearch'))}" aria-pressed="false">${icon('bookmark')}</button></div>`;
 $('.search-help').insertAdjacentHTML('afterend','<div id="selection-actions" class="feature-actions selection-actions" hidden></div>');
 $('.utility-bar').insertAdjacentHTML('beforeend',`<button type="button" id="selection-exit" class="iconbtn selection-floating-exit" aria-label="${esc(t('exitSelection'))}" title="${esc(t('exitSelection'))}" hidden>${icon('x')}</button>`);
 $('#selection-exit').onclick=()=>{resetSelection();bindSelectionCards()};
 matchingSavedSearch=null;
 $('#save-search').onclick=()=>searchEditor(matchingSavedSearch,{query:route().params.get('q')||'',sort:$('#sort').value});
 refreshSearchSaveButton().catch(e=>toast(e.message));
}
function matchingSearch(items,query,sort){return items.find(s=>!s.error&&s.query.trim()===query.trim()&&s.sort===sort)||null}
async function refreshSearchSaveButton(){
 const button=$('#save-search'),hash=activeLibraryHash;if(!button)return;
 const query=route().params.get('q')||'',sort=$('#sort').value;
 button.disabled=true;matchingSavedSearch=null;
 try{
  const items=await api('saved-searches');
  if(!button.isConnected||activeLibraryHash!==hash||route().path!=='/library')return;
  matchingSavedSearch=matchingSearch(items,query,sort);
  const label=t(matchingSavedSearch?'editSavedSearch':'saveSearch');
  button.classList.toggle('is-saved',!!matchingSavedSearch);button.setAttribute('aria-pressed',String(!!matchingSavedSearch));
  button.setAttribute('aria-label',label);button.title=label;button.dataset.tooltip=label;
 }finally{if(button.isConnected&&activeLibraryHash===hash)button.disabled=false}
}
function resetSelection(){selecting=false;selectedWorks.clear();selectionVersion++}
const batchDeletion=createBatchDelete({getIds:()=>[...selectedWorks],getContext:()=>({hash:activeLibraryHash,version:selectionVersion}),confirm,api,t,onBusy:busy=>{if($('#batch-trash'))$('#batch-trash').disabled=busy||!selectedWorks.size;if($('#batch-edit'))$('#batch-edit').disabled=busy||!selectedWorks.size},onDeleted:async(result,context)=>{markLibraryDirty();toast(t('batchDeleted').replace('{count}',result.deleted));if(route().path==='/library'&&activeLibraryHash===context.hash&&selectionVersion===context.version){resetSelection();await library()}}});
function toggleWorkSelection(id,checked){if(!selecting){selecting=true;selectionVersion++}if(checked)selectedWorks.add(id);else selectedWorks.delete(id);bindSelectionCards()}
function bindSelectionCards(){
 const actions=$('#selection-actions');if(!actions)return;
 actions.hidden=!selecting;
 $('#selection-exit').hidden=!selecting;
 actions.innerHTML=selecting?`<div class="selection-primary"><button type="button" id="select-visible" class="btn" aria-label="${esc(t('selectVisible'))}" title="${esc(t('selectVisible'))}">${esc(t('selectVisibleShort'))}</button><button type="button" id="select-results" class="btn" aria-label="${esc(t('selectResults'))}" title="${esc(t('selectResults'))}">${esc(t('selectResultsShort'))}</button></div><div class="selection-summary"><span role="status">${esc(t('selectedCount'))}: ${selectedWorks.size}</span>${btn(t('batchEdit'),'batch-edit','primary')}<button type="button" id="batch-trash" class="btn iconbtn danger" aria-label="${esc(t('deleteSelected'))}" title="${esc(t('deleteSelected'))}">${icon('trash')}</button></div>`:'';
 $$('[data-work-check]').forEach(input=>{const id=input.dataset.workCheck;input.checked=selectedWorks.has(id);input.closest('.work-card').classList.toggle('work-selected',input.checked);input.onchange=()=>toggleWorkSelection(id,input.checked)});
 $$('.card').forEach(a=>{const id=a.getAttribute('href').split('/').pop();a.onclick=e=>{if(selecting){e.preventDefault();toggleWorkSelection(id,!selectedWorks.has(id))}else captureLibrary()}});
 if(!selecting)return;
 $('#select-visible').onclick=()=>{libraryItems.forEach(w=>selectedWorks.add(w.id));bindSelectionCards()};
 $('#select-results').onclick=safely(async()=>{const b=$('#select-results');b.disabled=true;try{const hash=activeLibraryHash,version=selectionVersion;const r=await api('works?ids=1&q='+encodeURIComponent(route().params.get('q')||''));if(route().path!=='/library'||activeLibraryHash!==hash||!selecting||version!==selectionVersion)return;r.ids.forEach(id=>selectedWorks.add(id));bindSelectionCards()}finally{if(b.isConnected)b.disabled=false}});
 $('#batch-edit').disabled=batchDeletion.busy||!selectedWorks.size;
 $('#batch-edit').onclick=()=>batchEditor([...selectedWorks]);
 $('#batch-trash').disabled=batchDeletion.busy||!selectedWorks.size;
 $('#batch-trash').onclick=safely(batchDeletion.run);
}
async function trashPage(){
 const items=await api('trash');shell('trash',heading(t('trash'),t('trashHint'),items.length?btn(t('emptyTrash'),'trash-empty','danger'):'')+`<div id="trash-error"></div><div class="row wrap feature-actions">${items.length?btn(t('restoreSelected'),'restore-selected','primary'):''}</div><div class="directory-list">${items.map(w=>`<div class="directory-row trash-row"><label class="check-label"><input type="checkbox" data-trash-check="${w.id}"><span><b>${esc(w.title)}</b><small>${esc(new Date(w.deleted_at).toLocaleString(lang))}</small></span></label><div class="row wrap"><button class="btn" data-restore="${w.id}">${esc(t('restore'))}</button><button class="btn danger" data-purge="${w.id}">${esc(t('permanentDelete'))}</button></div></div>`).join('')||`<p>${esc(t('trashEmpty'))}</p>`}</div>`);
 const restoreIds=safely(async ids=>{if(await restoreEntries(ids)){markLibraryDirty();toast(t('operationDone'));trashPage()}});
 $$('[data-restore]').forEach(b=>b.onclick=()=>restoreIds([b.dataset.restore]));
 $('#restore-selected')?.addEventListener('click',()=>restoreIds($$('[data-trash-check]:checked').map(b=>b.dataset.trashCheck)));
 $$('[data-purge]').forEach(b=>b.onclick=safely(async()=>{if(!await confirm(t('permanentDelete'),t('permanentHint')))return;await api('trash/'+b.dataset.purge,'DELETE');markLibraryDirty();trashPage()}));
 $('#trash-empty')?.addEventListener('click',safely(async()=>{if(!await confirm(t('emptyTrash'),t('permanentHint')))return;await api('trash','DELETE');markLibraryDirty();trashPage()}));
}
async function restoreEntries(ids){
 if(!ids.length)return false;
 const preview=await api('trash/restore-preview','POST',{ids});
 if(preview.missing.length&&!await confirm(t('restoreWarning'),preview.missing.map(x=>x.title+': '+x.names.join(', ')).join('\n'),t('continueRestore')))return false;
 await api('trash/restore','POST',{ids,signature:preview.signature});return true;
}
async function showTrashedSource(matches,value){
 if(!value){nav('/trash');return;}
 draft=blank();baseline=JSON.stringify(draft);draft.links=[{url:value,label:'',is_primary:true}];
 const active=draft,version=routeVersion;
 if(!await trashSourceUI.prepare(active,'',()=>draft===active&&routeVersion===version)){if(draft===active&&routeVersion===version){draft=null;nav('/trash');}return;}
 history.replaceState(null,'','#/new');previousHash=location.hash;await edit(null,true);
 if(importerSourceURL(value))await interactiveImport(null,true);
}
function importerSourceURL(value){return isPawchiveSource(value)||isStoreSource(value)||isDLsitePlaySeries(value)||/^https?:\/\/(www\.)?(hitomi\.la|nhentai\.net|momon-ga\.com)\//i.test(value)}

const mergeLabel=e=>displayName(e)+(e.gender&&e.gender!=='neutral'?' · '+t(e.gender):'');
async function historyPage(){
 const items=await api('history');shell('history',heading(t('history'),t('historyHint'))+`<div class="directory-list">${items.map(h=>`<div class="directory-row"><div><b>${esc(t(h.kind+'Operation'))}</b><div class="subtitle">${esc(new Date(h.created).toLocaleString(lang))} · ${h.count} ${esc(t('works'))}</div><div class="subtitle">${h.merge?esc(mergeLabel(h.merge.source)+' → '+mergeLabel(h.merge.target))+'<br>':''}${h.titles.map(esc).join(' · ')}</div><div class="subtitle">${h.scale?esc(h.scale.name+' · '+h.scale.before+' → '+h.scale.after):h.fields.map(k=>esc(t(k))).join(', ')}</div></div><button class="btn" data-undo="${h.id}" ${h.undone?'disabled':''}>${esc(t(h.undone?'undone':'undo'))}</button></div>`).join('')||`<p>${esc(t('historyEmpty'))}</p>`}</div>`);
 $$('[data-undo]').forEach(b=>b.onclick=safely(async()=>{const preview=await api('history/'+b.dataset.undo+'/preview','POST',{});const description=t('undoConfirm')+'\n'+(preview.merge?mergeLabel(preview.merge.source)+' → '+mergeLabel(preview.merge.target)+' · '+preview.count+' '+t('works'):preview.scale?`${preview.scale.after} → ${preview.scale.before}`:preview.details.map(d=>d.title+': '+d.fields.map(t).join(', ')).join('\n'));if(!await confirm(t('undo'),description,t('undo')))return;b.disabled=true;try{await api('history/'+b.dataset.undo+'/undo','POST',{});markLibraryDirty();await refreshConfig();toast(t('operationDone'));historyPage()}finally{if(b.isConnected)b.disabled=false}}));
}
async function savedSearchPage(){
 const items=await api('saved-searches');shell('savedSearches',heading(t('savedSearches'),t('savedSearchHint'),btn(t('saveSearch'),'new-search','primary'))+`<div class="directory-list">${items.map((s,i)=>`<div class="directory-row saved-search-row"><div><button class="saved-search-name" data-open-search="${s.id}" ${s.error?'disabled':''}>${esc(s.name)}</button><div class="subtitle">${esc(s.query||t('library'))} · ${esc(s.sort)}</div>${s.error?`<div class="error">${esc(t('searchInvalid'))} ${esc(localizeError(s.error,lang))}</div>`:''}</div><div class="row wrap"><button class="btn" data-edit-search="${s.id}">${esc(t('edit'))}</button><button class="btn" data-order-search="${i}:up" ${i===0?'disabled':''}>${esc(t('moveUp'))}</button><button class="btn" data-order-search="${i}:down" ${i===items.length-1?'disabled':''}>${esc(t('moveDown'))}</button><button class="btn danger" data-delete-search="${s.id}">${esc(t('delete'))}</button></div></div>`).join('')||`<p>${esc(t('searchEmpty'))}</p>`}</div>`);
 $('#new-search').onclick=()=>searchEditor();
 $$('[data-open-search]').forEach(b=>b.onclick=()=>{const s=items.find(s=>s.id===b.dataset.openSearch);librarySnapshot=null;seed=String(Date.now());nav('/library?'+new URLSearchParams({q:s.query,sort:s.sort}))});
 $$('[data-edit-search]').forEach(b=>b.onclick=()=>searchEditor(items.find(s=>s.id===b.dataset.editSearch)));
 $$('[data-delete-search]').forEach(b=>b.onclick=safely(async()=>{if(!await confirm(t('delete'),items.find(s=>s.id===b.dataset.deleteSearch).name))return;await api('saved-searches/'+b.dataset.deleteSearch,'DELETE');savedSearchPage()}));
 $$('[data-order-search]').forEach(b=>b.onclick=safely(async()=>{const [index,direction]=b.dataset.orderSearch.split(':'),i=Number(index),j=i+(direction==='up'?-1:1);await api('saved-searches/reorder','POST',{ids:items.map((s,n)=>n===i?items[j].id:n===j?items[i].id:s.id)});savedSearchPage()}));
}
function searchEditor(item=null,defaults={}){
 modal(`<h2>${esc(t('saveSearch'))}</h2><div id="search-edit-error"></div><form id="search-edit" class="stack"><label>${esc(t('searchName'))}<input id="search-name" required maxlength="200" value="${esc(item?.name||'')}"></label><label>${esc(t('searchExpression'))}<input id="search-expression" maxlength="4096" value="${esc(item?.query??defaults.query??'')}"></label><label>${esc(t('searchSort'))}<select id="search-sort">${sortOptions(item?.sort||defaults.sort||'newest')}</select></label><div class="actions">${btn(t('cancel'),'search-cancel')}<button class="btn primary" type="submit">${esc(t('save'))}</button></div></form>`);
 $('#search-cancel').onclick=closeModal;
 $('#search-edit').onsubmit=async e=>{e.preventDefault();const b=$('#search-edit button[type=submit]');b.disabled=true;try{await api('saved-searches'+(item?'/'+item.id:''),item?'PUT':'POST',{name:$('#search-name').value,query:$('#search-expression').value,sort:$('#search-sort').value});closeModal();toast(t('saved'));if(route().path==='/saved-searches')savedSearchPage();else if(route().path==='/library')refreshSearchSaveButton().catch(e=>toast(e.message))}catch(e){error($('#search-edit-error'),e)}finally{if(b.isConnected)b.disabled=false}};
}
function batchEditor(ids,patch={}){
 modal(`<h2>${esc(t('batchEdit'))} · ${ids.length}</h2><p>${esc(t('batchHint'))}</p><div id="batch-error"></div><div class="stack">${metadataKinds.map(k=>`<section><label>${esc(t(k))}<select data-batch-mode="${k}"><option value="">${esc(t('unchanged'))}</option>${[['add','addMode'],['remove','removeMode'],['replace','replaceMode'],['clear','clearMode']].map(([v,label])=>`<option value="${v}" ${patch[k]?.mode===v?'selected':''}>${esc(t(label))}</option>`).join('')}</select></label><div class="row wrap">${(patch[k]?.items||[]).map(e=>`<button class="tag" data-batch-remove="${k}:${e.id}">${esc(displayName(e))} ×</button>`).join('')}<button class="btn" data-batch-choose="${k}" ${!patch[k]||patch[k].mode==='clear'?'disabled':''}>${esc(t('select'))}</button></div></section>`).join('')}${config.dimensions.map(d=>`<label>${d.number}. ${esc(d.name)}<select data-batch-rating="${d.id}"><option value="keep">${esc(t('unchanged'))}</option><option value="null" ${patch.ratings?.[d.id]===null?'selected':''}>${esc(t('unrated'))}</option>${Array.from({length:d.maximum},(_,i)=>`<option value="${i+1}" ${patch.ratings?.[d.id]===i+1?'selected':''}>${i+1}/${d.maximum}</option>`).join('')}</select></label>`).join('')}<section><label>${esc(t('marks'))}<select id="batch-mark-mode"><option value="">${esc(t('unchanged'))}</option>${[['add','addMode'],['remove','removeMode'],['replace','replaceMode'],['clear','clearMode']].map(([v,label])=>`<option value="${v}" ${patch.marks?.mode===v?'selected':''}>${esc(t(label))}</option>`).join('')}</select></label><div id="batch-marks">${markUI.buttons({marks:patch.marks?.items||[]})}</div></section><label>${esc(t('category'))}<select id="batch-category"><option value="keep">${esc(t('unchanged'))}</option><option value="" ${patch.category===''?'selected':''}>${esc(t('notSpecified'))}</option>${Object.keys(config.categories).map(k=>`<option value="${k}" ${patch.category===k?'selected':''}>${esc(t(k))}</option>`).join('')}</select></label><label class="check-label"><input id="batch-language-enable" type="checkbox" ${'language' in patch?'checked':''}>${esc(t('languageValue'))}</label><input id="batch-language" maxlength="100" value="${esc(patch.language||'')}"></div><div class="actions">${btn(t('cancel'),'batch-cancel')}${btn(t('previewChanges'),'batch-preview','primary')}</div>`);
 $('#batch-cancel').onclick=closeModal;
 $$('[data-batch-mode]').forEach(el=>el.onchange=()=>{if(el.value)patch[el.dataset.batchMode]={mode:el.value,items:patch[el.dataset.batchMode]?.items||[]};else delete patch[el.dataset.batchMode];batchEditor(ids,patch)});
 $$('[data-batch-choose]').forEach(b=>b.onclick=()=>chooseMetadata(b.dataset.batchChoose,item=>{const items=patch[b.dataset.batchChoose].items;if(!items.some(e=>e.id===item.id))items.push(item);batchEditor(ids,patch)}));
 $$('[data-batch-remove]').forEach(b=>b.onclick=()=>{const [k,id]=b.dataset.batchRemove.split(':');patch[k].items=patch[k].items.filter(e=>e.id!==id);batchEditor(ids,patch)});
 $$('[data-batch-rating]').forEach(el=>el.onchange=()=>{patch.ratings??={};if(el.value==='keep')delete patch.ratings[el.dataset.batchRating];else patch.ratings[el.dataset.batchRating]=el.value==='null'?null:Number(el.value);if(!Object.keys(patch.ratings).length)delete patch.ratings});
 $('#batch-mark-mode').onchange=e=>{if(e.target.value)patch.marks={mode:e.target.value,items:patch.marks?.items||[]};else delete patch.marks;batchEditor(ids,patch)};
 if(patch.marks&&patch.marks.mode!=='clear'){const selected={marks:patch.marks.items};markUI.bind($('#batch-marks'),()=>selected,work=>{patch.marks.items=work.marks})}else $$('#batch-marks button').forEach(b=>b.disabled=true);

 $('#batch-category').onchange=e=>{if(e.target.value==='keep')delete patch.category;else patch.category=e.target.value};
 $('#batch-language-enable').onchange=e=>{if(e.target.checked)patch.language=$('#batch-language').value;else delete patch.language};
 $('#batch-language').oninput=e=>{if($('#batch-language-enable').checked)patch.language=e.target.value};
 $('#batch-preview').onclick=async()=>{const b=$('#batch-preview');b.disabled=true;b.textContent=t('loading');try{const preview=await api('batch/preview','POST',{ids,patch});modal(`<h2>${esc(t('batchPreview'))}</h2><p>${esc(t('selectedCount'))}: ${preview.total}<br>${esc(t('changedCount'))}: ${preview.changed}<br>${esc(t('unchangedCount'))}: ${preview.unchanged}</p><div class="stack">${Object.entries(patch).map(([k,v])=>`<div><b>${esc(t(k))}</b>: ${esc(batchDescription(k,v))}${v?.items?.length?' · '+v.items.map(e=>esc(k==='marks'?markUI.name(config.marks.find(d=>d.number===e)):displayName(e))).join(', '):''}</div>`).join('')}</div><div id="batch-apply-error"></div><div class="actions">${btn(t('backToBatch'),'batch-back')}${btn(t('applyChanges'),'batch-apply','primary')}</div>`);$('#batch-back').onclick=()=>batchEditor(ids,patch);$('#batch-apply').disabled=!preview.changed;$('#batch-apply').onclick=async()=>{const apply=$('#batch-apply');apply.disabled=true;try{const result=await api('batch/apply','POST',{id:preview.id});closeModal();markLibraryDirty();resetSelection();toast(`${t('operationDone')}: ${result.changed} · ${t('unchangedCount')}: ${result.unchanged}`);await library()}catch(e){error($('#batch-apply-error'),e)}finally{if(apply.isConnected)apply.disabled=false}}}catch(e){error($('#batch-error'),e)}finally{if(b.isConnected){b.disabled=false;b.textContent=t('previewChanges')}}};
}
function batchDescription(k,v){if(v?.mode)return t(({add:'addMode',remove:'removeMode',replace:'replaceMode',clear:'clearMode'})[v.mode]);if(k==='bought')return t(v?'bought':'purchaseNo');if(k==='ratings')return Object.entries(v).map(([id,n])=>{const d=config.dimensions.find(d=>d.id===id);return `${d?.number}. ${d?.name}: ${n===null?t('unrated'):n+'/'+d?.maximum}`}).join(' · ');if(k==='category')return t(v||'notSpecified');return v||t('notSpecified')}
function releasePreview(){clearTimeout(previewTimer);previewController?.abort();previewController=null;if(previewObjectUrl)URL.revokeObjectURL(previewObjectUrl);previewObjectUrl='';previewSequence++}
function bindCoverPreview(id){
 releasePreview();const input=$('[data-field="cover"]'),container=$('#cover-preview'),value=draft.cover;
 container.innerHTML=`<p class="muted small">${esc(t('previewHint'))}</p><div class="image-preview-grid">${id?`<div><span>${esc(t('previewSaved'))}</span><div class="cover preview-cover" id="saved-cover-preview"></div></div>`:''}<div><span>${esc(t('previewNew'))}</span><div class="cover preview-cover" id="draft-cover-preview"></div><p class="muted small" id="preview-status" role="status"></p>${btn(t('retry'),'preview-retry')}</div></div>`;
 if(id){api('works/'+id).then(w=>{const el=$('#saved-cover-preview');if(el&&el.closest('#cover-preview')===container){el.innerHTML=image(w);images()}}).catch(()=>{})}
 const run=async()=>{
  clearTimeout(previewTimer);previewController?.abort();if(previewObjectUrl)URL.revokeObjectURL(previewObjectUrl);previewObjectUrl='';const sequence=++previewSequence,url=input.value.trim(),box=$('#draft-cover-preview'),status=$('#preview-status');if(!box||!container.isConnected)return;box.replaceChildren();
  if(!url){status.textContent=t('previewEmpty');return}
  try{const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol)||parsed.username||parsed.password)throw Error()}catch{status.textContent=t('previewInvalid');return}
  status.textContent=t('loading');const controller=new AbortController();previewController=controller;
  try{
   let src=url;
   if(relayCover(url)){
    const response=await fetch('/api/covers/preview',{method:'POST',headers:{'Content-Type':'application/json','X-Library-Token':config.token},body:JSON.stringify({url}),signal:controller.signal,cache:'no-store'});
    if(!response.ok)throw Error();const blob=await response.blob();if(sequence!==previewSequence||!container.isConnected)return;src=previewObjectUrl=URL.createObjectURL(blob);
   }
   if(sequence!==previewSequence||!container.isConnected)return;const img=new Image();img.referrerPolicy='no-referrer';img.alt=t('previewNew');img.onload=()=>{if(sequence===previewSequence&&container.isConnected)status.textContent=t('previewReady')};img.onerror=()=>{if(sequence===previewSequence&&container.isConnected){box.replaceChildren();status.textContent=t('previewFailed')}};img.src=src;box.append(img);
  }catch(e){if(e.name!=='AbortError'&&sequence===previewSequence&&container.isConnected)status.textContent=t('previewFailed')}
 };
 input.addEventListener('input',()=>{clearTimeout(previewTimer);previewController?.abort();previewSequence++;previewTimer=setTimeout(run,600)});
 $('#preview-retry').onclick=run;if(value)run();else $('#preview-status').textContent=t('previewEmpty');
}
function prepareSharedRoute(){
 if(location.pathname!=='/share-target')return;
 const p=new URLSearchParams(location.search);sessionStorage.setItem('folio-shared-content',JSON.stringify({url:p.get('url')||'',text:p.get('text')||'',title:p.get('title')||''}));
 history.replaceState(null,'','/#/share');previousHash=location.hash;
}
async function sharedPage(version){
 const raw=sessionStorage.getItem('folio-shared-content');sessionStorage.removeItem('folio-shared-content');const content=raw?JSON.parse(raw):{};
 const urls=[...new Set([content.url,content.text,content.title].filter(Boolean).flatMap(s=>s.match(/https?:\/\/[^\s<>"\u3000]+/g)||[]).map(s=>s.replace(/[.,;\u3002]+$/,'')))].filter(value=>{try{const u=new URL(value);return !u.username&&!u.password}catch{return false}});
 if(!urls.length){shell('library',heading(t('shareChoose'),t('shareNoUrl')));return}
 if(urls.length>1){shell('library',heading(t('shareChoose'),'')+`<div class="directory-list">${urls.map((u,i)=>`<button class="btn shared-link" data-shared-link="${i}">${esc(u)}</button>`).join('')}</div>`);$$('[data-shared-link]').forEach(b=>b.onclick=safely(()=>openSharedUrl(urls[Number(b.dataset.sharedLink)],version)));return}
 await openSharedUrl(urls[0],version);
}
async function openSharedUrl(value,version){
 if(importerSourceURL(value)){nav('/source?'+new URLSearchParams({url:value}));return}
 const lookup=await api('source-check','POST',{url:value,generic:true});if(version!==routeVersion)return;
 if(lookup.matches.length){if(lookup.matches.every(w=>w.deleted_at)){await showTrashedSource(lookup.matches,value);return}nav('/work/'+lookup.matches.find(w=>!w.deleted_at).id);return}
 draft=blank();baseline=JSON.stringify(draft);draft.links=[{url:value,label:'',is_primary:true}];history.replaceState(null,'','#/new');previousHash=location.hash;await edit(null,true);toast(t('sharedManual'));
}
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;if(route().path==='/settings')mountInstallTools()});
window.addEventListener('appinstalled',()=>{installPrompt=null});
function mountInstallTools(){
 $('#pwa-tools')?.remove();$('.main .stack').insertAdjacentHTML('afterbegin',`<section class="panel stack" id="pwa-tools"><h3>${esc(t('installApp'))}</h3><p class="muted">${esc(t(window.isSecureContext?'installHint':'installUnavailable'))}</p>${btn(t('installApp'),'pwa-install')}</section>`);
 $('#pwa-install').onclick=safely(async()=>{if(!installPrompt){toast(t('installUnavailable'));return}await installPrompt.prompt();await installPrompt.userChoice;installPrompt=null});
}

async function mergeSavedDraft(id){
 const s=(en,ja)=>lang==='ja'?ja:en;
 if(JSON.stringify(draft)!==baseline)return toast(s('Save your changes before merging this entry.','統合する前に編集内容を保存してください。'));
 if(!draft.links.some(l=>l.url))return toast(t('addLink'));
 const active=draft,version=routeVersion,current=()=>draft===active&&routeVersion===version&&JSON.stringify(draft)===baseline;
 const candidates=await api('works?limit=40');if(!current())return;
 const decision=await nhentaiUI.chooseMatch(draft,candidates.items.filter(w=>w.id!==id),false,{exclude:id,existing:true,title:s('Choose the entry to keep','残す作品を選択'),hint:s('All saved source links will be added as secondary links. The current entry will go to Trash.','保存済みのソースリンクをすべて副リンクとして追加し、現在の作品はゴミ箱へ移動します。')});
 if(decision?.action!=='attach'||!current())return;
 const p=await api('works/'+id+'/merge-preview','POST',{target:decision.target});if(!current())return;
 const accepted=await confirm(s('Confirm link merge','リンク統合の確認'),s(`Move ${p.links.length} source links from “${p.source.title}” to “${p.target.title}” as secondary links? The source entry will go to Trash. Destination metadata and personal records are preserved.`,`「${p.source.title}」のリンク${p.links.length}件を「${p.target.title}」の副リンクとして追加します。統合元はゴミ箱へ移動します。統合先のメタデータ・評価・マーク・レビューは維持します。`),s('Merge','統合'));
 if(!accepted||!current())return;
 const result=await api('works/'+id+'/merge-links','POST',{target:decision.target,signature:p.signature});
 draft=null;markLibraryDirty();toast(s('Links merged','リンクを統合しました'));nav('/work/'+result.id);
}

async function shareWork(work,version){
 const s=(en,ja)=>lang==='ja'?ja:en;
 const state=await api('shares/'+work.id);if(version!==routeVersion)return;
 modal(`<div class="metadata-picker-header"><h2>${esc(s('Share a snapshot','作品を共有'))}</h2><button type="button" id="share-x" class="iconbtn" aria-label="${esc(t('close'))}">${icon('x')}</button></div><p>${esc(s('Anyone with the link can view this snapshot, including the selected personal records. Later edits are not reflected. You can revoke access here. Moving the work to Trash also revokes its shares.','リンクを知っている人は、選択した個人記録を含め閲覧できます。共有時点の内容を固定し、以降の編集は反映しません。ここで共有解除できます。元の作品をゴミ箱へ移した場合も共有解除されます。'))}</p><div class="row wrap">${['ratings','review','marks'].map(k=>`<label class="check-label"><input type="checkbox" data-share-option="${k}" checked><span>${esc(t(k))}</span></label>`).join('')}</div><p class="muted small">${esc(s('Title, cover, authors, tags and all source links are included. Search-engine indexing is disabled.','タイトル・表紙・作者・タグなどのメタデータと、すべてのソースリンクを公開します。現在は検索エンジンへの掲載を抑止します。'))}</p><div id="share-preview" class="panel stack"></div><div id="share-error"></div><div class="actions"><button class="btn" id="share-close">${esc(t('close'))}</button><button class="btn primary" id="share-create" ${state.base?'':'disabled'}>${esc(s('Publish snapshot','この内容で共有リンクを発行'))}</button></div>${state.base?'':`<p>${esc(s('Public sharing URL is not configured yet.','公開用URLはまだ設定されていません。'))}</p>`}<h3>${esc(s('Shared links','発行済みリンク'))}</h3><div id="share-list" class="stack"></div>`);
 const current=()=>version===routeVersion&&!!$('#share-preview');let sequence=0;
 const options=()=>Object.fromEntries([...$$('[data-share-option]')].map(x=>[x.dataset.shareOption,x.checked]).concat([['language',lang]]));
 const paint=items=>{
  $('#share-list').innerHTML=items.map(i=>`<div class="stack panel"><small>${esc(new Date(i.created).toLocaleString(lang))} · ${esc(i.revoked?s('Revoked','共有解除済み'):s('Active','公開中'))}</small>${i.revoked?'':`<input readonly aria-label="${esc(s('Share URL','共有URL'))}" value="${esc(i.url)}"><div class="row wrap"><a class="btn" href="${esc(i.url)}" target="_blank" rel="noopener noreferrer">${esc(s('Open','開く'))}</a><button class="btn" data-copy-share="${esc(i.token)}">${esc(s('Copy link','リンクをコピー'))}</button><button class="btn" data-revoke-share="${esc(i.token)}">${esc(s('Revoke','共有解除'))}</button></div>`}</div>`).join('')||`<p>${esc(s('No shared links yet.','共有リンクはまだありません。'))}</p>`;
  $$('[data-copy-share]').forEach(b=>b.onclick=safely(async()=>{await navigator.clipboard.writeText(items.find(i=>i.token===b.dataset.copyShare).url);toast(s('Link copied','リンクをコピーしました'))}));
  $$('[data-revoke-share]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api('shares/'+work.id+'/'+b.dataset.revokeShare,'DELETE');if(current()){const latest=await api('shares/'+work.id);if(current())paint(latest.items)}}catch(e){if(current())error($('#share-error'),e)}finally{b.disabled=false}});
 };
 const refresh=async()=>{const seq=++sequence;$('#share-create').disabled=true;try{const p=await api('shares/'+work.id+'/preview','POST',{options:options()});if(!current()||seq!==sequence)return;$('#share-preview').innerHTML=`<b>${esc(p.title)}</b><small>${esc(p.links.map(l=>l.label||l.url).join(' · '))}</small>${['author','circle','series','character','tag'].filter(k=>p[k].length).map(k=>`<small>${esc(t(k))}: ${esc(p[k].map(x=>x.name).join(', '))}</small>`).join('')}${p.ratings.map(d=>`<small>${esc(d.name)}: ${d.value}/${d.maximum}</small>`).join('')}${p.marks.length?`<small>${esc(p.marks.map(m=>m.symbol+' '+m.label).join(' · '))}</small>`:''}${p.review?`<p class="review">${esc(p.review)}</p>`:''}`;$('#share-create').disabled=!state.base}catch(e){if(current())error($('#share-error'),e)}};
 $('#share-close').onclick=closeModal;$('#share-x').onclick=closeModal;$$('[data-share-option]').forEach(x=>x.onchange=refresh);paint(state.items);await refresh();
 if(!current())return;
 $('#share-create').onclick=async()=>{const button=$('#share-create');button.disabled=true;try{await api('shares/'+work.id,'POST',{expected_updated:work.updated,options:options()});if(current()){const latest=await api('shares/'+work.id);if(current()){paint(latest.items);toast(s('Sharing link created','共有リンクを発行しました'))}}}catch(e){if(current())error($('#share-error'),e)}finally{if(current())button.disabled=!state.base}};
}
