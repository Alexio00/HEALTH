// HEALTH PR #100: F-01 adversarial generation regressions, synthetic only.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../app.js"), "utf8");
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
    "compactSelect","bindFilterableTables","bindAttributeFilters","console","URLSearchParams",
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
    () => "", () => {}, () => {}, { error: () => {} },
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
console.log("HEALTH #58 F-01 adversarial auth/UI generation: 2/2 PASS");
