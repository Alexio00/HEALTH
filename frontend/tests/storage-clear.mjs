// HEALTH PR #103 CT-01: cross-tab localStorage.clear() regression.
// Executes actual shipped Auth storage listener and actual clearMedicalUi/UI listener.
// Entire test is synthetic: no production network, credentials or medical content.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const authSource = readFileSync("frontend/supabase-client.js", "utf8");
const appSource = readFileSync("frontend/app.js", "utf8");
const KEY = "health.session.v1";
const MARKER = "health.session.revoked.v1";
const sessionPayload = () => ({
  access_token: "synthetic_access", refresh_token: "synthetic_refresh",
  user: { id: "synthetic-owner" }, expires_in: 3600
});
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
function authHarness() {
  const localMap = new Map(), sessionMap = new Map();
  const storage = m => ({
    getItem: key => m.get(key) ?? null,
    setItem: (key, v) => m.set(key, v),
    removeItem: key => m.delete(key),
    clear: () => m.clear()
  });
  const localStorage = storage(localMap), sessionStorage = storage(sessionMap);
  let listener, response = async () => ({ ok: true, status: 200, json: async () => sessionPayload() });
  const calls = [];
  const window = { addEventListener(type, fn) { if (type === "storage") listener = fn; } };
  const factory = new Function("localStorage", "sessionStorage", "window", "fetch",
    authSource.replace("export function createClient(", "function createClient(") +
    "\nreturn createClient;");
  const client = factory(localStorage, sessionStorage, window, (...args) => {
    calls.push(args[0]);
    return response(...args);
  })("https://synthetic.invalid", "pk_synthetic");
  assert.equal(typeof listener, "function", "real Auth storage handler bound");
  const notify = (area, key, oldValue, newValue) =>
    listener({ storageArea: area, key, oldValue, newValue });
  return {
    client, localStorage, sessionStorage, localMap, sessionMap, notify, calls,
    setResponse: fn => { response = fn; }
  };
}
const first = appSource.indexOf("function clearMedicalUi() {");
const stop = appSource.indexOf("logoutButton.addEventListener", first);
const eventStart = appSource.indexOf('window.addEventListener("storage", (event) => {', stop);
const eventEnd = appSource.indexOf("\n});", eventStart);
assert(first >= 0 && stop > first && eventStart > stop && eventEnd > eventStart);
const clearUI = appSource.slice(first, stop);
const eventUI = appSource.slice(eventStart, eventEnd + 4);
function uiHarness(localStorage, sessionStorage) {
  let storageHandler, screen = "app", timers = 0;
  const window = { addEventListener(type, fn) { if(type === "storage") storageHandler = fn; } };
  const view = { innerHTML:"SYNTHETIC_MEDICAL_DOM", replaceChildren(){this.innerHTML="";} };
  const tags = new Set(["synthetic-tag"]);
  const loginError = {textContent:""};
  const password = { value: "synthetic-password" };
  const location = {hash:"#/records/synthetic"};
  const login = {};
  const build = new Function(
    "window","localStorage","sessionStorage","cancelNeutralMidnight","showOnly",
    "login","view","recordTagFilters","clearPinnedHeaders","document",
    "loginError","location",
    "let uiGeneration=0;\n" + clearUI + eventUI +
    "\nreturn {generation:()=>uiGeneration};"
  );
  const { generation } = build(window,localStorage,sessionStorage,
    ()=>{timers++;},target=>{if (target===login) screen="login";},login,view,tags,
    ()=>{}, {querySelector: selector=>selector==="#password"?password:null}, loginError, location);
  return {
    view,tags,password,location,loginError,generation,
    notify:event=>storageHandler(event),
    get screen(){return screen;},get timers(){return timers;}
  };
}

