// This helper only navigates; it never reads library data from the source page.
export function bookmarklet(base) {
 const url=new URL(base);
 if(!['http:','https:'].includes(url.protocol)||url.username||url.password)throw Error('Use an HTTP or HTTPS URL without credentials');
 const target=url.origin+'/#/source?url=';
 return 'javascript:(()=>{if(!["hitomi.la","www.hitomi.la","nhentai.net","www.nhentai.net"].includes(location.hostname)){alert("Open a Hitomi or nhentai work page first / Hitomi・nhentaiの作品ページで実行してください");return;}location.href='+JSON.stringify(target)+'+encodeURIComponent(location.href);})();';
}
