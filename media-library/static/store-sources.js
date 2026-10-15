export function isStoreSource(value){
 try{const u=new URL(value);if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.port&&!['80','443'].includes(u.port))return false;
 const host=u.hostname.replace(/^www\./,'');
 return u.hostname==='play.dlsite.com'&&/^\/work\/(RJ|BJ)\d{6,12}\/?$/i.test(u.pathname)||['dlsite.com','dlsharing.com'].includes(host)&&/^\/(home|maniax|girls|books)(-touch)?\/work\/\=\/product_id\/(RJ|BJ)\d{6,12}\.html\/?$/i.test(u.pathname)||host==='dmm.co.jp'&&/^\/dc\/doujin\/-\/detail\/\=\/cid=d_(?=0*[1-9])\d{1,12}\/?$/.test(u.pathname)||['book.dmm.com','book.dmm.co.jp'].includes(host)&&/^\/product\/[1-9]\d{0,11}\/(?!latest\/?$)[a-z0-9_]{1,80}\/?$/.test(u.pathname);
 }catch{return false}
}
export const isStoreCover=value=>/^https:\/\/img\.dlsite\.jp\/modpub\/images2\/work\//.test(value)||/^https:\/\/(?:doujin-assets\.dmm\.co\.jp|ebook-assets\.dmm\.(?:com|co\.jp))\/digital\//.test(value);
export function isDLsitePlaySeries(value){
 try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&u.hostname==='play.dlsite.com'&&!u.username&&!u.password&&(!u.port||['80','443'].includes(u.port))&&/^\/series\/TITLE\d{6,12}\/?$/.test(u.pathname)}catch{return false}
}
