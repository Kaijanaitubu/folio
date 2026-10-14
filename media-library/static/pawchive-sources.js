export function isPawchiveSource(value){
 try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&['pawchive.pw','www.pawchive.pw'].includes(u.hostname)&&!u.username&&!u.password&&(!u.port||['80','443'].includes(u.port))&&/^\/(fanbox|patreon)\/(?:user\/[1-9]\d{0,19}\/)?post\/[1-9]\d{0,19}\/?$/.test(u.pathname)}catch{return false}
}
export const isPawchiveCover=value=>/^https:\/\/file\.pawchive\.pw\/data\//.test(value)||/^https:\/\/img\.pawchive\.pw\/thumbnail\/data\//.test(value);
export function originalKey(value){
 try{const u=new URL(value);let m;
 if(['patreon.com','www.patreon.com'].includes(u.hostname)&&(m=u.pathname.match(/^\/(?:[a-zA-Z0-9_-]+\/)?posts\/(?:[a-zA-Z0-9_-]+-)?([1-9]\d{0,19})\/?$/)))return 'patreon:'+m[1];
 if(['fanbox.cc','www.fanbox.cc'].includes(u.hostname))m=u.pathname.match(/^\/@[a-zA-Z0-9_-]{1,64}\/posts\/([1-9]\d{0,19})\/?$/);
 else if(/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.fanbox\.cc$/.test(u.hostname))m=u.pathname.match(/^\/posts\/([1-9]\d{0,19})\/?$/);
 if(m)return 'fanbox:'+m[1];
 }catch{}return value;
}
export function mergeOriginals(links=[],selected=[]){
 const result=[...links];
 for(const link of selected)if(!result.some(old=>originalKey(old.url)===originalKey(link.url)))result.push({url:link.url,label:link.label,is_primary:false});
 return result;
}
