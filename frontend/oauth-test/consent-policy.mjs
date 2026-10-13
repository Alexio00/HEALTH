// Pure validation; neither user credentials nor server identity are trusted here.
export function authorizationIdFromURL(value) {
 try {
  const ids=new URL(value).searchParams.getAll('authorization_id');
  // Supabase issues an opaque 32-character ID, not the authorization row UUID.
  return ids.length===1 && /^[A-Za-z0-9]{32}$/.test(ids[0]) ? ids[0] : null;
 } catch { return null; }
}
export function connectionConfigAllowed(config) {
 if (!config || typeof config !== 'object' || Array.isArray(config)
  || Object.keys(config).sort().join(',') !== 'callback,clientId,publishableKey'
  || typeof config.publishableKey !== 'string'
  || !/^sb_publishable_[A-Za-z0-9_-]{20,80}$/.test(config.publishableKey)
  || typeof config.clientId !== 'string'
  || !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(config.clientId)
  || typeof config.callback !== 'string') return false;
 try {
  const u = new URL(config.callback);
  return u.origin === 'https://chatgpt.com'
   && /^\/connector\/oauth\/[A-Za-z0-9_-]{8,100}$/.test(u.pathname)
   && !u.username && !u.password && !u.search && !u.hash;
 } catch { return false; }
}
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

