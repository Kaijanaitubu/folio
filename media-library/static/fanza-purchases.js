// Runs in the user's logged-in purchase page. Reads visible purchase metadata
// and scrolls that list only; never reads cookies, account IDs or payment data.
async function exportFanzaPurchases(language){
 const s=(en,ja)=>language==='ja'?ja:en;
 if(location.protocol!=='https:'||!['www.dmm.co.jp','dmm.co.jp'].includes(location.hostname)||location.pathname!=='/dc/-/mylibrary/'){alert(s('Open your FANZA doujin purchased works page first.','FANZA同人の購入済み作品一覧を開いてください。'));return}
 if(document.getElementById('folio-purchase-progress')){alert(s('Export is already running.','書き出し中です。'));return}
 if(!document.getElementById('genre_book')?.checked){alert(s('Filter the purchased list to Comics and apply the filter first.','作品形式で「コミック」を選び、「作品を探す」で適用してから実行してください。'));return}
 const anchors=()=>[...document.querySelectorAll('a[href*="/dc/-/mylibrary/detail/"]')];
 let pane=anchors()[0];while(pane&&!(['auto','scroll'].includes(getComputedStyle(pane).overflowY)))pane=pane.parentElement;
 if(!pane){alert(s('No scrollable purchased comic list was found.','スクロール可能な購入済みコミック一覧が見つかりません。'));return}
 let cancelled=false;
 const panel=document.createElement('div');panel.id='folio-purchase-progress';panel.style.cssText='position:fixed;right:12px;top:12px;z-index:2147483647;padding:16px;background:#202020;color:white;border:1px solid #f49a44;border-radius:10px;font:14px sans-serif;max-width:300px';
 const status=document.createElement('p'),stop=document.createElement('button');stop.textContent=s('Cancel export','書き出しを中止');stop.onclick=()=>{cancelled=true};panel.append(status,stop);document.body.append(panel);
 const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const pause=()=>new Promise(resolve=>setTimeout(resolve,600));const started=Date.now();let ready=0,previous='';
 try{
  while(Date.now()-started<180000){
   if(cancelled)return;
   if(!pane.isConnected||!document.getElementById('genre_book')?.checked)throw Error(s('The filter changed. Start again.','一覧や絞り込みが変わりました。最初からやり直してください。'));
   const links=new Map();
   for(const a of anchors()){
    if(!pane.contains(a))continue;
    const u=new URL(a.href,location.href),match=u.pathname.match(/^\/dc\/-\/mylibrary\/detail\/=\/product_id=(d_[0-9]{1,20})\/?$/);
    if(u.origin!==location.origin||!match)throw Error(s('Unexpected purchased-work URL.','購入作品のURL形式が想定と異なります。'));
    const format=a.querySelector('[class^="listRightHeaderGenre"]')?.textContent.trim();
    if(format!=='コミック')throw Error(s('The list includes non-comic or unknown items. Apply the Comics filter.','漫画以外、または形式不明の作品が含まれます。コミックの絞り込みを適用してください。'));
    links.set(match[1],{url:'https://www.dmm.co.jp/dc/doujin/-/detail/=/cid='+match[1]+'/',title:a.querySelector('[class^="productTitle"]')?.textContent.trim()||''});
   }
   const totalText=pane.innerText.match(/合計\s*[:：]\s*([0-9,]+)\s*作品/),total=totalText?Number(totalText[1].replaceAll(',','')):null;
   status.textContent=s('Loaded comics: ','読み込み済みコミック：')+links.size+(total===null?'':' / '+total);
   const signature=[...links.keys()].sort().join(',');
   ready=total!==null&&total>0&&links.size===total&&signature===previous?ready+1:0;previous=signature;
   if(ready>=2){
    if(!confirm(s('Purchased comics in the current filter: ','現在の絞り込みの購入済みコミック：')+total+s(' items. Save the import file? No login or payment information is included.','件。取り込み用ファイルを保存しますか？ログイン情報・決済情報は含みません。')))return;
    const html='<!DOCTYPE NETSCAPE-Bookmark-file-1>\n<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n<TITLE>FANZA purchased comics</TITLE>\n<H1>FANZA purchased comics</H1>\n<DL><p>\n'+[...links.values()].map(x=>'<DT><A HREF="'+escape(x.url)+'">'+escape(x.title)+'</A>').join('\n')+'\n</DL><p>\n';
    if(new TextEncoder().encode(html).length>12*1024*1024)throw Error(s('Export exceeds 12 MB.','出力が12 MBを超えます。'));
    const url=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='fanza-purchased-comics-'+new Date().toISOString().slice(0,10)+'.html';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);return;
   }
   pane.scrollTo({top:pane.scrollHeight,behavior:'instant'});await pause();
  }
  throw Error(s('The displayed total and loaded count did not match within 3 minutes. No file was saved. Retry after the list finishes loading.','3分以内に一覧の合計件数と読み込み件数が一致しませんでした。ファイルは保存しません。一覧の読み込み後に再実行してください。'));
 }catch(e){alert(s('Export failed: ','書き出しに失敗しました：')+e.message)}finally{panel.remove()}
}
export function fanzaPurchasesBookmarklet(language='en'){return 'javascript:('+exportFanzaPurchases.toString()+')('+JSON.stringify(language==='ja'?'ja':'en')+');void(0);'}
export function fanzaPurchaseTools(language='en'){
 const s=(en,ja)=>language==='ja'?ja:en;
 return `<details class="panel stack"><summary>${s('FANZA doujin — purchased comics','FANZA同人：購入済みコミック')}</summary><p>${s('Export purchased comic links from your logged-in browser. Passwords and cookies stay there. This is a page exporter, not an account API connection.','ログイン済みブラウザの購入一覧からコミックのリンクを書き出します。パスワード・Cookieはブラウザに保持します。アカウントAPIへの接続方式ではありません。')}</p><ol><li>${s('Save the export bookmark below, then open Purchased works on FANZA.','下の出力用ブックマークを保存し、FANZAの購入済み作品を開きます。')}</li><li>${s('Clear keywords, filter format to Comics, then apply Search. Run the export bookmark.','キーワードを空にし、作品形式を「コミック」にして「作品を探す」を押します。出力用ブックマークを実行します。')}</li><li>${s('The list scrolls automatically. When loaded and displayed totals match, confirm to save HTML. Upload it using the file field below and review before importing.','一覧を自動スクロールします。表示合計と読み込み件数が一致したら、確認してHTMLを保存します。下のファイル欄で読み込み、確認後に取り込みを開始します。')}</li></ol><p>${s('Purchased marks are not assigned automatically. Existing URLs use the usual duplicate skip. Bookshelf imports are not yet supported.','購入済みマークは自動付与しません。登録済みURLは従来どおりスキップします。DMMブックスの本棚はまだ未対応です。')}</p><label><span>${s('Export bookmark address','出力用ブックマークのURL')}</span><textarea id="fanza-purchases-code" readonly rows="3"></textarea></label><div class="row wrap"><button class="btn" id="fanza-purchases-copy">${s('Copy bookmark address','ブックマーク用URLをコピー')}</button><a id="fanza-purchases-bookmark" draggable="true">FANZA purchases</a><a href="https://www.dmm.co.jp/dc/-/mylibrary/" target="_blank" rel="noopener">${s('Open purchased works','購入済み作品を開く')}</a></div></details>`;
}
export function bindFanzaPurchaseTools(language='en'){
 const input=document.getElementById('fanza-purchases-code');if(!input)return;input.value=fanzaPurchasesBookmarklet(language);
 const link=document.getElementById('fanza-purchases-bookmark');link.href=input.value;link.onclick=e=>{e.preventDefault();alert(language==='ja'?'このブックマークはFANZAの購入一覧で実行してください。':'Run this bookmark on your FANZA purchased list.')};
 document.getElementById('fanza-purchases-copy').onclick=async()=>{try{await navigator.clipboard.writeText(input.value)}catch{input.focus();input.select()}};
}
