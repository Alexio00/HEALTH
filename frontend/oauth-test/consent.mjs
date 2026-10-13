import { consentAllowed,callbackAllowed,connectionConfigAllowed } from './consent-policy.mjs';
// Runtime parameters live in private TEST configuration, never in public GitHub.
let CONFIG=null;
const CONFIG_URL='https://yjmcesdayfmfissghzgm.supabase.co/functions/v1/health-chat-mcp-test-v1/connection-info';
const ROOT='https://yjmcesdayfmfissghzgm.supabase.co/auth/v1';
const $=id=>document.getElementById(id);
const status=text=>{$('status').textContent=text;};
const authId=new URL(location.href).searchParams.get('authorization_id');
let token=null;
let reviewed=null;
async function request(path,body,session) {
 const response=await fetch(ROOT+path,{method:body===undefined?'GET':'POST',
  headers:{apikey:CONFIG.publishableKey,...(session?{authorization:'Bearer '+session}:{}),
   ...(body===undefined?{}:{'content-type':'application/json'})},
  ...(body===undefined?{}:{body:JSON.stringify(body)}),cache:'no-store',credentials:'omit',redirect:'error'});
 if(!response.ok)throw Error('AUTH_REQUEST_REJECTED');
 return response.json();
}
async function loadReview() {
 const details=await request('/oauth/authorizations/'+authId,undefined,token);
 if(!consentAllowed(details,CONFIG))throw Error('UNACCEPTED_CLIENT_CALLBACK_OR_SCOPE');
 reviewed=details;
 $('details').textContent=JSON.stringify({client:details.client.name,client_id:details.client.id,
  callback:details.redirect_uri,scope:details.scope},null,2);
 $('review').hidden=false;$('login').hidden=true;$('approve').disabled=false;$('deny').disabled=false;
 status('Проверь приложение и адрес возврата. Токены остаются в памяти этой страницы.');
}
$('login').addEventListener('submit',async event=>{
 event.preventDefault();const form=event.currentTarget;
 try{
  status('Проверяю вход…');
  const result=await request('/token?grant_type=password',{email:form.elements.email.value,password:form.elements.password.value});
  form.elements.password.value='';
  if(typeof result.access_token!=='string')throw Error('SESSION_MISSING');token=result.access_token;
  await loadReview();
 }catch{token=null;reviewed=null;form.elements.password.value='';status('Вход или подключение отклонены. Проверь учётную запись и настройки OAuth.');}
});
for(const action of ['approve','deny'])$(action).addEventListener('click',async()=>{
 $('approve').disabled=true;$('deny').disabled=true;
 try{
  if(!token||!reviewed)throw Error('REVIEW_REQUIRED');
  // Re-read before consent; accepted client, exact callback and scope must still match.
  const current=await request('/oauth/authorizations/'+authId,undefined,token);
  if(!consentAllowed(current,CONFIG))throw Error('REVIEW_CHANGED');
  const result=await request('/oauth/authorizations/'+authId+'/consent',{action},token);
  if(!callbackAllowed(result.redirect_url,CONFIG.callback))throw Error('CALLBACK_REJECTED');
  token=null;reviewed=null;location.assign(result.redirect_url);
 }catch{token=null;reviewed=null;status('Результат согласия не подтверждён. Не повторяй автоматически; начни новое подключение.');}
});
async function initialize() {
 if(typeof authId!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(authId)){
  status('Начни подключение из ChatGPT: отсутствует корректный запрос OAuth.');return;
 }
 try {
  const response=await fetch(CONFIG_URL,{method:'GET',cache:'no-store',credentials:'omit',
   redirect:'error',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(5000)});
  if(!response.ok)throw Error('CONFIG_UNAVAILABLE');
  const text=await response.text();if(text.length>2048)throw Error('CONFIG_TOO_LARGE');
  const config=JSON.parse(text);if(!connectionConfigAllowed(config))throw Error('CONFIG_REJECTED');
  CONFIG=Object.freeze(config);
  $('login').querySelector('button').disabled=false;
  status('Войди в существующую учётную запись HEALTH-TEST.');
 }catch{CONFIG=null;status('Настройка подключения недоступна. Вход закрыт до её проверки.');}
}
initialize();
window.addEventListener('pagehide',()=>{token=null;reviewed=null;});
