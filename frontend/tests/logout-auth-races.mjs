// HEALTH PR #100: F-01 adversarial generation regressions, synthetic only.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../app.js"), "utf8");
const authSource = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../supabase-client.js"), "utf8");
function sourceSlice(start, end) {
  const i = src.indexOf(start);
  const j = src.indexOf(end, i + start.length);
  assert.ok(i >= 0 && j > i, "missing source: " + start);
  return src.slice(i, j);
}
const testedCode = [
  sourceSlice("function isActiveUiGeneration(generation) {", "\nconst uniqueValues"),
  sourceSlice("async function enterApp(session, generation) {", "\nasync function boot()"),
  sourceSlice("function clearMedicalUi() {", "\nlogoutButton.addEventListener"),
  sourceSlice("async function route(generation", "\nasync function fetchCaseBundles"),
  sourceSlice("async function renderVaccination(generation) {", "\nasync function renderCurrentState")
].join("\n");
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
function createRuntime(assertReader = async () => true) {
  const app = { hidden: true, classList: { contains(key) { return key === "hidden" && app.hidden; } } };
  const login = { hidden: false };
  const view = { innerHTML: "", replaceChildren() { this.innerHTML = ""; } };
  const recordTagFilters = new Set();
  const loginError = { textContent: "" };
  const location = { hash: "#/vaccination" };
  const pending = [];
  const supabase = {
    auth: { signOut: async () => ({ error: null }) },
    from() {
      return {
        select() { return this; }, contains() { return this; }, order() { return this; },
        then(resolve, reject) {
          const job = pending.shift();
          if (!job) throw Error("unexpected synthetic SELECT");
          return job.promise.then(resolve, reject);
        }
      };
    }
  };
  const make = new Function("app","login","view","recordTagFilters","loginError","location",
    "supabase","assertReader","showOnly","clearPinnedHeaders","document","setupStickyChrome",
    "buildVaccinationView","uniqueValues","filterableTable","vaccinationRows",
    "compactSelect","bindFilterableTables","bindAttributeFilters",
    "cancelNeutralMidnight","scheduleNeutralMidnight","projectNeutralDates","console","URLSearchParams",
    "let uiGeneration=0;\n" + testedCode +
    "\nreturn {enterApp,clearMedicalUi,generation:()=>uiGeneration,nextGeneration:()=>++uiGeneration};");
  const runner = make(app, login, view, recordTagFilters, loginError, location,
    supabase, assertReader,
    target => { app.hidden = target !== app; login.hidden = target !== login; },
    () => {}, { querySelector: () => null }, () => {},
    records => ({
      history: [{ sourceStatus: records[0]?.marker || "" }],
      latest: [{ marker: records[0]?.marker || "" }],
      planned: []
    }),
    values => [...new Set(values)],
    (_headers, rows) => JSON.stringify(rows),
    items => items.map(x => x.marker || x.sourceStatus),
    () => "", () => {}, () => {},
    () => {}, () => {}, () => ({stateById:new Map(),questions:[]}), { error: () => {} },
    class { getAll() { return []; } });
  return { ...runner, app, view, location, pending };
}
{
  const h = createRuntime();
  const oldA = deferred(), oldB = deferred(), freshA = deferred(), freshB = deferred();
  h.pending.push(oldA, oldB, freshA, freshB);
  const old = h.enterApp({ user: { id: "old-synthetic" } }, h.generation());
  for (let i = 0; i < 6; i++) await Promise.resolve();
  h.clearMedicalUi();
  h.location.hash = "#/vaccination"; // local wipe routes to #/; re-login navigates back.
  h.nextGeneration();
  const fresh = h.enterApp({ user: { id: "new-synthetic" } }, h.generation());
  for (let i = 0; i < 6; i++) await Promise.resolve();
  freshA.resolve({ data: [{ marker: "NEW_SESSION" }], error: null });
  freshB.resolve({ data: [], error: null });
  await fresh;
  assert.match(h.view.innerHTML, /NEW_SESSION/);
  oldA.resolve({ data: [{ marker: "OLD_SESSION" }], error: null });
  oldB.resolve({ data: [], error: null });
  await old;
  assert.match(h.view.innerHTML, /NEW_SESSION/);
  assert.doesNotMatch(h.view.innerHTML, /OLD_SESSION/);
}
{
  const gate = deferred();
  const h = createRuntime(() => gate.promise);
  const pending = h.enterApp({ user: { id: "old-synthetic" } }, h.generation());
  h.clearMedicalUi();
  gate.resolve(true);
  await pending;
  assert.equal(h.app.hidden, true);
  assert.equal(h.view.innerHTML, "");
}

