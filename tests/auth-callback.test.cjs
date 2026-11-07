const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../assets/js/00-auth-callback.js'),'utf8');
function run(href){
 const replaced=[],listeners={};
 const window={location:{href},addEventListener:(name,fn)=>{(listeners[name]??=[]).push(fn);}};
 const context={URL,URLSearchParams,window,history:{state:null,replaceState:(...args)=>{replaced.push(args[2]);window.location.href=new URL(args[2],window.location.href).href;}}};
 vm.runInNewContext(source,context);return {context,replaced,listeners};
}
test('recovery fragment credentials are removed before page subresources load',()=>{
 const {context,replaced}=run('https://site.invalid/?keep=1#type=recovery&access_token=fixture&refresh_token=secret');
 assert.deepEqual(replaced,['/?keep=1']);assert.ok(context.window.__caAuthCallback.hash.includes('access_token=fixture'));
});
test('query recovery credentials and errors are removed while unrelated query values survive',()=>{
 const {replaced}=run('https://site.invalid/?keep=1&auth=recovery&token_hash=fixture&type=recovery&error_description=private');
 assert.deepEqual(replaced,['/?keep=1']);
});
test('ordinary anchors and navigation remain untouched',()=>{
 const {context,replaced}=run('https://site.invalid/?make=BMW#allGrid');
 assert.deepEqual(replaced,[]);assert.equal(context.window.__caAuthCallback,undefined);
});
test('recovery-only entry markers are captured and removed while ordinary anchors survive',()=>{
 const {context,replaced}=run('https://site.invalid/?keep=1&auth=recovery#allGrid');
 assert.deepEqual(replaced,['/?keep=1#allGrid']);
 assert.equal(context.window.__caAuthCallback.search,'?keep=1&auth=recovery');
});
test('fragment navigation on an existing tab scrubs credentials before notifying auth and is consumed once',()=>{
 const {context,replaced,listeners}=run('https://site.invalid/?keep=1#allGrid');
 const seen=[];
 context.window.caHandleAuthCallback=()=>{seen.push({href:context.window.location.href,callback:context.window.__caAuthCallback});delete context.window.__caAuthCallback;};
 context.window.location.href='https://site.invalid/?keep=1#type=recovery&access_token=fixture&refresh_token=secret';
 listeners.hashchange.forEach(fn=>fn());
 listeners.popstate.forEach(fn=>fn());
 assert.deepEqual(replaced,['/?keep=1']);
 assert.equal(seen.length,1);assert.equal(seen[0].href,'https://site.invalid/?keep=1');
 assert.ok(seen[0].callback.hash.includes('access_token=fixture'));
 assert.equal(context.window.__caAuthCallback,undefined);
});
