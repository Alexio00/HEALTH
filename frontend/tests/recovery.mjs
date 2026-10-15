// Issue #102: execute the real shipped client and UI handlers with synthetic fetch/DOM.
// No live Supabase, medical SELECT, email delivery, or production credentials.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync("frontend/supabase-client.js", "utf8");
const appSource = readFileSync("frontend/app.js", "utf8");
const html = readFileSync("frontend/index.html", "utf8");
const STORAGE = "health.session.v1";
const makeClient = new Function("localStorage", "sessionStorage", "window", "fetch",
  source.replace("export function createClient(", "function createClient(") +
  "\nreturn createClient;");
const response = (status = 200, data = {}) =>
  ({ status, ok: status >= 200 && status < 300, json: async () => data });
function held() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
function harness() {
  const ls = new Map(), ss = new Map(), listeners = [], calls = [];
  let network = async () => response();
  const storage = store => ({
    getItem: key => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, value),
    removeItem: key => store.delete(key)
  });
  const client = makeClient(storage(ls), storage(ss),
    { addEventListener: (type, fn) => { if(type === "storage") listeners.push(fn); } },
    async (url, init) => {
      calls.push({ url, method: init.method, auth: init.headers.Authorization,
        body: init.body ? JSON.parse(init.body) : null, cache: init.cache });
      return network(url, init);
    })("https://synthetic.invalid", "pk_synthetic");
  return {
    client, calls, ls, ss, listeners, setNetwork: fn => { network = fn; },
    storageEvent: (oldValue, newValue) => listeners.forEach(fn =>
      fn({key: STORAGE, oldValue, newValue}))
  };
}
const fragment = (more = "") => "#access_token=synthetic-recovery-access" +
  "&refresh_token=synthetic-recovery-refresh&token_type=bearer&expires_in=3600&type=recovery" + more;
const VALID_USER = { id: "synthetic-user" };
const recoveryNetwork = () => async (url) => {
  if (url.endsWith("/user")) return response(200, VALID_USER);
  return response();
};

// The only outbound email redirect is the pinned HTTPS PWA path; no SDK required.
{
  const h = harness();
  h.setNetwork(async () => response(200));
  assert.equal((await h.client.auth.requestPasswordRecovery("owner@example.invalid")).error, null);
  assert.equal(h.calls[0].method, "POST");
  assert.equal(h.calls[0].cache, "no-store");
  const u = new URL(h.calls[0].url);
  assert.equal(u.pathname, "/auth/v1/recover");
  assert.equal(u.searchParams.get("redirect_to"), "https://alexio00.github.io/HEALTH/");
  assert.deepEqual(h.calls[0].body, { email: "owner@example.invalid" });
  assert.equal(h.calls[0].auth, undefined);
  assert((await h.client.auth.requestPasswordRecovery("bad")).error);
  assert.equal(h.calls.length, 1, "invalid input never makes a network request");
  h.setNetwork(async () => response(429));
  assert((await h.client.auth.requestPasswordRecovery("owner@example.invalid")).error);
}

