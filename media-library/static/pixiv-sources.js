export function isPixivSource(value){
 try{
  const u=new URL(value);if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.port&&!['80','443'].includes(u.port))return false;
  const id='[1-9][0-9]{0,19}';
  if(['pixiv.net','www.pixiv.net'].includes(u.hostname))return new RegExp('^/(?:[a-z]{2}/)?artworks/'+id+'/?$').test(u.pathname)||u.pathname==='/member_illust.php'&&u.searchParams.getAll('illust_id').length===1&&new RegExp('^'+id+'$').test(u.searchParams.get('illust_id')||'');
  if(['fanbox.cc','www.fanbox.cc'].includes(u.hostname))return new RegExp('^/(?:@[a-zA-Z0-9_-]{1,64}/)?posts/'+id+'/?$').test(u.pathname);
  return /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.fanbox\.cc$/.test(u.hostname)&&new RegExp('^/posts/'+id+'/?$').test(u.pathname);
 }catch{return false}
}
export const isPixivCover=value=>/^https:\/\/(?:i|pixiv)\.pximg\.net\//.test(value);
