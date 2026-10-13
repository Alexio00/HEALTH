import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { webcrypto,createHash } from 'node:crypto';
import { connectionConfigAllowed,consentAllowed,callbackAllowed,authorizationIdFromURL,scopeAllowed,recoveryFromURL,recoveryRecordAllowed,recoverySessionAllowed,RECOVERY_URL,RECOVERY_KEY,RECOVERY_TTL_MS } from '../oauth-test/consent-policy.mjs';
const recoveryAPI={recoveryFromURL,recoveryRecordAllowed,recoverySessionAllowed,RECOVERY_URL,RECOVERY_KEY};

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
const details={client:{id:config.clientId},redirect_uri:config.callback,scope:'openid email offline_access'};
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
 const context=vm.createContext({connectionConfigAllowed,consentAllowed,callbackAllowed,authorizationIdFromURL,...recoveryAPI,
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
assert(consentAllowed({...details,scope:'openid email offline_access'},config));
for(const scope of ['openid','openid email','openid email offline_access profile','openid email offline_access openid','openid  email offline_access'])assert(!scopeAllowed(scope));
for(const scope of ['offline_access email openid','email openid offline_access'])assert(scopeAllowed(scope));
// A valid request can reach login, but wider scopes never reach owner consent.
{
 const elements=new Map(),requests=[],handlers=new Map(),button={disabled:true};
 const el=id=>{
  if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,disabled:true,
   addEventListener(type,fn){handlers.set(id+':'+type,fn);},querySelector(){return button;}});
  return elements.get(id);
 };
 const context=vm.createContext({connectionConfigAllowed,consentAllowed,callbackAllowed,authorizationIdFromURL,...recoveryAPI,
  document:{getElementById:el},location:{href:base+'a'.repeat(32)},
  window:{addEventListener(){}},URL,AbortSignal,fetch:async(url,init)=>{
   requests.push({url,init});
   if(url.endsWith('/connection-info'))return {ok:true,text:async()=>JSON.stringify(config)};
   if(url.includes('/token?'))return {ok:true,json:async()=>({access_token:'SYNTHETIC_TOKEN'})};
   return {ok:true,json:async()=>({...details,scope:'openid email offline_access profile'})};
  }});
 vm.runInContext(source,context);await new Promise(setImmediate);
 const form={elements:{email:{value:'synthetic@example.invalid'},password:{value:'SYNTHETIC_PASSWORD'}}};
 await handlers.get('login:submit')({preventDefault(){},currentTarget:form});
 assert.equal(form.elements.password.value,'');
 assert(el('status').textContent.includes('scope за пределами согласованного TEST-набора'));
 assert.equal(el('approve').disabled,true);assert.equal(el('deny').disabled,true);
 assert.equal(requests.length,3);
 assert(!requests.some(r=>r.url.endsWith('/consent')));
}
console.log('PASS TEST consent config projection, callback/scope, fail-closed network and login gates');

// Password recovery uses synthetic values only; no mail is sent by this suite.
const code='00000000-0000-4000-8000-000000000004';
const now=Date.now(),record={verifier:'a'.repeat(64),startedAt:now};
const session={access_token:'SYNTHETIC.ONLY.TOKEN',token_type:'bearer',expires_in:3600,
 user:{id:'00000000-0000-4000-8000-000000000005',is_anonymous:false}};
assert.deepEqual(recoveryFromURL(RECOVERY_URL),{kind:'start'});
assert.deepEqual(recoveryFromURL(RECOVERY_URL+'&code='+code),{kind:'callback',code});
for(const url of [RECOVERY_URL+'&mode=recovery',RECOVERY_URL+'&authorization_id='+'a'.repeat(32),
 RECOVERY_URL+'&code='+code+'&code='+code,RECOVERY_URL+'&code=bad',RECOVERY_URL+'#access_token=synthetic',
 RECOVERY_URL+'&redirect_to=https://evil.invalid',RECOVERY_URL.replace('alexio00.github.io','evil.invalid'),
 RECOVERY_URL+'&error=access_denied',RECOVERY_URL.replace('mode=recovery','mode=other')])assert.equal(recoveryFromURL(url),null);
assert(recoveryRecordAllowed(record,now));
for(const bad of [null,{...record,token:'synthetic'}, {...record,verifier:'b'.repeat(63)},
 {...record,startedAt:now+1}, {...record,startedAt:now-RECOVERY_TTL_MS}, {...record,startedAt:'now'}])
 assert(!recoveryRecordAllowed(bad,now));
assert(recoverySessionAllowed(session));
for(const bad of [null,{}, {...session,access_token:'raw'}, {...session,expires_in:0},
 {...session,expires_in:86401}, {...session,token_type:'other'},
 {...session,user:{...session.user,is_anonymous:true}}])assert(!recoverySessionAllowed(bad));

