// Purpose-specific entry points share the same explicit file preview and job flow.
export function importScreen({view,service,lang,esc,icon,t,sourceTools,pawTools,fanzaTools,modes,pawOption}){
 const s=(en,ja)=>lang==='ja'?ja:en;
 const href=(v,svc='')=>'#/imports?'+new URLSearchParams({view:v,...(svc?{service:svc}:{})});
 const names={home:s('Import','取り込む'),link:s('From a link','リンクから'),bookmarks:s('Browser bookmarks','ブラウザのブックマーク'),favorites:s('Service favorites','サービスのお気に入り'),purchases:s('Purchased works','購入済み作品'),history:s('Import history','取り込み履歴'),settings:s('Registration setup','登録方法の設定')};
 const nav=`<nav class="import-nav" aria-label="${s('Import navigation','インポートのメニュー')}">${['home','history','settings'].map(v=>`<a href="${href(v)}" ${view===v?'aria-current="page"':''}>${esc(names[v])}</a>`).join('')}</nav>`;
 const cards=[['link','external',s('Paste a work URL. Open an existing entry or import a new one.','作品URLを貼り付けて、登録済みの作品を開くか、新しく取り込みます。')],['bookmarks','bookmark',s('Read an HTML export from your browser.','ブラウザから書き出したブックマークHTMLを読み込みます。')],['favorites','star',s('nhentai, Pawchive or Kemono post favorites.','nhentai・Pawchive・Kemonoの投稿のお気に入り。')],['purchases','book',s('Import comic and CG links exported from your FANZA purchased list.','FANZAの購入一覧から書き出したコミック・CGを取り込みます。')]];
 const lead=view==='home'?'':`<div class="import-view-heading"><a href="${href('home')}">← ${esc(names.home)}</a><h2>${esc(names[view])}</h2></div>`;
 const services=(items)=>`<nav class="import-services" aria-label="${s('Service','サービス')}">${items.map(([id,label])=>`<a href="${href(view,id)}" ${service===id?'aria-current="page"':''}>${label}</a>`).join('')}</nav>`;
 let content='';
 if(view==='home')content=`<div class="import-cards">${cards.map(([id,symbol,hint])=>`<a class="import-card" href="${href(id)}">${icon(symbol)}<h2>${esc(names[id])}</h2><p>${esc(hint)}</p><span>${s('Choose →','選ぶ →')}</span></a>`).join('')}</div>`;
 else if(view==='settings')content=sourceTools();
 else if(view==='history')content=`<p class="muted">${s('Progress, pause/resume and pending decisions for every import source.','すべての取り込み元の進捗、停止・再開、確認待ちをここで管理できます。')}</p><div id="jobs" class="directory-list"></div>`;
 else if(view==='link')content=`<section class="panel stack"><p>${s('Works with supported source URLs. Registered links open the existing entry without re-importing.','対応サイトの作品URLを入力してください。登録済みのリンクは再インポートせず既存作品を開きます。')}</p><p class="muted small">Hitomi · nhentai · momon-ga · DLsite / Play · FANZA / DMM · Pawchive · Pixiv · FANBOX</p><form id="source-open-form" class="stack"><label><span>${esc(t('sourcePaste'))}</span><input id="source-url" type="url" required placeholder="https://…"></label><div><button type="submit" class="btn primary">${esc(t('openInFolio'))}</button></div></form><a href="${href('settings')}">${s('Set up bookmarklets and sharing →','ブックマークレット・共有の設定 →')}</a></section>`;
 else{
  if(view==='favorites')content+=services([['nhentai','nhentai'],['pawchive','Pawchive'],['kemono','Kemono']]);
  if(view==='purchases')content+=`<p class="muted">${s('FANZA doujin comics and CG are supported. DLsite purchase lists and DMM Books shelves are not supported yet.','FANZA同人のコミック・CGに対応しています。DLsite購入一覧・DMMブックス本棚は準備中です。')}</p>`;
  if(view==='favorites'&&service==='nhentai')content+='<div id="nhentai-import"></div>';
  else{
   const kind=view==='bookmarks'?'bookmarks':view==='purchases'?'fanza':service;
   if(kind==='pawchive')content+=`<details class="import-export"><summary>${s('How to export Pawchive favorites','Pawchiveのお気に入りの書き出し方')}</summary>${pawTools()}</details>`;
   if(kind==='fanza')content+=fanzaTools(lang);
   const label=kind==='kemono'?s('Kemono favorites JSON','Kemonoのお気に入りJSON'):kind==='pawchive'?s('Pawchive favorites HTML','Pawchiveのお気に入りHTML'):kind==='fanza'?s('FANZA purchased comics / CG HTML','FANZA購入済みコミック・CG HTML'):s('Browser bookmark HTML','ブラウザのブックマークHTML');
   const hint=kind==='kemono'?s('Choose the original JSON export. Post favorites from FANBOX / Patreon are imported through Pawchive. Artist favorites are counted but not imported.','書き出したJSONをそのまま選択してください。FANBOX／Patreonの投稿をPawchive経由で取り込みます。お気に入り作者は件数だけ表示し、取り込みません。'):s('Choose the exported HTML file. Review the list before starting; selecting a file does not register works.','書き出したHTMLを選択してください。ファイルの選択だけでは登録せず、一覧を確認してから開始します。');
   content+=`<label class="file-drop">${icon('upload')}<h3>${label}</h3><span>${hint}</span><input id="bookmark-file" aria-label="${label}" type="file" accept="${kind==='kemono'?'.json,application/json':'.html,.htm,text/html'}"></label><div id="import-error" role="alert"></div><div id="import-list-summary" aria-live="polite"></div><details class="panel stack import-options"><summary>${s('Import options','取り込みオプション')}</summary><label><span>${s('Title priority','タイトルの優先方式')}</span><select id="bookmark-title-mode"><option value="source">${esc(t('sourceTitleFirst'))}</option><option value="bookmark">${s('Names in the file first','ファイル内の名前を優先')}</option></select><small class="muted">${s('If the preferred name is missing, use the other name.','優先する名前がなければ、もう一方の名前を使います。')}</small></label>${modes('bookmark-tag-mode','nhentaiBatch')}${['bookmarks','pawchive','kemono'].includes(kind)?pawOption():''}</details><div id="bookmark-preview"></div>`;
  }
 }
 return nav+lead+content;
}

export function importLocation(params){
 const choices=['home','link','bookmarks','favorites','purchases','history','settings'];
 const view=choices.includes(params.get('view'))?params.get('view'):'home';
 const service=view==='favorites'&&['nhentai','pawchive','kemono'].includes(params.get('service'))?params.get('service'):'nhentai';
 return {view,service,kind:view==='bookmarks'?'bookmarks':view==='purchases'?'fanza':service};
}