// Invalid callback variants must never reach /user, /rest/v1, or the medical router.
for (const invalid of [
  "", "#/records/SYNTHETIC", "#type=recovery", "#access_token=synthetic&token_type=bearer&type=magiclink",
  fragment("&untrusted=1"), fragment("&type=recovery"),
  fragment().replace("token_type=bearer", "token_type=mac"),
  fragment().replace("refresh_token=synthetic-recovery-refresh&", ""),
  fragment().replace("expires_in=3600", "expires_in=0"),
  fragment().replace("expires_in=3600", "expires_in=invalid"),
  fragment().replace("access_token=synthetic-recovery-access", "access_token=")
]) {
  const h = harness();
  h.ls.set(STORAGE, JSON.stringify({access_token:"old",refresh_token:"old"}));
  const result = await h.client.auth.beginPasswordRecovery(invalid);
  assert(result.error, "malformed fragment denied");
  assert.equal(h.ls.has(STORAGE), false, "old reader session cleared");
  assert.equal(h.calls.length, 0, "no server request for malformed fragment");
}
{
  const h = harness();
  h.setNetwork(async (url) => url.endsWith("/user") ? response(401) : response());
  assert((await h.client.auth.beginPasswordRecovery(fragment())).error);
  assert.equal(h.calls.filter(x=>x.method==="GET").length,1);
  assert((await h.client.auth.finishPasswordRecovery("synthetic-long-password")).error);
  assert(!h.calls.some(x=>x.method==="PUT"));
}
{
  const h = harness();
  h.setNetwork(recoveryNetwork());
  assert.equal((await h.client.auth.beginPasswordRecovery(fragment())).error,null);
  assert.equal(h.ls.has(STORAGE), false, "recovery JWT NEVER persisted");
  assert.equal(h.ss.get("health.session.revoked.v1"),"1","ordinary session stays revoked");
  const update = await h.client.auth.finishPasswordRecovery("synthetic-long-password");
  assert.equal(update.error,null);
  assert.equal(update.updated,true);
  assert.equal(update.logoutConfirmed,true);
  assert.deepEqual(h.calls.map(x=>[x.method,new URL(x.url).pathname]),[
    ["GET","/auth/v1/user"],["PUT","/auth/v1/user"],["POST","/auth/v1/logout"]]);
  assert.equal(h.calls[1].auth,"Bearer synthetic-recovery-access");
  assert.deepEqual(h.calls[1].body,{password:"synthetic-long-password"});
  assert.equal(h.ls.has(STORAGE),false);
  assert((await h.client.auth.finishPasswordRecovery("synthetic-long-password")).error,
    "link consumed after successful update");
  assert.equal(h.calls.filter(x=>x.method==="PUT").length,1);
}
{
  const h = harness();
  h.setNetwork(recoveryNetwork());
  assert.equal((await h.client.auth.beginPasswordRecovery(fragment())).error,null);
  const [first,second] = await Promise.all([
    h.client.auth.finishPasswordRecovery("synthetic-long-password"),
    h.client.auth.finishPasswordRecovery("synthetic-long-password")
  ]);
  assert.equal([first,second].filter(x=>x.updated).length,1);
  assert.equal(h.calls.filter(x=>x.method==="PUT").length,1,"double submit fail closed");
}
for (const status of [400,401,422,500]) {
  const h = harness(); h.setNetwork(async url => {
    if (url.endsWith("/user")) return response(200,VALID_USER);
    if (url.endsWith("/logout")) return response(204);
    return response(status);
  });
  assert.equal((await h.client.auth.beginPasswordRecovery(fragment())).error,null);
  const result = await h.client.auth.finishPasswordRecovery("synthetic-long-password");
  assert(result.error);
  assert.equal(result.updated,false);
  assert.equal(h.calls.filter(x=>x.method==="PUT").length,1);
  assert.equal(h.calls.filter(x=>x.url.endsWith("/logout")).length,1);
}
{
  const h = harness();
  h.setNetwork(async url => url.endsWith("/user") ? response(200,VALID_USER)
    : url.endsWith("/logout") ? response(503) : response());
  await h.client.auth.beginPasswordRecovery(fragment());
  const result = await h.client.auth.finishPasswordRecovery("synthetic-long-password");
  assert(result.updated && !result.logoutConfirmed,"unconfirmed remote logout reported");
  assert.equal(h.ls.has(STORAGE),false,"no medical session even on logout failure");
}
{
  const h = harness();
  const pending = held();
  h.setNetwork(async url => url.endsWith("/user") ? pending.promise : response());
  const entering = h.client.auth.beginPasswordRecovery(fragment());
  await Promise.resolve();
  h.storageEvent(null,"another-tab-session");
  pending.resolve(response(200,VALID_USER));
  assert((await entering).error,"cross-tab replacement invalidates pending recovery");
  assert((await h.client.auth.finishPasswordRecovery("synthetic-long-password")).error);
  assert(!h.calls.some(x=>x.method==="PUT"));
}
{
  const h = harness();
  const pending = held();
  h.setNetwork(async url => url.includes("grant_type=password") ? pending.promise
    : url.endsWith("/user") ? response(200,VALID_USER) : response());
  const signIn = h.client.auth.signInWithPassword({email:"synthetic@example.invalid",password:"synthetic"});
  await Promise.resolve();
  assert.equal((await h.client.auth.beginPasswordRecovery(fragment())).error,null);
  pending.resolve(response(200, {access_token:"LATE",refresh_token:"LATE",user:VALID_USER}));
  assert((await signIn).error,"in-flight login cannot restore reader session after recovery start");
  assert.equal(h.ls.has(STORAGE),false);
  await h.client.auth.cancelPasswordRecovery();
}
{
  const h = harness();
  h.setNetwork(recoveryNetwork());
  await h.client.auth.beginPasswordRecovery(fragment());
  assert((await h.client.auth.finishPasswordRecovery("short")).error);
  assert(!h.calls.some(x=>x.method==="PUT"),"short password rejected locally");
}
{
  const h = harness();
  h.setNetwork(async () => { throw new Error("TOKEN_SYNTHETIC_SECRET"); });
  const result = await h.client.auth.beginPasswordRecovery(fragment());
  assert(result.error && !result.error.message.includes("TOKEN_SYNTHETIC_SECRET"),
    "network error never exposes credentials");
}

