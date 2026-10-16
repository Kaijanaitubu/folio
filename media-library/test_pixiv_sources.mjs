import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {isPixivSource,isPixivCover} from './static/pixiv-sources.js';
import {bookmarklet} from './static/source-link.js';
for(const url of ['https://www.pixiv.net/artworks/123','https://www.pixiv.net/en/artworks/123?x=1','https://pixiv.net/member_illust.php?illust_id=123','https://author.fanbox.cc/posts/456','https://www.fanbox.cc/@author_name/posts/456','https://www.fanbox.cc/posts/456'])assert.ok(isPixivSource(url),url);
for(const url of ['https://www.pixiv.net/novel/show.php?id=123','https://www.pixiv.net/artworks/0','https://pixiv.net.evil/artworks/123','https://evil.fanbox.cc.evil/posts/456','https://user@www.pixiv.net/artworks/123','https://www.pixiv.net/member_illust.php?illust_id=123&illust_id=456'])assert.ok(!isPixivSource(url),url);
assert.ok(isPixivCover('https://i.pximg.net/c/example.jpg'));
const script=bookmarklet('https://folio.example').slice('javascript:'.length);
for(const host of ['www.pixiv.net','author.fanbox.cc','www.fanbox.cc','pawchive.pw']){
 const location={hostname:host,href:'https://'+host+'/posts/123'};
 vm.runInNewContext(script,{location,alert:()=>assert.fail('supported host rejected')});
 assert.ok(location.href.startsWith('https://folio.example/#/source?url='));
}
const location={hostname:'author.fanbox.cc.evil',href:'https://author.fanbox.cc.evil/posts/123'};let rejected=false;
vm.runInNewContext(script,{location,alert:()=>rejected=true});assert.ok(rejected);
const app=readFileSync(new URL('./static/app.js',import.meta.url),'utf8');
assert.match(app,/importerSourceURL\(value\)\{return isPixivSource\(value\)/);
assert.match(app,/relayCover=url=>isPixivCover\(url\)/);
console.log('Pixiv/FANBOX source URLs, bookmarklet navigation and relay integration passed.');
