// HEALTH #58 synthetic logout regression. No real Supabase access or medical data.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const clientSource = readFileSync(join(here, "../supabase-client.js"), "utf8");
const appSource = readFileSync(join(here, "../app.js"), "utf8");
const STORAGE_KEY = "health.session.v1";
const payload = (name = "old") => ({
  access_token: "synthetic-access-" + name,
  refresh_token: "synthetic-refresh-" + name,
  user: { id: "synthetic-owner" },
  expires_in: 3600
});
const okResponse = (name) => ({ ok: true, status: 200, json: async () => payload(name) });
let count = 0;
function pass(condition, label) {
  assert.ok(condition, label);
  count++;
}
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
function createHarness() {
  const store = new Map();
  const listeners = [];
  const storage = {
    getItem: key => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, value),
    removeItem: key => store.delete(key)
  };
  let network = async () => okResponse("old");
  const fakeWindow = { addEventListener: (type, fn) => { if (type === "storage") listeners.push(fn); } };
  const factory = new Function("localStorage", "window", "fetch",
    clientSource.replace("export function createClient(", "function createClient(") +
    "\nreturn createClient;");
  const client = factory(storage, fakeWindow, (...args) => network(...args))("https://synthetic.invalid", "pk_synthetic");
  return { storage, store, client, listeners, setNetwork: fn => { network = fn; } };
}

{
  const h = createHarness();
  const login = await h.client.auth.signInWithPassword({ email: "owner@example.invalid", password: "synthetic" });
  pass(!login.error && !!h.store.get(STORAGE_KEY), "login");
  const held = deferred();
  h.setNetwork(async () => held.promise);
  const exiting = h.client.auth.signOut();
  pass(h.storage.getItem(STORAGE_KEY) === null, "local tokens cleared before remote reply");
  held.resolve({ ok: false, status: 503 });
  const result = await exiting;
  pass(result.error && !/synthetic-access|synthetic-refresh/.test(result.error.message), "server error sanitized");
  h.setNetwork(async () => okResponse("new"));
  pass(!(await h.client.auth.signInWithPassword({ email: "owner@example.invalid", password: "again" })).error, "relogin");
  h.setNetwork(async () => ({ ok: true, status: 200 }));
  pass((await h.client.auth.signOut()).error === null && h.storage.getItem(STORAGE_KEY) === null, "normal logout");
  pass((await h.client.auth.signOut()).error === null, "repeated logout");
}
{
  const h = createHarness();
  await h.client.auth.signInWithPassword({ email: "owner@example.invalid", password: "synthetic" });
  const stalled = deferred();
  h.setNetwork(async () => stalled.promise);
  h.client.auth.signOut();
  pass(h.storage.getItem(STORAGE_KEY) === null, "timeout / unresolved logout immediately clears local tokens");
  stalled.resolve({ ok: true, status: 200 });
}
{
  const h = createHarness();
  await h.client.auth.signInWithPassword({ email: "owner@example.invalid", password: "synthetic" });
  const current = JSON.parse(h.storage.getItem(STORAGE_KEY));
  current.expires_at = 1;
  h.storage.setItem(STORAGE_KEY, JSON.stringify(current));
  const held = deferred();
  h.setNetwork(async url => url.includes("grant_type=refresh_token") ? held.promise : { ok: true, status: 200 });
  const pendingRefresh = h.client.auth.getSession();
  await Promise.resolve();
  await h.client.auth.signOut();
  held.resolve(okResponse("late-refresh"));
  await pendingRefresh;
  pass(h.storage.getItem(STORAGE_KEY) === null, "late refresh cannot resurrect logout");
}
{
  const h = createHarness();
  await h.client.auth.signInWithPassword({ email: "owner@example.invalid", password: "synthetic" });
  const held = deferred();
  h.setNetwork(async () => held.promise);
  const signIn = h.client.auth.signInWithPassword({ email: "owner@example.invalid", password: "synthetic" });
  await Promise.resolve();
  h.setNetwork(async () => ({ ok: true, status: 200 }));
  await h.client.auth.signOut();
  held.resolve(okResponse("late-signin"));
  const result = await signIn;
  pass(!!result.error && h.storage.getItem(STORAGE_KEY) === null, "late login cannot resurrect logout");
}

const uiPattern = /function clearMedicalUi\(\) \{[\s\S]*?\n\}\n\nlogoutButton\.addEventListener\("click", async \(\) => \{[\s\S]*?\n\}\);[\s\S]*?window\.addEventListener\("storage", \(event\) => \{[\s\S]*?\n\}\);/;
const uiCode = appSource.match(uiPattern)?.[0];
pass(!!uiCode, "actual DOM handler identified");
function simulateUI(signOut) {
  const login = { classList: { contains: () => false } };
  const view = { innerHTML: "SYNTHETIC_MEDICAL_MARKER", replaceChildren() { this.innerHTML = ""; } };
  const recordTagFilters = new Set(["SYNTHETIC_TAG"]);
  const password = { value: "synthetic-password" };
  const loginError = { textContent: "" };
  const location = { hash: "#/records/SYNTHETIC_MARKER" };
  let hidden = false, clicked, stored, pinned = 0;
  const logoutButton = { addEventListener: (type, cb) => { if (type === "click") clicked = cb; } };
  const window = { addEventListener: (type, cb) => { if (type === "storage") stored = cb; } };
  new Function("logoutButton", "showOnly", "login", "view", "recordTagFilters",
    "clearPinnedHeaders", "document", "loginError", "location", "supabase", "window", uiCode)(
    logoutButton, () => { hidden = true; }, login, view, recordTagFilters,
    () => { pinned++; }, { querySelector: () => password }, loginError, location, { auth: { signOut } }, window);
  return { click: clicked, stored, view, loginError, location, recordTagFilters, password, get hidden() { return hidden; }, get pinned() { return pinned; } };
}
{
  const h = simulateUI(async () => ({ error: null }));
  await h.click();
  pass(h.hidden && h.view.innerHTML === "" && h.password.value === "" && h.pinned === 1 &&
    h.location.hash === "#/" && !h.recordTagFilters.size, "normal DOM wipe");
}
{
  const h = simulateUI(async () => { throw Error("sensitive network details"); });
  await h.click();
  pass(h.view.innerHTML === "" && !/sensitive network/.test(h.loginError.textContent), "network failure DOM/error safe");
}
{
  const held = deferred();
  const h = simulateUI(async () => held.promise);
  h.click();
  pass(h.view.innerHTML === "" && h.hidden, "stalled logout DOM immediate");
  held.resolve({ error: null });
}
{
  const h = simulateUI(async () => ({ error: null }));
  h.stored({ key: STORAGE_KEY, newValue: null });
  pass(h.hidden && h.view.innerHTML === "", "other-tab logout DOM wiped");
}
pass(/if \(app\.classList\.contains\("hidden"\)\) \{\s*view\.replaceChildren\(\)/.test(appSource),
  "in-flight old route has hidden-view cleanup guard");
console.log("HEALTH #58 logout synthetic: " + count + "/" + count + " PASS");