// Execute shipped UI event handlers, not a second test-only implementation.
const start = appSource.indexOf("// The public recovery UI never fetches medical rows");
const end = appSource.indexOf('loginForm.addEventListener("submit"', start);
assert(start >= 0 && end > start);
const uiSource = appSource.slice(start,end);
function element() {
  const handlers = new Map();
  return {
    handlers, value:"", textContent:"", disabled:false,
    classList: { hidden:false, contains(name) { return this.hidden && name==="hidden"; } },
    addEventListener(type,fn) { handlers.set(type,fn); },
    reportValidity() { return true; }, focus() {}
  };
}
function uiHarness(auth) {
  const ids = ["#forgot-password","#email","#recovery-email","#recovery-send",
    "#recovery-request-status","#recovery-request-back","#recovery-password",
    "#recovery-password-confirm","#recovery-save","#recovery-reset-status",
    "#recovery-reset-back"];
  const map = Object.fromEntries(ids.map(id=>[id,element()]));
  const login=element(),recoveryRequest=element(),recoveryReset=element(),loading=element();
  recoveryRequest.classList.hidden = true;
  recoveryReset.classList.hidden = true;
  const loginError=element(), loginStatus=element(), view={replaceChildren() {this.empty=true;}};
  const document={querySelector: id => map[id]};
  const recoveryRequestForm=element(),recoveryResetForm=element();
  const shown=[];
  const showOnly = el => {
    for(const section of [login,recoveryRequest,recoveryReset,loading])
      section.classList.hidden = section !== el;
    shown.push(el);
  };
  const run = new Function("document","supabase","loginError","loginStatus","login",
    "recoveryRequest","recoveryReset","recoveryRequestForm","recoveryResetForm",
    "showOnly","view","loading","uiGeneration",uiSource +
    "\nreturn {bootRecovery};");
  const { bootRecovery } = run(document,{auth},loginError,loginStatus,login,
    recoveryRequest,recoveryReset,recoveryRequestForm,recoveryResetForm,
    showOnly,view,loading,0);
  return {map,login,recoveryRequest,recoveryReset,recoveryRequestForm,recoveryResetForm,
    loginError,loginStatus,bootRecovery,shown};
}
{
  let requests = 0;
  const ui=uiHarness({
    requestPasswordRecovery: async () => {requests++; return {error:new Error("429")};},
    finishPasswordRecovery: async () => ({updated:true,logoutConfirmed:true}),
    beginPasswordRecovery: async () => ({error:null}),
    cancelPasswordRecovery: async () => {}
  });
  ui.map["#email"].value="owner@example.invalid";
  ui.map["#forgot-password"].handlers.get("click")();
  assert.equal(ui.map["#recovery-email"].value,"owner@example.invalid");
  await Promise.all([ui.recoveryRequestForm.handlers.get("submit")({preventDefault(){}}),
    ui.recoveryRequestForm.handlers.get("submit")({preventDefault(){}})]);
  assert.equal(requests,1,"actual submit handler prevents two fast submits");
  assert.match(ui.map["#recovery-request-status"].textContent,/Если адрес зарегистрирован/);
  await ui.bootRecovery(fragment());
  assert.equal(ui.recoveryReset.classList.hidden,false);
  ui.map["#recovery-password"].value="synthetic-long-password";
  ui.map["#recovery-password-confirm"].value="mismatch";
  await ui.recoveryResetForm.handlers.get("submit")({preventDefault(){}});
  assert.equal(ui.map["#recovery-reset-status"].textContent,"Пароли не совпадают.");
  ui.map["#recovery-password-confirm"].value="synthetic-long-password";
  await ui.recoveryResetForm.handlers.get("submit")({preventDefault(){}});
  assert.equal(ui.login.classList.hidden,false);
  assert.match(ui.loginStatus.textContent,/Пароль изменён/);
  assert.equal(ui.map["#recovery-password"].value,"");
}
assert(html.includes('id="forgot-password"'));
assert(html.includes('autocomplete="new-password"'));
assert(html.includes('name="referrer" content="no-referrer"'));
assert(/const isRecoveryCandidate[\s\S]*?if \(scrubbed\) void bootRecovery\(fragment\)/.test(appSource));
assert(appSource.includes('if (isRecoveryCandidate)') &&
  appSource.indexOf('if (isRecoveryCandidate)') < appSource.indexOf('await supabase.auth.getSession()'),
  "callback is recognized before reader getSession");
console.log("PASS issue #102 recovery API, invalid callbacks, races, no persisted tokens, real UI handlers");
