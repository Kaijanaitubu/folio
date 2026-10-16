// This helper only navigates; it never reads library data from the source page.
export function bookmarklet(base) {
 const url=new URL(base);
 if(!['http:','https:'].includes(url.protocol)||url.username||url.password)throw Error('Use an HTTP or HTTPS URL without credentials');
 const target=url.origin+'/#/source?url=';
 return 'javascript:(()=>{if(!(/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.fanbox\\.cc$/.test(location.hostname)||["pixiv.net","www.pixiv.net","fanbox.cc","www.fanbox.cc","pawchive.pw","www.pawchive.pw","hitomi.la","www.hitomi.la","nhentai.net","www.nhentai.net","momon-ga.com","www.momon-ga.com","www.dlsite.com","dlsite.com","play.dlsite.com","dlsharing.com","www.dlsharing.com","www.dmm.co.jp","dmm.co.jp","book.dmm.com","book.dmm.co.jp"].includes(location.hostname))){alert("Open a supported work page first / 対応サイトの作品ページで実行してください");return;}location.href='+JSON.stringify(target)+'+encodeURIComponent(location.href);})();';
}
