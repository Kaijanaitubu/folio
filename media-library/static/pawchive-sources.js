export function isPawchiveSource(value){
 try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&['pawchive.pw','www.pawchive.pw'].includes(u.hostname)&&!u.username&&!u.password&&(!u.port||['80','443'].includes(u.port))&&/^\/(fanbox|patreon)\/(?:user\/[1-9]\d{0,19}\/)?post\/[1-9]\d{0,19}\/?$/.test(u.pathname)}catch{return false}
}
export const isPawchiveCover=value=>/^https:\/\/file\.pawchive\.pw\/data\//.test(value)||/^https:\/\/img\.pawchive\.pw\/thumbnail\/data\//.test(value);