// A nonempty cross-tab session replacement must wipe A's medical DOM before
// B's credentials can be observed by this already-open tab.
{
  const h = createRuntime();
  const oldRecords = deferred(), oldPlan = deferred();
  h.pending.push(oldRecords, oldPlan);
  const rendered = h.enterApp({ user: { id: "owner_A" } }, h.generation());
  for (let i = 0; i < 6; i++) await Promise.resolve();
  oldRecords.resolve({ data: [{ marker: "MEDICAL_CONTENT_OWNER_A" }], error: null });
  oldPlan.resolve({ data: [], error: null });
  await rendered;
  assert.match(h.view.innerHTML, /MEDICAL_CONTENT_OWNER_A/);
  assert.equal(h.app.hidden, false);
  let handler;
  new Function("window", "clearMedicalUi", "loginError",
    sourceSlice('window.addEventListener("storage", (event) => {', "\nconst mobileMenu"))(
      { addEventListener: (kind, fn) => { if (kind === "storage") handler = fn; } },
      h.clearMedicalUi,
      { textContent: "" });
  assert.equal(typeof handler, "function");
  handler({
    key: "health.session.v1",
    oldValue: JSON.stringify({ access_token: "synthetic_A", user: { id: "owner_A" } }),
    newValue: JSON.stringify({ access_token: "synthetic_B", user: { id: "owner_B" } })
  });
  assert.equal(h.app.hidden, true);
  assert.equal(h.view.innerHTML, "");
}

// AUTH-01: real loginForm handler + real enterApp + real Auth client. The
// renderer below is synthetic; prior tests independently execute real route().
function passwordLoginFixture() {
  const store = new Map(), tombstones = new Map(), replies = new Map();
  const localStorage = {
    getItem: k => store.get(k) ?? null,
    setItem: (k, v) => store.set(k, v),
    removeItem: k => store.delete(k)
  };
  const sessionStorage = {
    getItem: k => tombstones.get(k) ?? null,
    setItem: (k, v) => tombstones.set(k, v),
    removeItem: k => tombstones.delete(k)
  };
  const fetch = (url, args) => {
    assert.ok(url.includes("grant_type=password"), "no external fetch");
    const email = JSON.parse(args.body).email;
    const promise = deferred();
    replies.set(email, promise);
    return promise.promise;
  };
  const authFactory = new Function("localStorage", "sessionStorage", "window", "fetch",
    authSource.replace("export function createClient(", "function createClient(") +
    "\nreturn createClient;");
  const client = authFactory(localStorage, sessionStorage, { addEventListener() {} }, fetch)(
    "https://synthetic.invalid", "synthetic-key");
  let currentEmail = "", medicalDom = "", readerId = "", loginHandler;
  const loginForm = { addEventListener: (type, fn) => { if (type === "submit") loginHandler = fn; } };
  const app = {};
  const ui = new Function("loginForm","document","loginError","supabase",
    "assertReader","showOnly","app","route",
    "let uiGeneration = 0;\n" +
    sourceSlice("async function enterApp(session, generation) {", "\nasync function boot()") +
    sourceSlice('loginForm.addEventListener("submit", async (event) => {', "\nfunction clearMedicalUi()")
  );
  ui(loginForm, {
    querySelector: selector => selector === "#email" ? { value: currentEmail } :
      selector === "#password" ? { value: "synthetic-pass" } : null
  }, { textContent: "" }, client,
    async user => { readerId = user; return true; },
    () => {}, app, async () => { medicalDom = "MEDICAL_DOM_" + readerId; });
  function respond(email, id) {
    const pending = replies.get(email);
    assert.ok(pending, "missing deferred Auth response " + email);
    pending.resolve({
      ok: true, status: 200,
      json: async () => ({
        access_token: "synthetic_access_" + id,
        refresh_token: "synthetic_refresh_" + id,
        expires_in: 3600,
        user: { id }
      })
    });
  }
  return {
    client, store, replies, respond,
    submit(email) {
      currentEmail = email;
      return loginHandler({ preventDefault() {} });
    },
    get medicalDom() { return medicalDom; }
  };
}
async function assertNewerLoginWins(order) {
  const h = passwordLoginFixture();
  const pendingA = h.submit("email_A");
  const pendingB = h.submit("email_B");
  assert.ok(h.replies.has("email_A") && h.replies.has("email_B"));
  if (order === "A-first") {
    h.respond("email_A", "user_A");
    await pendingA;
    assert.equal(h.store.has("health.session.v1"), false,
      "stale early response must not persist older login");
  }
  h.respond("email_B", "user_B");
  await pendingB;
  assert.equal(h.medicalDom, "MEDICAL_DOM_user_B");
  assert.equal(JSON.parse(h.store.get("health.session.v1")).user.id, "user_B");
  if (order === "B-first") {
    h.respond("email_A", "user_A");
    await pendingA;
  }
  assert.equal(h.medicalDom, "MEDICAL_DOM_user_B");
  assert.equal(JSON.parse(h.store.get("health.session.v1")).user.id, "user_B",
    "late password response must not overwrite newer user's token");
  assert.equal((await h.client.auth.getSession()).data.session.user.id, "user_B");
}
await assertNewerLoginWins("B-first");
await assertNewerLoginWins("A-first");

console.log("HEALTH #58 F-01 / AUTH-01 adversarial generation: 5/5 PASS");
