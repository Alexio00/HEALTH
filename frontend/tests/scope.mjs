import assert from "node:assert/strict";
import { scopePolicy } from "../release/scope.mjs";
const head = "a".repeat(40);
const owner = { authorId: 308028794, head, body: "PWA-RELEASE-CONTROL: " + head };
const ordinary = { authorId: 1, head, body: "" };
const entry = path => [{ path, mode: "100644" }];
for (const p of ["frontend/app.js", "frontend/tests/contract.mjs", "docs/PWA_RELEASE.md", "AGENTS.md"])
  assert.doesNotThrow(() => scopePolicy(entry(p), ordinary));
for (const p of ["scripts/writer/x.py", "db/x.sql", "supabase/x.ts",
  ".github/workflows/owner-authorize.yml", "frontend/private/x.json", "frontend/.env",
  "frontend/records/a.json", "frontend/x.sql", "sources/x.pdf", "docs/WRITER.md"])
  assert.throws(() => scopePolicy(entry(p), owner), undefined, p);
for (const p of [".github/workflows/deploy-pages.yml", ".github/workflows/code-validation.yml",
  ".github/workflows/pwa-scope.yml", "frontend/release/scope.mjs"]) {
  assert.throws(() => scopePolicy(entry(p), ordinary));
  assert.throws(() => scopePolicy(entry(p), { ...owner, head: "b".repeat(40) }));
  assert.throws(() => scopePolicy(entry(p), { ...owner, authorId: 1 }));
  assert.doesNotThrow(() => scopePolicy(entry(p), owner));
}
assert.throws(() => scopePolicy([{ path: "frontend/app.js", mode: "120000" }], owner));
assert.throws(() => scopePolicy(entry("frontend/../db/a"), owner));
assert.throws(() => scopePolicy([], owner));
console.log("PASS: scope allowlist, backend denial, symlinks, exact-head owner control");


// Issue #40A: exercise exact production implementations against the
// independently reported malformed metadata and bilingual overdue inputs.
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { plannedVaccinations, neutralPlanSourceStatus } from "../vaccination.mjs";
const appSource=readFileSync("frontend/app.js","utf8");
const start=appSource.indexOf("const NEUTRAL_DATE_TEXT =");
const end=appSource.indexOf("// Binding both authentication",start);
assert(start>0 && end>start);
const actual=vm.runInNewContext(appSource.slice(start,end)+
  "\n({projectNeutralDates,moscowCalendarDay})",{Intl,Date,Map});
const item=(metadata)=>({plan_item_id:1,title:"Synthetic item",status:"planned",
  due_on:"2026-10-14",metadata});
for(const meta of [
  {historical:"true"},{due_text:{description:"conditional"}},
  {source_status:123},{historical:1},{due_text:[]},
  {source_status:false},{deadline_condition:{x:true}},{date_kind:"exact"}
]) {
  const p=actual.projectNeutralDates([item(meta)],new Date("2026-10-15T12:00:00Z"));
  assert.equal(p.questions.length,0,"metadata must fail closed: "+JSON.stringify(meta));
  assert.equal(p.stateById.get(1),"UNDETERMINED");
}
for(const meta of [{},{historical:false},{source_status:"planned"},{due_text:""}]) {
  assert.equal(actual.projectNeutralDates([item(meta)],
    new Date("2026-10-15T12:00:00Z")).questions.length,1);
}
for(const status of ["OVERDUE"," overdue ","Overdue","Просрочено"," ПРОСРОЧЕНО "]) {
  assert.equal(neutralPlanSourceStatus(status),"Запланировано");
  const rows=plannedVaccinations([{plan_item_id:1,title:"Synthetic flu vaccination",
    status:"planned",due_on:"2025-05-01",
    metadata:{kind:"вакцинация",source_status:status}}],"2026-10-15");
  assert.equal(rows[0].sourceStatus,"Запланировано");
  assert.equal(rows[0].overdue,false);
}
assert(appSource.includes('neutralPlanSourceStatus(x.metadata?.source_status, "запланировано")'));
console.log("PASS #40A auditor BLOCKER-01/02 typed metadata and overdue claims");
