import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { connectionConfigAllowed,consentAllowed,callbackAllowed,authorizationIdFromURL } from '../oauth-test/consent-policy.mjs';

// All identities and values in this test are synthetic, not deployed configuration.
const config={publishableKey:'sb_publishable_SYNTHETIC_ONLY_000000000000',
 clientId:'00000000-0000-4000-8000-000000000002',
 callback:'https://chatgpt.com/connector/oauth/synthetic'};
assert(connectionConfigAllowed(config));
for(const bad of [null,{}, {...config,owner_subject:'synthetic-owner'},
 {...config,publishableKey:'eyJ_SYNTHETIC_LEGACY'}, {...config,clientId:'invalid'},
 {...config,callback:'https://evil.example/connector/oauth/synthetic'},
 {...config,callback:config.callback+'?state=x'}, {...config,callback:config.callback+'#token'}]) {
 assert.equal(connectionConfigAllowed(bad),false);
}
const details={client:{id:config.clientId},redirect_uri:config.callback,scope:'openid'};
assert(consentAllowed(details,config));
assert(!consentAllowed({...details,scope:'openid profile'},config));
assert(!consentAllowed({...details,client:{id:'other'}},config));
assert(!consentAllowed({...details,redirect_uri:'https://evil.example'},config));
assert(callbackAllowed(config.callback+'?code=synthetic&state=synthetic',config.callback));
assert(!callbackAllowed('https://evil.example',config.callback));

const source=readFileSync('frontend/oauth-test/consent.mjs','utf8').replace(/^import .*;\s*$/m,'');
async function initializeScenario(body,query='?authorization_id='+('a'.repeat(32)),ok=true){
 const button={disabled:true},elements=new Map(),requests=[];
 const el=id=>{
  if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,disabled:true,
   addEventListener(){},querySelector(){return button;}});
  return elements.get(id);
 };
 const context=vm.createContext({connectionConfigAllowed,consentAllowed,callbackAllowed,authorizationIdFromURL,
  document:{getElementById:el},location:{href:'https://example.invalid/HEALTH/oauth-test/consent.html'+query},
  window:{addEventListener(){}},URL,AbortSignal,
  fetch:async(url,init)=>{requests.push({url,init});return {ok,text:async()=>body};}});
 vm.runInContext(source,context);
 await new Promise(setImmediate);
 return {button,requests,status:el('status').textContent};
}
const valid=await initializeScenario(JSON.stringify(config));
assert.equal(valid.button.disabled,false);
assert.equal(valid.requests.length,1);
assert.equal(valid.requests[0].url,'https://yjmcesdayfmfissghzgm.supabase.co/functions/v1/health-chat-mcp-test-v1/connection-info');
assert.equal(valid.requests[0].init.credentials,'omit');
assert.equal(valid.requests[0].init.redirect,'error');
assert.equal(valid.requests[0].init.referrerPolicy,'no-referrer');
assert.equal(valid.requests[0].init.cache,'no-store');
for(const body of ['not JSON','x'.repeat(2049),JSON.stringify({...config,owner_subject:'synthetic'})]) {
 const r=await initializeScenario(body);assert.equal(r.button.disabled,true);
 assert.equal(r.requests.length,1);assert(r.status.includes('Вход закрыт'));
}
assert.equal((await initializeScenario(JSON.stringify(config),undefined,false)).button.disabled,true);
for(const query of ['', '?authorization_id=invalid',
 '?authorization_id=00000000-0000-4000-8000-000000000003',
 '?authorization_id='+('a'.repeat(31)), '?authorization_id='+('a'.repeat(33)),
 '?authorization_id='+('a'.repeat(32))+'&authorization_id='+('b'.repeat(32)),
 '?authorization_id='+encodeURIComponent('../'.repeat(10)+'ab')]) {
 const r=await initializeScenario(JSON.stringify(config),query);
 assert.equal(r.button.disabled,true);assert.equal(r.requests.length,0);
}
const base='https://example.invalid/consent?authorization_id=';
for(const id of ['a'.repeat(32),'Ab09Z'.repeat(6)+'XY']){
 assert.equal(authorizationIdFromURL(base+id),id);
 assert.equal((await initializeScenario(JSON.stringify(config),'?authorization_id='+id)).button.disabled,false);
}
assert.equal(authorizationIdFromURL('not a URL'),null);
assert.equal(authorizationIdFromURL(base+'a'.repeat(32)+'%2F'),null);
assert.equal(authorizationIdFromURL(base+'a'.repeat(31)+'_'),null);
assert.equal(authorizationIdFromURL(base+'a'.repeat(31)+'-'),null);
assert(!consentAllowed({...details,scope:'openid email offline_access'},config),
 'real ChatGPT scope shape must remain blocked until separately accepted');
// A valid request can reach login, but wider scopes never reach owner consent.
{
 const elements=new Map(),requests=[],handlers=new Map(),button={disabled:true};
 const el=id=>{
  if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,disabled:true,
   addEventListener(type,fn){handlers.set(id+':'+type,fn);},querySelector(){return button;}});
  return elements.get(id);
 };
 const context=vm.createContext({connectionConfigAllowed,consentAllowed,callbackAllowed,authorizationIdFromURL,
  document:{getElementById:el},location:{href:base+'a'.repeat(32)},
  window:{addEventListener(){}},URL,AbortSignal,fetch:async(url,init)=>{
   requests.push({url,init});
   if(url.endsWith('/connection-info'))return {ok:true,text:async()=>JSON.stringify(config)};
   if(url.includes('/token?'))return {ok:true,json:async()=>({access_token:'SYNTHETIC_TOKEN'})};
   return {ok:true,json:async()=>({...details,scope:'openid email offline_access'})};
  }});
 vm.runInContext(source,context);await new Promise(setImmediate);
 const form={elements:{email:{value:'synthetic@example.invalid'},password:{value:'SYNTHETIC_PASSWORD'}}};
 await handlers.get('login:submit')({preventDefault(){},currentTarget:form});
 assert.equal(form.elements.password.value,'');
 assert(el('status').textContent.includes('scope шире openid'));
 assert.equal(el('approve').disabled,true);assert.equal(el('deny').disabled,true);
 assert.equal(requests.length,3);
 assert(!requests.some(r=>r.url.endsWith('/consent')));
}
console.log('PASS TEST consent config projection, callback/scope, fail-closed network and login gates');

