export const STORAGE_KEY='folio.work-prototype.v1';
export const clone=value=>JSON.parse(JSON.stringify(value));
export const uid=()=>globalThis.crypto?.randomUUID?.()||'p'+Date.now().toString(36)+Math.random().toString(36).slice(2);
export const unique=values=>[...new Set(values.map(v=>String(v).trim()).filter(Boolean))];
export const dimensionDefaults=[{id:'overall',number:0,name:'総合評価',maximum:5,symbol:'★'}, {id:'story',number:1,name:'ストーリー',maximum:5,symbol:'★'}, {id:'mood',number:2,name:'淫靡さ',maximum:5,symbol:'♥'}, {id:'art',number:3,name:'作画',maximum:5,symbol:'★'}];
const link=(id,site,label,role,languages,pages,dates,primary=false)=>({id,site,label,role,languages,pages,dates,primary,url:'https://example.com/'+id});
export function fixtures(){
 const base={id:'atelier',title:'雨上がりのアトリエ',cover:'./cover.svg',format:'manga',publication:'doujin',creation:'original',authors:['橙野すみ'],circles:['薄明編集室'],tags:[{name:'日常',gender:'none'},{name:'年上',gender:'female'},{name:'短編',gender:'none'}],originals:[],characters:[],series:['雨の日のスケッチ'],age:'adult',ai:'unknown',aiSource:'',review:'雨が止むまでの、少しだけ特別な時間。\n窓の光と静かな会話が印象に残った。',ratings:{overall:4,story:4,mood:3,art:4},marks:[1,4],relations:[{id:'r1',name:'薄明アンソロジー vol.1',entry:'anthology',url:'https://example.com/collection'}],links:[link('store-a','dlsite','DLsite','main',['日本語'],32,[{kind:'release',value:'2026-10-10',label:''}],true),link('store-b','fanza','FANZA · フルカラー版','main',['日本語','English'],40,[{kind:'release',value:'2026-10-12',label:''}]),link('sample','pixiv','pixiv · サンプル','sample',['日本語'],8,[{kind:'published',value:'2026-09-20',label:''},{kind:'other',value:'2026-09',label:'予告掲載'}])]};
 return {version:1,priorities:{dlsite:1,fanza:1,pixiv:2,fanbox:2,other:3},dimensions:clone(dimensionDefaults),characters:[{id:'mio',name:'朝凪ミオ',originals:['星見アカデミア'],blocked:[]},{id:'rei',name:'真白レイ',originals:[],blocked:[]}],works:[base,{...clone(base),id:'stargazer',title:'星見通りの帰り道',creation:'derivative',originals:['星見アカデミア'],characters:['mio'],series:[],relations:[],review:'架空の二次創作サンプル。原作・キャラクター欄の配置を確認できます。',links:[link('fanwork','other','作者公式','main',['日本語'],24,[{kind:'published',value:'2026-10'}],true)]},{...clone(base),id:'anthology',title:'薄明アンソロジー vol.1',format:'cg',publication:'commercial',relations:[],review:'収録先として接続するための架空エントリ。',characters:[],series:[],links:[link('collection','dlsite','DLsite','main',['日本語'],120,[{kind:'release',value:'2026'}],true)]}]};
}
export function blankWork(){return {id:uid(),title:'',cover:'',format:'',publication:'',creation:'',authors:[],circles:[],tags:[],originals:[],characters:[],series:[],age:'adult',ai:'unknown',aiSource:'',review:'',ratings:{},marks:[],relations:[],links:[]};}
export function allLanguages(work){return unique(work.links.flatMap(l=>l.languages));}
const priority=(l,priorities)=>Number(priorities[l.site]??99);
export function representativePages(work,priorities){
 const eligible=work.links.filter(l=>l.role==='main'&&Number.isInteger(l.pages)&&l.pages>=0);
 if(!eligible.length)return null;
 const top=Math.min(...eligible.map(l=>priority(l,priorities)));
 return eligible.filter(l=>priority(l,priorities)===top).reduce((a,b)=>a.pages>=b.pages?a:b);
}
export function validDate(value){
 const m=/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(value||'');
 if(!m||Number(m[1])<1)return false;
 if(!m[2])return true;
 const month=Number(m[2]);if(month<1||month>12)return false;
 if(!m[3])return true;
 const day=Number(m[3]),max=new Date(Date.UTC(Number(m[1]),month,0)).getUTCDate();
 return day>=1&&day<=max;
}
export function representativeDate(work,priorities){
 for(const kind of ['release','published']){
  const eligible=work.links.filter(l=>l.role==='main').flatMap(l=>l.dates.filter(d=>d.kind===kind&&validDate(d.value)).map(d=>({link:l,date:d})));
  if(!eligible.length)continue;
  const top=Math.min(...eligible.map(v=>priority(v.link,priorities)));
  // Preview convention: partial dates sort before longer dates with the same prefix.
  // Preserve and show the original precision; never store a made-up month/day.
  return eligible.filter(v=>priority(v.link,priorities)===top).sort((a,b)=>a.date.value.localeCompare(b.date.value))[0];
 }
 return null;
}
export function associate(work,characters){
 if(work.originals.length!==1)return [];
 const original=work.originals[0],added=[];
 for(const id of work.characters){const c=characters.find(c=>c.id===id);if(c&&!c.originals.includes(original)&&!c.blocked.includes(original)){c.originals.push(original);added.push(c.name);}}
 return added;
}
export function disconnect(character,original){character.originals=character.originals.filter(o=>o!==original);character.blocked=unique([...character.blocked,original]);}
export function reconnect(character,original){character.blocked=character.blocked.filter(o=>o!==original);character.originals=unique([...character.originals,original]);}
export function deriveOverall(values){if(values[0]===5||values[1]===5)return 5;return values.length===3&&values.every(v=>Number.isInteger(v)&&v>=1&&v<=5)?Math.ceil(values.reduce((a,b)=>a+b,0)/3):null;}
export function safeURL(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password}catch{return false;}}
export function errors(work){
 const out=[];
 if(!work.title.trim())out.push({path:'title',key:'needTitle'});
 if(work.cover&&!safeURL(work.cover)&&work.cover!=='./cover.svg')out.push({path:'cover',key:'needURL'});
 for(const [i,l] of work.links.entries()){
  if(!safeURL(l.url))out.push({path:`links.${i}.url`,key:'needURL'});
  if(l.pages!==null&&(!Number.isInteger(l.pages)||l.pages<0))out.push({path:`links.${i}.pages`,key:'needPages'});
  for(const [j,d] of l.dates.entries())if(d.value&&!validDate(d.value))out.push({path:`links.${i}.dates.${j}.value`,key:'needDate'});
 }
 return out;
}
