const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../assets/js/00-auth-callback.js'),'utf8');
function run(href){const replaced=[];const context={URL,URLSearchParams,window:{location:{href}},history:{state:null,replaceState:(...args)=>replaced.push(args[2])}};vm.runInNewContext(source,context);return {context,replaced};}
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