async function recoveryScenario({url=RECOVERY_URL,stored=null,failPath='',badSession=false,logoutFail=false,storageFailure=false,wrongUser=false}={}){
 const elements=new Map(),handlers=new Map(),requests=[],historyChanges=[],order=[],storage=new Map();
 if(stored!==null)storage.set(RECOVERY_KEY,stored);
 const el=id=>{
  if(!elements.has(id)){
   const button={disabled:true};
   elements.set(id,{textContent:'',hidden:false,disabled:true,elements:{email:{value:''},password:{value:''},confirmation:{value:''}},
    addEventListener(type,fn){handlers.set(id+':'+type,fn);},querySelector(){return button;}});
  }
  return elements.get(id);
 };
 const localStorage={getItem(k){if(storageFailure)throw Error('storage blocked');return storage.get(k)??null;},
  setItem(k,v){if(storageFailure)throw Error('storage blocked');storage.set(k,v);},removeItem(k){storage.delete(k);}};
 const context=vm.createContext({connectionConfigAllowed,consentAllowed,callbackAllowed,authorizationIdFromURL,...recoveryAPI,
  document:{getElementById:el},location:{href:url},history:{replaceState(a,b,u){historyChanges.push(u);order.push('clean-url');}},
  window:{addEventListener(type,fn){handlers.set('window:'+type,fn);}},URL,AbortSignal,localStorage,
  crypto:webcrypto,Uint8Array,TextEncoder,btoa:s=>Buffer.from(s,'binary').toString('base64'),
  fetch:async(url,init)=>{
   order.push('network');requests.push({url,init});
   if(url.endsWith('/connection-info'))return {ok:failPath!=='config',text:async()=>JSON.stringify(config)};
   const ok=!url.includes(failPath||'NEVER_FAIL') && !(logoutFail && url.includes('/logout'));
   if(url.includes('/token?'))return {ok,json:async()=>badSession?{}:session};
   if(url.endsWith('/user'))return {ok,json:async()=>({id:wrongUser?'different':session.user.id})};
   return {ok,status:url.includes('/logout')?204:200,json:async()=>({})};
  }});
 vm.runInContext(source,context);await new Promise(setImmediate);
 return {el,handlers,requests,historyChanges,order,storage,context,
  submit:async id=>handlers.get(id+':submit')({preventDefault(){},currentTarget:el(id)})};
}
{
 const r=await recoveryScenario();
 assert.equal(r.el('login').hidden,true);assert.equal(r.el('recovery').hidden,false);
 assert.equal(r.el('recover-email').querySelector('button').disabled,false);
 r.el('recover-email').elements.email.value='synthetic@example.invalid';
 await r.submit('recover-email');
 const sent=r.requests.find(x=>x.url.includes('/recover?'));assert(sent);
 const data=JSON.parse(sent.init.body),pending=JSON.parse(r.storage.get(RECOVERY_KEY));
 assert.equal(data.email,'synthetic@example.invalid');assert.equal(data.code_challenge_method,'s256');
 assert.equal(data.code_challenge,createHash('sha256').update(pending.verifier).digest('base64url'));
 assert.equal(new URL(sent.url).searchParams.get('redirect_to'),RECOVERY_URL);
 assert.equal(Object.keys(pending).sort().join(','),'startedAt,verifier');
 assert(!JSON.stringify(pending).includes('synthetic@example.invalid'));
 assert.equal(r.el('recover-email').elements.email.value,'');
 await r.submit('recover-email');assert.equal(r.requests.filter(x=>x.url.includes('/recover?')).length,1);
}
for(const fail of [{failPath:'/recover?'},{storageFailure:true},{failPath:'config'}]){
 const r=await recoveryScenario(fail);r.el('recover-email').elements.email.value='synthetic@example.invalid';
 await r.submit('recover-email');assert.equal(r.storage.size,0);
 assert(!r.requests.some(x=>x.url.endsWith('/user')));
 assert.equal(r.el('recover-password').querySelector('button').disabled,true);
}
{
 const r=await recoveryScenario({url:RECOVERY_URL+'&code='+code,stored:JSON.stringify(record)});
 assert.equal(r.order[0],'clean-url');assert.deepEqual(r.historyChanges,[RECOVERY_URL]);
 assert.equal(r.storage.size,0);assert.equal(r.el('recover-password').querySelector('button').disabled,false);
 const exchange=r.requests.find(x=>x.url.includes('grant_type=pkce'));
 assert.deepEqual(JSON.parse(exchange.init.body),{auth_code:code,code_verifier:record.verifier});
 assert(!r.requests.some(x=>x.url.includes('/oauth/')));
 const f=r.el('recover-password');f.elements.password.value='SYNTHETIC_NEW_PASSWORD';f.elements.confirmation.value='different';
 await r.submit('recover-password');assert.equal(r.requests.filter(x=>x.url.endsWith('/user')).length,0);
 assert.equal(f.elements.password.value,'');assert.equal(f.elements.confirmation.value,'');
 f.elements.password.value='SYNTHETIC_NEW_PASSWORD';f.elements.confirmation.value='SYNTHETIC_NEW_PASSWORD';
 await r.submit('recover-password');
 const update=r.requests.find(x=>x.url.endsWith('/user'));assert.equal(update.init.method,'PUT');
 assert.deepEqual(Object.keys(JSON.parse(update.init.body)),['password']);
 assert.equal(update.init.headers.authorization,'Bearer '+session.access_token);
 assert(r.requests.some(x=>x.url.endsWith('/logout?scope=global') && x.init.method==='POST'));
 assert(r.el('status').textContent.includes('Пароль изменён'));
 assert.equal(f.elements.password.value,'');assert.equal(f.elements.confirmation.value,'');
 await r.submit('recover-password');assert.equal(r.requests.filter(x=>x.url.endsWith('/user')).length,1);
 assert(!r.requests.some(x=>/github|production/.test(x.url)));
 for(const req of r.requests){assert.equal(req.init.credentials,'omit');assert.equal(req.init.cache,'no-store');
  assert.equal(req.init.redirect,'error');assert.equal(req.init.referrerPolicy,'no-referrer');}
}
for(const options of [{stored:null},{stored:JSON.stringify({...record,startedAt:now-RECOVERY_TTL_MS})},
 {stored:JSON.stringify(record),failPath:'/token?'},{stored:JSON.stringify(record),badSession:true},
 {stored:'not-json'},{storageFailure:true}]){
 const r=await recoveryScenario({url:RECOVERY_URL+'&code='+code,...options});
 assert.equal(r.el('recover-password').querySelector('button').disabled,true);
 assert(!r.requests.some(x=>x.url.endsWith('/user')));
 if(options.stored===null || options.storageFailure || options.stored==='not-json')
  assert(!r.requests.some(x=>x.url.includes('grant_type=pkce')));
}
{
 const r=await recoveryScenario({url:RECOVERY_URL+'&code='+code,stored:JSON.stringify(record),logoutFail:true});
 const f=r.el('recover-password');f.elements.password.value='SYNTHETIC_NEW_PASSWORD';f.elements.confirmation.value='SYNTHETIC_NEW_PASSWORD';
 await r.submit('recover-password');assert(r.el('status').textContent.includes('завершение сессий не подтверждено'));
 assert.equal(f.elements.password.value,'');assert.equal(f.querySelector('button').disabled,true);
}
{
 const r=await recoveryScenario({url:RECOVERY_URL+'&code='+code,stored:JSON.stringify(record)});
 r.handlers.get('window:pagehide')();
 const f=r.el('recover-password');f.elements.password.value='SYNTHETIC_NEW_PASSWORD';f.elements.confirmation.value='SYNTHETIC_NEW_PASSWORD';
 await r.submit('recover-password');assert(!r.requests.some(x=>x.url.endsWith('/user')));
}
for(const query of ['&code=bad','&code='+code+'&code='+code,'#access_token=SYNTHETIC']){
 const r=await recoveryScenario({url:RECOVERY_URL+query,stored:JSON.stringify(record)});
 assert.equal(r.requests.length,0);assert.equal(r.el('recover-password').querySelector('button').disabled,true);
}
for(const options of [{failPath:'/user'},{wrongUser:true},{expired:true}]){
 const r=await recoveryScenario({url:RECOVERY_URL+'&code='+code,stored:JSON.stringify(record),...options});
 if(options.expired)vm.runInContext('Date.now=()=>'+(now+16*60*1000),r.context);
 const f=r.el('recover-password');f.elements.password.value='SYNTHETIC_NEW_PASSWORD';f.elements.confirmation.value='SYNTHETIC_NEW_PASSWORD';
 await r.submit('recover-password');assert(!r.el('status').textContent.includes('Пароль изменён'));
 assert.equal(f.elements.password.value,'');assert.equal(f.elements.confirmation.value,'');
 assert.equal(f.querySelector('button').disabled,true);
 if(options.expired)assert(!r.requests.some(x=>x.url.endsWith('/user')));
}
console.log('PASS TEST email recovery: S256 binding, fixed route, storage TTL, replay/failures, password clear, logout and no OAuth consent');


