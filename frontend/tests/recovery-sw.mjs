// Verify the exact legacy shell SW cannot intercept the new Auth callback.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const base = "https://synthetic.invalid/HEALTH/";
const source = readFileSync("frontend/sw.js", "utf8");
const html = readFileSync("frontend/recovery.html", "utf8");
const entry = readFileSync("frontend/recovery.js", "utf8");
const build = readFileSync("frontend/release/build.mjs", "utf8");
const cacheName = "health-shell-" + "a".repeat(40);
const shellHash = Object.fromEntries(
  ["index.html", "styles.css", "app.js", "vaccination.mjs", "supabase-client.js",
    "config.js", "manifest.webmanifest", "icon.svg"].map(x=>["./"+x,"0".repeat(64)]));
const legacy = source.replaceAll("__HEALTH_RELEASE__", "a".repeat(40))
  .replace("/* __HEALTH_HASHES__ */ {}", JSON.stringify(shellHash));
assert.notEqual(legacy,source);
const handlers = {};
const oldShell = new Map([
  [base+"index.html",new Response("OLD_RELEASE_INDEX",{headers:{"content-type":"text/html"}})],
  [base+"app.js",new Response("OLD_RELEASE_APP",{headers:{"content-type":"text/javascript"}})],
  [base+"supabase-client.js",new Response("OLD_RELEASE_CLIENT",{headers:{"content-type":"text/javascript"}})]
]);
let network = 0;
const context = vm.createContext({
  URL, Request, Response, caches:{open:async()=>({
    match:async key=>oldShell.get(String(key)),
    put:async()=>{throw new Error("unexpected write");}
  })},
  fetch:async()=>{network++;throw new Error("offline");},
  self:{location:new URL(base+"sw.js"),addEventListener:(name,fn)=>{handlers[name]=fn;}}
});
vm.runInContext(legacy,context);
const intercept=async path=>{
  let result, called=false;
  handlers.fetch({
    request:new Request(new URL(path,base)),
    respondWith:p=>{called=true;result=p;}
  });
  return {called,content:called?(await result).text():null};
};
assert.equal((await intercept("#access_token=synthetic&type=recovery")).called,true,
  "legacy root callback serves old app (previous security regression)");
assert.equal((await intercept("app.js")).called,true);
assert.equal((await intercept("supabase-client.js")).called,true);
assert.equal(network,0,"legacy shell cache is genuinely network-free");
for(const path of [
  "recovery.html#access_token=synthetic&type=recovery",
  "recovery.js",
  "supabase-client.js?recovery-entry-v1",
  "config.js?recovery-entry-v1"
]) {
  assert.equal((await intercept(path)).called,false,
    path+": old Service Worker MUST bypass recovery assets");
}
assert.equal(network,0,"legacy SW did not attempt a fallback to cached app");
assert(entry.includes('import { createClient } from "./supabase-client.js?recovery-entry-v1"'));
assert(entry.includes('from "./config.js?recovery-entry-v1"'));
assert(!entry.includes('import "./app.js"'),"callback never loads medical reader");
assert(/history.replaceState\(null, "", location.pathname\)/.test(entry));
assert(html.includes('src="./recovery.js"'));
assert(!html.includes('src="./app.js"'));
assert(html.includes('content="no-referrer"'));
assert(build.includes('"recovery.html", "recovery.js"'));
assert(!source.includes('"./recovery.html"') && !source.includes('"./recovery.js"'),
  "new and legacy SW intentionally leave recovery assets outside shell cache");
console.log("PASS #103 legacy-SW old cached shell → uncached callback, network-only scripts, fail-closed offline");