// Real cross-tab clear: exact StorageEvent semantics (key/old/newValue all null).
{
  const h = authHarness();
  const ui = uiHarness(h.localStorage,h.sessionStorage);
  const signed = await h.client.auth.signInWithPassword({email:"owner@example.invalid",password:"synthetic"});
  assert.equal(signed.error,null);
  assert(h.localMap.has(KEY),"session saved before other-tab clear");
  h.localStorage.clear();
  const event = { key:null, oldValue:null, newValue:null, storageArea:h.localStorage };
  h.notify(event.storageArea,event.key,event.oldValue,event.newValue);
  ui.notify(event);
  assert.equal(h.sessionMap.get(MARKER),"1","clear invalidates Auth tombstone");
  assert.equal((await h.client.auth.getSession()).data.session,null,"no session remains");
  assert.equal(ui.screen,"login","visible medical screen hidden");
  assert.equal(ui.view.innerHTML,"","sensitive medical DOM wiped immediately");
  assert.equal(ui.tags.size,0,"tags wiped");
  assert.equal(ui.password.value,"","credential input wiped");
  assert.equal(ui.generation(),1,"pending medical renders invalidated by generation");
  assert.equal(ui.location.hash,"#/","route reset");
}
// An in-flight password login must never resurrect after cross-tab clear.
{
  const h=authHarness();
  const pending=deferred();
  h.setResponse(async()=>pending.promise);
  const login=h.client.auth.signInWithPassword({email:"owner@example.invalid",password:"synthetic"});
  await Promise.resolve();
  h.localStorage.clear();
  h.notify(h.localStorage,null,null,null);
  pending.resolve({ok:true,status:200,json:async()=>sessionPayload()});
  assert((await login).error,"pending login denied after clear");
  assert.equal(h.localMap.has(KEY),false,"no stale token persisted");
  assert.equal(h.sessionMap.get(MARKER),"1","revocation marker retained");
}
// An in-flight refresh must also be invalidated; no stale access token after clear.
{
  const h=authHarness();
  assert.equal((await h.client.auth.signInWithPassword({
    email:"owner@example.invalid",password:"synthetic"})).error,null);
  const stored=JSON.parse(h.localMap.get(KEY));
  stored.expires_at=1;
  h.localMap.set(KEY,JSON.stringify(stored));
  const pending=deferred();
  h.setResponse(async()=>pending.promise);
  const refresh=h.client.auth.getSession();
  await Promise.resolve();
  h.localStorage.clear();
  h.notify(h.localStorage,null,null,null);
  pending.resolve({ok:true,status:200,json:async()=>sessionPayload()});
  assert.equal((await refresh).data.session,null,"stale refresh response discarded");
  assert.equal(h.localMap.has(KEY),false);
}
// localStorage.removeItem still works without storageArea (older synthetic harness).
{
  const h=authHarness();
  const ui=uiHarness(h.localStorage,h.sessionStorage);
  ui.notify({key:KEY,oldValue:"synthetic-old",newValue:null});
  assert.equal(ui.generation(),1);
  h.notify(undefined,KEY,"synthetic-old",null);
  assert.equal(h.sessionMap.get(MARKER),"1");
}
// No false invalidation from another StorageArea or unrelated key.
{
  const h=authHarness();
  const ui=uiHarness(h.localStorage,h.sessionStorage);
  const held=deferred();
  h.setResponse(async()=>held.promise);
  const login=h.client.auth.signInWithPassword({email:"owner@example.invalid",password:"synthetic"});
  await Promise.resolve();
  for (const event of [
    {key:null,oldValue:null,newValue:null,storageArea:h.sessionStorage},
    {key:"irrelevant",oldValue:"a",newValue:"b",storageArea:h.localStorage},
    {key:null,oldValue:null,newValue:null} // no evidence this was localStorage.clear()
  ]) {
    h.notify(event.storageArea,event.key,event.oldValue,event.newValue);
    ui.notify(event);
  }
  assert.equal(ui.generation(),0,"unrelated storage events do not touch UI");
  assert.equal(ui.view.innerHTML,"SYNTHETIC_MEDICAL_DOM");
  held.resolve({ok:true,status:200,json:async()=>sessionPayload()});
  assert.equal((await login).error,null,"unrelated storage event cannot cancel login");
  assert(h.localMap.has(KEY));
}
console.log("PASS CT-01 localStorage.clear: UI wipe, epoch, stale login/refresh rejection, unrelated-area denial");
