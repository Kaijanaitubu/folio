// Self-contained code copied to a user's bookmark. Only Pawchive receives its
// own login session; the downloaded file contains validated post URLs alone.
async function exportFavorites(language){
 const ja=language==='ja',s=(en,jp)=>ja?jp:en;
 if(location.protocol!=='https:'||!['pawchive.pw','www.pawchive.pw'].includes(location.hostname)){alert(s('Open Pawchive and log in first.','Pawchiveを開き、ログインしてから実行してください。'));return}
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),40000);
 try{
  const response=await fetch('/api/v1/account/favorites?type=post',{method:'GET',credentials:'same-origin',redirect:'error',cache:'no-store',headers:{Accept:'application/json'},signal:controller.signal});
  if(response.status===401||response.status===403)throw Error(s('Log in to Pawchive, then try again.','Pawchiveへログインしてから再試行してください。'));
  if(!response.ok)throw Error('HTTP '+response.status);
  if(!response.headers.get('Content-Type')?.toLowerCase().startsWith('application/json'))throw Error(s('Unexpected response. No file was saved.','応答形式が想定と異なります。ファイルは保存しません。'));
  const reader=response.body.getReader(),decoder=new TextDecoder();let size=0,text='';
  try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>12*1024*1024)throw Error(s('Favorites response exceeds 12 MB.','お気に入りの応答が12 MBを超えています。'));text+=decoder.decode(value,{stream:true})}text+=decoder.decode()}finally{reader.releaseLock()}
  const rows=JSON.parse(text);
  if(!Array.isArray(rows)||rows.length>100000)throw Error(s('Unexpected or oversized favorites list.','お気に入り一覧の形式または件数が想定と異なります。'));
  const id=value=>typeof value==='string'&&/^[1-9]\d{0,19}$/.test(value)?value:typeof value==='number'&&Number.isSafeInteger(value)&&value>0?String(value):null;
  const links=[],seen=new Set();let unsupported=0,duplicates=0;
  for(const row of rows){
   if(!row||!['fanbox','patreon'].includes(row.service)){unsupported++;continue}
   const user=id(row.user),post=id(row.id);
   if(!user||!post)throw Error(s('A supported post has invalid IDs. No file was saved.','対応投稿のIDが不正です。ファイルは保存しません。'));
   const key=row.service+':'+post;if(seen.has(key)){duplicates++;continue}seen.add(key);
   links.push('https://pawchive.pw/'+row.service+'/user/'+user+'/post/'+post);
  }
  if(!links.length){alert(s('No supported posts found. API items: ','対応投稿がありません。APIの件数：')+rows.length+s('; unsupported: ','、未対応：')+unsupported);return}
  const message=s('API favorites: ','APIのお気に入り：')+rows.length+'\n'+s('Export supported posts: ','出力する対応投稿：')+links.length+'\n'+s('Unsupported: ','未対応：')+unsupported+'\n'+s('Duplicates: ','重複：')+duplicates+'\n\n'+s('Compare the API count with Pawchive before treating this as a complete list. Save the bookmark file?','全件取得の確認にはPawchiveの件数と照合してください。ブックマークファイルを保存しますか？');
  if(!confirm(message))return;
  const html='<!DOCTYPE NETSCAPE-Bookmark-file-1>\n<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n<TITLE>Pawchive Favorites</TITLE>\n<H1>Pawchive Favorites</H1>\n<DL><p>\n'+links.map(url=>'<DT><A HREF="'+url+'"></A>').join('\n')+'\n</DL><p>\n';
  if(new TextEncoder().encode(html).length>12*1024*1024)throw Error(s('Bookmark file exceeds 12 MB.','ブックマークファイルが12 MBを超えます。'));
  const object=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'})),link=document.createElement('a');
  link.href=object;link.download='pawchive-favorites-'+new Date().toISOString().slice(0,10)+'.html';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(object),30000);
 }catch(error){alert(s('Export failed: ','出力に失敗しました：')+(error.name==='AbortError'?s('Request timed out.','時間内に取得できませんでした。'):error.message))}finally{clearTimeout(timer)}
}
export function favoritesBookmarklet(language='en'){
 return 'javascript:('+exportFavorites.toString()+')('+JSON.stringify(language==='ja'?'ja':'en')+');void(0);';
}
