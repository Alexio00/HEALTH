import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
const source = readFileSync(process.env.SW_TEST_FILE || "frontend/sw.js", "utf8");
const origin = "https://example.test/HEALTH/";
const handlers = {};
const stores = new Map();
let online = true, status = 200, responseHeaders = {}, redirected = false, writes = 0;
const mime = url => url.endsWith(".html") ? "text/html" : url.endsWith(".css") ? "text/css" :
  url.endsWith(".webmanifest") ? "application/manifest+json" : url.endsWith(".svg") ? "image/svg+xml" : "text/javascript";
const cache = key => {
  if (!stores.has(key)) stores.set(key, new Map());
  return {
    put: async (url, res) => { writes++; stores.get(key).set(String(url), res); },
    match: async url => stores.get(key).get(String(url))
  };
};
const context = vm.createContext({
  URL, Request, Response, console, crypto: globalThis.crypto,
  caches: { open: async key => cache(key), keys: async () => [...stores.keys()],
    delete: async key => stores.delete(key) },
  self: { location: new URL(origin + "sw.js"), addEventListener: (name, f) => handlers[name] = f,
    skipWaiting: async () => {}, clients: { claim: async () => {} } },
  fetch: async url => {
    if (!online) throw new Error("offline");
    const res = new Response("synthetic", { status, headers: { "content-type": mime(String(url)), ...responseHeaders } });
    Object.defineProperty(res, "redirected", { value: redirected });
    return res;
  }
});
vm.runInContext(source, context);
const key = (path, init) => context.cacheKey(new Request(new URL(path, origin), init));
for (const path of ["", "index.html", "app.js", "styles.css", "vaccination.mjs", "#/vaccination", "#/records", "#/medications"])
  assert.ok(key(path), path);
for (const path of ["app.js?token=secret", "?code=abc", "?x=1", "oauth-test/consent.html",
  "oauth-home.html", "api/records", "records", "release.json", "https://db.test/api", "other.js"])
  assert.equal(key(path), null, path);
assert.equal(key("app.js", { method: "POST" }), null);
assert.equal(key("app.js", { headers: { authorization: "Bearer synthetic" } }), null);
assert.equal(key("app.js", { headers: { range: "bytes=0-1" } }), null);
const app = origin + "app.js";
assert.ok(context.safeResponse(new Response("ok", { headers: { "content-type": "text/javascript" } }), app));
for (const headers of [{ "cache-control": "no-store" }, { "cache-control": "private, max-age=10" },
  { "cache-control": "no-cache" }, { vary: "*" }, { vary: "Authorization" }, { "content-type": "text/html" }])
  assert.equal(context.safeResponse(new Response("x", { headers: { "content-type": "text/javascript", ...headers } }), app), false);
assert.equal(context.safeResponse(new Response("x", { status: 404 }), app), false);
const redir = new Response("x", { headers: { "content-type": "text/javascript" } });
Object.defineProperty(redir, "redirected", { value: true });
assert.equal(context.safeResponse(redir, app), false);
let pending;
handlers.install({ waitUntil: p => pending = p });
await pending;
assert.equal(writes, 8);
stores.set("health-shell-v14", new Map([["private", "old"]]));
stores.set("other-app", new Map());
handlers.activate({ waitUntil: p => pending = p });
await pending;
assert.equal(stores.has("health-shell-v14"), false);
assert.equal(stores.has("other-app"), true);
online = false;
for (const path of ["#/vaccination", "#/records", "#/medications", "app.js"]) {
  let result;
  handlers.fetch({ request: new Request(new URL(path, origin)), respondWith: p => result = p });
  assert.equal((await result).status, 200);
}
for (const path of ["oauth-test/consent.html", "?access_token=x", "api/records"]) {
  let intercepted = false;
  handlers.fetch({ request: new Request(new URL(path, origin)), respondWith: () => intercepted = true });
  assert.equal(intercepted, false);
}
console.log("PASS: SW allowlist, headers/query denial, response policy, install, cleanup, offline hash routes");
