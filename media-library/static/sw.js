// Folio deliberately never caches images, API responses or library data.
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
 if(event.request.mode!=='navigate')return;
 event.respondWith(fetch(event.request).catch(()=>new Response('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Folio</title><h1>Folio</h1><p>The server is unavailable. Check the Folio server and your Tailscale connection, then reload.</p><p>サーバーに接続できません。FolioサーバーとTailscaleの接続を確認して、再読み込みしてください。</p></html>',{status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})));
});
