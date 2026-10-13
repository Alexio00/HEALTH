// Pure validation; neither user credentials nor server identity are trusted here.
export function consentAllowed(details, config) {
 return typeof config.clientId==='string' && config.clientId.length>0
  && typeof config.callback==='string' && config.callback.startsWith('https://chatgpt.com/')
  && details?.client?.id===config.clientId && details.redirect_uri===config.callback
  && typeof details.scope==='string' && details.scope.trim()==='openid';
}
export function callbackAllowed(value, exact) {
 try {
  const u=new URL(value), e=new URL(exact);
  return u.origin==='https://chatgpt.com' && e.origin===u.origin && e.pathname===u.pathname
   && !u.username && !u.password && !u.hash && !e.search && !e.hash;
 } catch { return false; }
}
