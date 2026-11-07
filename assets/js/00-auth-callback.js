// Run before subresources. Recovery credentials never remain in the address
// bar, referrers or browser history while the page loads.
(function(){
 const keys=['access_token','refresh_token','token_hash','code','type','expires_in','expires_at','token_type','error','error_code','error_description'];
 function capture(){
  const url=new URL(window.location.href),fragment=new URLSearchParams(url.hash.slice(1));
  const recoveryEntry=url.searchParams.get('auth')==='recovery'||fragment.get('auth')==='recovery';
  if(!recoveryEntry&&!keys.some(k=>fragment.has(k)||url.searchParams.has(k)))return false;
  window.__caAuthCallback={hash:url.hash.slice(1),search:url.search};
  if(keys.some(k=>fragment.has(k))||fragment.get('auth')==='recovery')url.hash='';
  for(const key of keys)url.searchParams.delete(key);
  if(url.searchParams.get('auth')==='recovery')url.searchParams.delete('auth');
  history.replaceState(history.state,'',url.pathname+url.search+url.hash);
  return true;
 }
 // A mail app can reuse a tab and deliver only a new fragment. The head script
 // then does not run again, so capture and scrub that navigation before Auth UI.
 function navigate(){if(capture()&&typeof window.caHandleAuthCallback==='function')window.caHandleAuthCallback();}
 capture();
 window.addEventListener('hashchange',navigate);
 window.addEventListener('popstate',navigate);
})();
