// Run before subresources. Recovery credentials never remain in the address
// bar, referrers or browser history while the page loads.
(function(){
 const url=new URL(window.location.href),fragment=new URLSearchParams(url.hash.slice(1));
 const keys=['access_token','refresh_token','token_hash','code','type','expires_in','expires_at','token_type','error','error_code','error_description'];
 if(!keys.some(k=>fragment.has(k)||url.searchParams.has(k)))return;
 window.__caAuthCallback={hash:url.hash.slice(1),search:url.search};
 if(keys.some(k=>fragment.has(k)))url.hash='';
 for(const key of keys)url.searchParams.delete(key);
 if(url.searchParams.get('auth')==='recovery')url.searchParams.delete('auth');
 history.replaceState(history.state,'',url.pathname+url.search+url.hash);
})();
