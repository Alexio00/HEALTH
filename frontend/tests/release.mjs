import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, rmSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import vm from "node:vm";
import { webcrypto } from "node:crypto";
import { build, RUNTIME_FILES } from "../release/build.mjs";
import { probe, retryProbe, validateMarker } from "../release/smoke.mjs";
const root = mkdtempSync(join(tmpdir(), "health-release-"));
const sha = "a".repeat(40), other = "b".repeat(40), base = "https://synthetic.test/HEALTH/";
const mime = path => path.endsWith(".html") ? "text/html" : path.endsWith(".css") ? "text/css" :
  path.endsWith(".svg") ? "image/svg+xml" : /\.(mjs|js)$/.test(path) ? "text/javascript" : "application/json";
try {
  const manifest = build("frontend", root, sha);
  assert.throws(() => build("frontend", join(root, "bad"), "../bad"));
  assert.equal(manifest.sha, sha);
  assert.deepEqual(Object.keys(manifest.files), RUNTIME_FILES);
  assert.ok(!readdirSync(root).includes("tests"));
  assert.ok(!readdirSync(root).includes("release"));
  assert.ok(readFileSync(join(root, "index.html"), "utf8").includes('data-release-sha="' + sha + '"'));
  const source = readFileSync(join(root, "sw.js"), "utf8");
  assert.ok(source.includes("health-shell-"));
  assert.ok(!source.includes("__HEALTH_"));
  const generated2 = build("frontend", join(root, "second"), other);
  assert.notEqual(manifest.files["sw.js"], generated2.files["sw.js"]);
  assert.notEqual(manifest.files["index.html"], generated2.files["index.html"]);
  // Synthetic UI rollback: restore good bytes, rebuild under a NEW identity.
  const rollbackSource = join(root, "rollback-source");
  for (const path of RUNTIME_FILES) {
    mkdirSync(join(rollbackSource, path, ".."), { recursive: true });
    writeFileSync(join(rollbackSource, path), readFileSync(join("frontend", path)));
  }
  const originalApp = readFileSync(join(rollbackSource, "app.js"));
  writeFileSync(join(rollbackSource, "app.js"), Buffer.concat([originalApp, Buffer.from("\n// faulty synthetic UI change\n")]));
  const broken = build(rollbackSource, join(root, "broken"), "c".repeat(40));
  writeFileSync(join(rollbackSource, "app.js"), originalApp);
  const rollback = build(rollbackSource, join(root, "rollback"), "d".repeat(40));
  assert.notEqual(broken.files["app.js"], manifest.files["app.js"]);
  assert.equal(rollback.files["app.js"], manifest.files["app.js"]);
  assert.notEqual(rollback.files["sw.js"], manifest.files["sw.js"]);
  assert.notEqual(rollback.sha, manifest.sha);
  let corrupt = "", htmlInsteadOfJS = false, offline = false, fetched = 0, skips = 0;
  async function fetcher(url) {
    fetched++;
    if (offline) throw new Error("offline");
    const path = new URL(url).pathname.replace("/HEALTH/", "") || "index.html";
    const bytes = corrupt === path ? Buffer.from("wrong release") : readFileSync(join(root, path));
    return new Response(bytes, { headers: { "content-type": htmlInsteadOfJS && path.endsWith(".js") ? "text/html" : mime(path) } });
  }
  assert.equal((await probe(base, sha, fetcher)).files, 15);
  await assert.rejects(probe(base, other, fetcher), /SHA mismatch/);
  corrupt = "app.js";
  await assert.rejects(probe(base, sha, fetcher), /bytes mismatch/);
  corrupt = ""; htmlInsteadOfJS = true;
  await assert.rejects(probe(base, sha, fetcher), /MIME failure/);
  htmlInsteadOfJS = false;
  assert.throws(() => validateMarker({ ...manifest, files: { ...manifest.files, "../private": "0".repeat(64) } }, sha));
  let tries = 0, waits = 0;
  assert.equal(await retryProbe(async () => { if (++tries < 3) throw new Error("stale CDN"); return "PASS"; },
    { attempts: 3, wait: async () => waits++ }), "PASS");
  assert.equal(waits, 2);
  tries = 0;
  await assert.rejects(retryProbe(async () => { tries++; throw new Error("permanent"); },
    { attempts: 2, wait: async () => {} }));
  assert.equal(tries, 2);
  const handlers = {}, stores = new Map();
  const caches = {
    open: async key => {
      if (!stores.has(key)) stores.set(key, new Map());
      return { put: async (url, response) => stores.get(key).set(String(url), response),
        match: async url => stores.get(key).get(String(url)) };
    },
    keys: async () => [...stores.keys()],
    delete: async key => stores.delete(key)
  };
  const context = vm.createContext({ URL, Request, Response, crypto: webcrypto, caches, fetch: fetcher,
    Uint8Array, self: { location: new URL(base + "sw.js"), addEventListener: (name, fn) => handlers[name] = fn,
      skipWaiting: async () => skips++, clients: { claim: async () => {} } } });
  vm.runInContext(source, context);
  let pending;
  corrupt = "app.js";
  handlers.install({ waitUntil: p => pending = p });
  await assert.rejects(pending, /mismatched/);
  assert.equal(stores.get("health-shell-" + sha).size, 0, "failed install must not create a partial shell");
  assert.equal(skips, 0);
  corrupt = "";
  handlers.install({ waitUntil: p => pending = p }); await pending;
  assert.equal(stores.get("health-shell-" + sha).size, 8);
  assert.equal(skips, 1);
  stores.set("health-shell-v14", new Map());
  handlers.activate({ waitUntil: p => pending = p }); await pending;
  assert.ok(!stores.has("health-shell-v14"));
  offline = true;
  for (const path of ["#/vaccination", "#/records", "#/medications", "app.js"]) {
    const count = fetched; let promise;
    handlers.fetch({ request: new Request(new URL(path, base)), respondWith: p => promise = p });
    assert.equal((await promise).status, 200);
    assert.equal(fetched, count, "built worker must serve its coherent release");
  }
  console.log("PASS: exact artifact marker/hashes, bounded smoke failures, atomic SW install, automatic cache SHA and coherent offline routes");
} finally { rmSync(root, { recursive: true, force: true }); }
