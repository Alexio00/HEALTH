// HEALTH #58 F-02: localStorage fault injection with a synthetic Auth endpoint.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const content = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../supabase-client.js"), "utf8");
const factory = new Function("localStorage","sessionStorage","window","fetch",
  content.replace("export function createClient(", "function createClient(") + "\nreturn createClient;");
const KEY = "health.session.v1", MARKER = "health.session.revoked.v1";
const synthetic = {
  access_token: "synthetic_access",
  refresh_token: "synthetic_refresh",
  expires_in: 3600,
  user: { id: "synthetic-user" }
};
function harness(faults = {}) {
  const local = new Map(), session = new Map(), calls = [];
  const localStorage = {
    getItem(key) {
      if (faults.read) throw Error("synthetic getItem fault");
      return local.get(key) ?? null;
    },
    setItem(key, value) {
      if (faults.blank && value === "") throw Error("synthetic blank storage fault");
      local.set(key, value);
    },
    removeItem(key) {
      if (faults.remove) throw Error("synthetic remove storage fault");
      local.delete(key);
    }
  };
  const sessionStorage = {
    getItem: key => session.get(key) ?? null,
    setItem: (key, value) => session.set(key, value),
    removeItem(key) {
      if (faults.markerRemove) throw Error("synthetic tombstone removal fault");
      session.delete(key);
    }
  };
  const fetch = async (url) => {
    calls.push(url);
    if (url.includes("grant_type=password"))
      return { ok: true, status: 200, json: async () => synthetic };
    return { ok: !faults.remote, status: faults.remote ? 503 : 200 };
  };
  const make = () => factory(localStorage, sessionStorage, { addEventListener: () => {} }, fetch)
    ("https://synthetic.invalid", "pk_synthetic");
  return { local, session, calls, make, faults };
}
{
  const h = harness({ remove: true });
  const api = h.make();
  assert.equal((await api.auth.signInWithPassword({ email: "synthetic@example.invalid", password: "x" })).error, null);
  assert.equal((await api.auth.signOut()).error, null);
  assert.equal(h.local.get(KEY), "");
  assert.ok(h.calls.some(url => url.endsWith("/auth/v1/logout")));
  assert.equal((await api.auth.getSession()).data.session, null);
}
{
  const h = harness({ remove: true, blank: true });
  const api = h.make();
  await api.auth.signInWithPassword({ email: "synthetic@example.invalid", password: "x" });
  const result = await api.auth.signOut();
  assert.ok(result.error);
  assert.ok(h.local.get(KEY)?.includes("synthetic_access"));
  assert.equal(h.session.get(MARKER), "1");
  assert.ok(h.calls.some(url => url.endsWith("/auth/v1/logout")));
  assert.equal((await api.auth.getSession()).data.session, null);
  assert.equal((await h.make().auth.getSession()).data.session, null);
  assert.doesNotMatch(result.error.message, /synthetic_access|synthetic_refresh/);
}
{
  const h = harness({ remove: true, blank: true, remote: true });
  const api = h.make();
  await api.auth.signInWithPassword({ email: "synthetic@example.invalid", password: "x" });
  const result = await api.auth.signOut();
  assert.ok(result.error);
  assert.ok(h.calls.some(url => url.endsWith("/auth/v1/logout")));
  assert.equal((await api.auth.getSession()).data.session, null);
}
{
  const h = harness();
  const api = h.make();
  await api.auth.signInWithPassword({ email: "synthetic@example.invalid", password: "x" });
  h.local.set(KEY, "{invalid");
  assert.equal((await api.auth.getSession()).data.session, null);
}
{
  const h = harness();
  const api = h.make();
  await api.auth.signInWithPassword({ email: "synthetic@example.invalid", password: "x" });
  h.faults.read = true;
  const result = await api.auth.signOut();
  assert.ok(result.error, "getItem fault must not falsely confirm remote logout");
  assert.equal(h.local.has(KEY), false, "local token removal still attempted");
  assert.equal(h.calls.filter(url => url.endsWith("/auth/v1/logout")).length, 0,
    "server logout impossible without reading access token");
  assert.doesNotMatch(result.error.message, /synthetic_access|synthetic_refresh/);
}
{
  const h = harness();
  const api = h.make();
  await api.auth.signInWithPassword({ email: "synthetic@example.invalid", password: "x" });
  await api.auth.signOut();
  h.faults.markerRemove = true;
  const rejected = await api.auth.signInWithPassword({ email: "synthetic@example.invalid", password: "x" });
  assert.ok(rejected.error, "failed tombstone removal must reject login");
  assert.equal(h.local.has(KEY), false, "rejected login cannot persist credentials");
  assert.equal((await api.auth.getSession()).data.session, null);
  assert.equal(h.session.get(MARKER), "1");
  h.faults.markerRemove = false;
  const accepted = await api.auth.signInWithPassword({ email: "synthetic@example.invalid", password: "x" });
  assert.equal(accepted.error, null, "login works when marker can be cleared");
  assert.equal(h.session.has(MARKER), false);
  assert.ok((await api.auth.getSession()).data.session, "login state must be usable");
}
console.log("HEALTH #58 F-02 storage fault regression: 6/6 PASS");
