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
